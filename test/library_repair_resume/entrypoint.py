"""Freeze and replay a one-case missing-entrypoint intervention, without model calls."""
import argparse
import copy
import hashlib
from pathlib import Path
import shutil

from test.library_repair.core import ROOT, read, dump, digest, original_package, repaired_package, source_output
from test.library_repair.format_replay import extract_single_fence
from test.library_repair.evaluator import grade, prepare as prepare_runtime
from test.interface_blind.core import write_files
from test.webbench_expand.generate import output_files
from test.replay_library_repair import report_passed
from gui_dna.provider import parse_json
from .run import folder as library_folder, now

OUT = ROOT / 'artifacts/library-repair-entrypoint-20261114'
FULL = ROOT / 'artifacts/library-repair-full-20261114'


def prepare():
    assert not (OUT / 'inputs.json').exists()
    results = read(ROOT / 'test/results/library-repair-full.json')
    chosen = [r for r in results['rows'] if r['format'] == 'single_fence' and r['project'] == 'table'
              and r['builder'] == 'anthropic/claude-sonnet-4.5' and r['model'] == 'openai/gpt-oss-120b'
              and r['kind'] == 'candidate' and r['method'] == 'plan' and r['task'] == 4]
    assert len(chosen) == 2 and all(r['baseline']['passed'] and not r['passed'] for r in chosen)
    assert chosen[0]['source'] == chosen[1]['source']
    source = ROOT / chosen[0]['source']
    parsed = source_output(source)
    original = original_package('table', 'anthropic/claude-sonnet-4.5')
    base_files = output_files('plan', original, parsed)
    assert 'index.js' in base_files and 'src="index.js"' in base_files['index.html']
    missing = copy.deepcopy(base_files)
    del missing['index.js']
    variants = [('original', base_files), ('original_remove_entry', missing)]
    for condition in ('review', 'feedback'):
        response = read(library_folder('table', 'anthropic/claude-sonnet-4.5', condition) / 'output.json')['text']
        package = repaired_package(original, parse_json(extract_single_fence(response)))
        assert 'index.js' not in package['files']
        restored = copy.deepcopy(package)
        restored['files']['index.js'] = original['files']['index.js']
        before, after = [output_files('plan', p, parsed) for p in (package, restored)]
        assert set(after) - set(before) == {'index.js'}
        assert all(after[k] == v for k, v in before.items())
        variants += [(condition, before), (condition + '_restore_placeholder', after)]
    rows, jobs, hashes = [], {}, {}
    full = read(FULL / 'inputs.json')
    for name, files in variants:
        sha = digest(files)
        key = f'table/task-4/{sha}'
        page = OUT / 'pages' / name
        write_files(page, files)
        jobs[key] = {'page': str(page.relative_to(ROOT)), 'files_sha256': sha,
                     'reuse': str((FULL / 'scores' / key).relative_to(ROOT)) if key in full['jobs'] else None}
        rows.append({'name': name, 'score_key': key, 'entry_present': 'index.js' in files})
        for path in page.rglob('*'):
            if path.is_file():
                hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    inputs = {'source': str(source.relative_to(ROOT)), 'plan': parsed, 'rows': rows, 'jobs': jobs,
              'scope': 'Posthoc single table/Sonnet/GPT-OSS/task-4 fixed-plan intervention; not a new model score.'}
    dump(OUT / 'inputs.json', inputs)
    paths = [Path(__file__), Path(__file__).with_name('ENTRYPOINT.md'), OUT / 'inputs.json',
             ROOT / 'test/results/library-repair-full.json', ROOT / 'test/library_repair/evaluator.py']
    hashes.update({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    dump(OUT / 'snapshot.json', {'frozen_utc': now(), 'sha256': hashes})
    print('Frozen', len(rows), 'pages;', sum(bool(j['reuse']) for j in jobs.values()), 'exact report reuses')


def verify():
    for path, sha in read(OUT / 'snapshot.json')['sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    return read(OUT / 'inputs.json')


def evaluate():
    inputs = verify()
    prepare_runtime()
    for key, job in inputs['jobs'].items():
        folder = OUT / 'scores' / key
        if (folder / 'score.json').exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        if job['reuse']:
            previous = ROOT / job['reuse']
            score = read(previous / 'score.json')
            assert hashlib.sha256((previous / 'report.json').read_bytes()).hexdigest() == score['report_sha256']
            for name in ('score.json', 'report.json'):
                shutil.copy2(previous / name, folder / name)
        else:
            dump(folder / 'score.json', grade('table', ROOT / job['page'], 'task-4', folder / 'report.json'))
        print(key, read(folder / 'score.json')['all_passed'], flush=True)
    dump(OUT / 'evaluation-complete.json', {'inputs_sha256': digest(inputs), 'finished_utc': now()})


def analyze():
    inputs = verify()
    assert read(OUT / 'evaluation-complete.json')['inputs_sha256'] == digest(inputs)
    scores = {}
    for key, job in inputs['jobs'].items():
        folder = OUT / 'scores' / key
        score = read(folder / 'score.json')
        assert hashlib.sha256((folder / 'report.json').read_bytes()).hexdigest() == score['report_sha256']
        assert report_passed(read(folder / 'report.json')) == score['all_passed']
        scores[key] = score['all_passed']
    result = {**inputs, 'rows': [{**r, 'passed': scores[r['score_key']]} for r in inputs['rows']],
              'audit': {'pages': len(inputs['rows']), 'unique_reports': len(scores),
                        'reused_reports': sum(bool(j['reuse']) for j in inputs['jobs'].values())}}
    dump(ROOT / 'test/results/library-repair-entrypoint.json', result)
    print(result['rows'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'evaluate', 'analyze'])
    {'prepare': prepare, 'evaluate': evaluate, 'analyze': analyze}[parser.parse_args().phase]()
