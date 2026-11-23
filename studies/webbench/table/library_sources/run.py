"""Freeze, generate and replay a single prespecified three-arm table comparison."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from scripts.check_openrouter_credits import check_credits
from studies import browser_jobs
from studies.interface_blind.core import write_files
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.study_io import ROOT, UPSTREAM, digest, dump, now, read, sha, source_files
from studies.webbench_expand.core import config
from studies.table_library_sources.core import (
    AI, ARMS, CONTROLLERS, HERE, MODEL, MODULES, OUT, SOURCE, STARTED, TASKS,
    messages, packages, render, starter,
)

CAP = .90
END = datetime.fromisoformat('2026-11-23T05:42:00+00:00')
TARGETS = [(arm, task) for task in TASKS for arm in ARMS]
CONTROLS = ('starter', 'upstream_final', 'reference_full', 'ai_example2')
HARNESS = '157-table'


def file_hashes(files):
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(files))}


def verify(manifest):
    for path, checksum in manifest.items():
        if sha(ROOT / path) != checksum:
            raise ValueError(f'Frozen input changed: {path}')


def freeze():
    if OUT.exists():
        raise RuntimeError('Preserve prior stage directory')
    credit = check_credits(CAP)
    if not credit['sufficient']:
        raise BudgetStop('Insufficient balance')
    revision = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != '7b31ca2b786eef120dd49ce63dd03d0c0006046d':
        raise ValueError('Unexpected Web-Bench revision')
    pkg = packages()
    for arm in ARMS[:-1]:
        dump(OUT / (arm + '-package.json'), pkg[arm])
    pages = {'starter': starter(),
             'upstream_final': {str(p.relative_to(SOURCE / 'src')): p.read_text()
                                for p in (SOURCE / 'src').rglob('*') if p.is_file() and '.spec.' not in p.name},
             'reference_full': render('reference', pkg['reference'], {'controllers': list(CONTROLLERS)}),
             'ai_example2': render('ai', pkg['ai'], pkg['ai']['examples'][1]['plan'])}
    for name, page in pages.items():
        write_files(OUT / 'control-pages' / name, page)
    for arm, task in TARGETS:
        dump(OUT / 'inputs' / arm / (task + '.json'), messages(arm, task, pkg[arm]))
    browser_jobs.OUT = OUT
    assert browser_jobs.prepare_harness('expansion', 'table') == HARNESS
    public_sources = [*sorted((SOURCE / 'src-init').iterdir()), SOURCE / 'tasks.jsonl',
                      SOURCE / 'src/index.css', SOURCE / 'src/index.js', SOURCE / 'src/index.html',
                      *(SOURCE / f'src/common/{m}.js' for m in MODULES)]
    inputs = [HERE / n for n in ('core.py', 'run.py', 'compiler.js', 'PROTOCOL.md')]
    inputs += public_sources + [AI, AI.parent / 'messages.json', AI.parent / 'record.json']
    inputs += [ROOT / p for p in ('studies/interface_blind/core.py', 'studies/interface_blind/compile.cjs',
               'studies/webbench_expand/core.py', 'studies/webbench_expand/schema.py',
               'studies/study_io.py', 'studies/browser_jobs.py','studies/todomvc_dna/evaluate.py',
               'studies/streaming_provider_v2.py', 'studies/provider_ext.py','src/gui_dna/provider.py',
               'src/gui_dna/budget.py','src/gui_dna/tasks.py','studies/ledger_read.py',
               'artifacts/webbench-expand-runtime-157/package-lock.json')]
    originals = [p for p in (SOURCE / 'test').rglob('*') if p.is_file()]
    tested = [OUT / 'harness' / HARNESS / 'test' / p.relative_to(SOURCE / 'test') for p in originals]
    assert all(sha(a) == sha(b) for a,b in zip(originals, tested))
    inputs.extend(originals + tested + [OUT / 'harness' / HARNESS / 'playwright.config.cjs',
                                       OUT / 'harness' / HARNESS / 'package.json'])
    inputs += sorted((OUT / 'inputs').rglob('*.json')) + [OUT / (a + '-package.json') for a in ARMS[:-1]]
    inputs.extend(p for p in (OUT / 'control-pages').rglob('*') if p.is_file())
    finished = now()
    dump(OUT / 'freeze.json', {'opened_utc': STARTED, 'frozen_utc': finished,
         'agent_preparation_elapsed_seconds': (datetime.fromisoformat(finished) - datetime.fromisoformat(STARTED)).total_seconds(),
         'opening_credit_check': credit, 'upstream_revision': revision, 'inputs_sha256': file_hashes(inputs),
         'targets': TARGETS, 'controls': CONTROLS, 'model': MODEL, 'budget_usd': CAP})


def attempt(client, stage, arm, task, prompt, pkg):
    folder = OUT / 'candidates' / arm / task / stage
    saved = folder / 'record.json'
    if saved.exists():
        rec = read(saved)
        if rec['prompt_sha256'] != digest(prompt):
            raise ValueError('Saved prompt changed')
        return rec
    rec = {'stage': stage, 'arm': arm, 'task': task, 'generated': False, 'valid': False,
           'prompt_sha256': digest(prompt)}
    try:
        if datetime.now(timezone.utc) >= END and not (folder / 'call/request.json').exists():
            raise BudgetStop('Closed to new requests')
        raw = client.call(MODEL, prompt, folder / 'call', arm + '-' + stage, seed=20261123)
        rec['generated'] = True
        parsed = parse_json(raw)
        files = render(arm, pkg, parsed)
        write_files(folder / 'page', files)
        rec.update(valid=True, files_sha256=source_files(folder / 'page'))
    except (ProviderError, BudgetStop, ValueError, KeyError, TypeError) as error:
        rec['error'] = str(error)[:1200]
    rec['receipt_sha256'] = file_hashes(p for name in ('request.json', 'response.json', 'error.json', 'stream-events.jsonl')
                                      if (p := folder / 'call' / name).is_file())
    dump(saved, rec)
    return rec


def generate():
    manifest = read(OUT / 'freeze.json')
    verify(manifest['inputs_sha256'])
    if (OUT / 'generation-complete.json').exists() or datetime.now(timezone.utc) >= END:
        raise RuntimeError('Stage closed')
    cfg = config()
    cfg.update(models=[MODEL], max_tokens=8192, provider_order={}, budget_usd=CAP, stop_new_requests_usd=CAP)
    cfg['model_price_caps'][MODEL] = {'prompt': .2, 'completion': .8}
    client = StreamingOpenRouter(cfg, Ledger(OUT / 'budget.sqlite3', CAP, CAP))
    client.RATE_LIMIT_TRIES = 1
    pkg = {a: read(OUT / (a + '-package.json')) for a in ARMS[:-1]} | {'direct': None}

    def first(target):
        arm, task = target
        prompt = read(OUT / 'inputs' / arm / (task + '.json'))
        return attempt(client, 'first', arm, task, prompt, pkg[arm])

    def repair(row):
        arm, task = row['arm'], row['task']
        folder = OUT / 'candidates' / arm / task / 'first/call'
        prompt = read(folder / 'request.json')['body']['messages']
        raw = read(folder / 'response.json')['choices'][0]['message']['content']
        prompt.extend([{'role': 'assistant', 'content': raw}, {'role': 'user', 'content':
            'Public format/compiler feedback: ' + row['error'] +
            '\nReturn the complete corrected JSON output. No behavioral feedback is available.'}])
        return attempt(client, 'repair', arm, task, prompt, pkg[arm])

    with ThreadPoolExecutor(max_workers=5) as pool:
        probe = list(pool.map(first, TARGETS[:3]))
        if not any(r['generated'] for r in probe):
            raise RuntimeError('No model response in the first probe; stopped')
        rows = probe + list(pool.map(first, TARGETS[3:]))
        rows += list(pool.map(repair, [r for r in rows if r['generated'] and not r['valid']]))
    frozen = [p for p in (OUT / 'candidates').rglob('*') if p.is_file()]
    dump(OUT / 'generation-complete.json', {'frozen_utc': now(), 'freeze_sha256': sha(OUT / 'freeze.json'),
                                            'rows': rows, 'files_sha256': file_hashes(frozen)})


def evaluate(control):
    browser_jobs.OUT = OUT
    freeze_data = read(OUT / 'freeze.json')
    verify(freeze_data['inputs_sha256'])
    if control:
        jobs = [(name + '/' + t, t, OUT / 'control-pages' / name) for t in TASKS for name in CONTROLS]
        marker = OUT / 'controls-complete.json'
    else:
        gen = read(OUT / 'generation-complete.json')
        assert gen['freeze_sha256'] == sha(OUT / 'freeze.json')
        verify(gen['files_sha256'])
        jobs = []
        for row in gen['rows']:
            arm, task, stage = row['arm'], row['task'], row['stage']
            if row['valid']:
                key = f'{arm}/{task}/{stage}'
                jobs.append((key, task, OUT / 'candidates' / key / 'page'))
        marker = OUT / 'scores-complete.json'
    def score(one):
        key, task, page = one
        job = {'harness': HARNESS, 'runtime': '157', 'page': str(page.relative_to(ROOT)),
               'files': source_files(page), 'specs': browser_jobs.current_task_specs(task)}
        result = browser_jobs.grade(key, job, calibration=control)
        return key, {'passed': result['all_passed'], 'report_sha256': result['report_sha256']}
    with ThreadPoolExecutor(max_workers=4) as pool:
        scored = dict(pool.map(score, jobs))
    dump(marker, {'completed_utc': now(), 'rows': scored})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'controls', 'generate', 'score'))
    args = parser.parse_args()
    if args.action == 'freeze':
        freeze()
    elif args.action == 'generate':
        generate()
    else:
        evaluate(args.action == 'controls')
