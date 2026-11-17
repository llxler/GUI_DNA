"""One effective revision per library and condition, with immutable inputs."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import shutil
import subprocess

from gui_dna.budget import Ledger, BudgetStop
from gui_dna.provider import ProviderError, parse_json
from test.ledger_read import calls, totals
from test.review_stage import freeze
from test.streaming_provider_v2 import StreamingOpenRouter
from .core import (ROOT, HERE, OUT, ORIGINAL, PROJECTS, BUILDERS, MODELS, CONDITIONS,
                   PUBLIC_TASKS, TEST_TASKS, config, read, dump, digest, slug,
                   messages_for, original_package, repaired_package, source_folder)


def now():
    return datetime.now(timezone.utc).isoformat()


def library_folder(project, builder, condition):
    return OUT / 'libraries' / project / slug(builder) / condition


def freeze_inputs():
    assert read(OUT / 'calibration-complete.json')['all_passed']
    files = [HERE / n for n in ('__init__.py', 'core.py', 'run.py', 'evaluator.py', 'evaluate.py', 'PROTOCOL.md')]
    files += [ROOT / p for p in (
        'test/provider_ext.py', 'test/streaming_provider_v2.py', 'src/gui_dna/provider.py',
        'src/gui_dna/budget.py', 'test/interface_blind/core.py', 'test/interface_blind/compile.cjs',
        'test/webbench_expand/core.py', 'test/webbench_expand/schema.py',
        'test/webbench_expand/generate.py', 'test/webbench_expand/free_build.cjs',
        'test/webbench_expand/evaluate_pinned.py', 'test/behavior_feedback.py',
        'test/webbench_expand/runtime-lock.json')]
    files += [OUT / p for p in ('public-inputs.json', 'input-provenance.json', 'calibration-complete.json')]
    files += [ROOT / p for p in read(OUT / 'input-provenance.json')['public_reports_sha256']]
    for project in PROJECTS:
        files.append(ROOT / 'artifacts/web-bench/projects' / project / 'tasks.jsonl')
        for builder in BUILDERS:
            files.append(ORIGINAL / 'libraries' / project / slug(builder) / 'package.json')
            for model in MODELS:
                for method in ('plan', 'free_lib'):
                    for k in set(TEST_TASKS) | (set(PUBLIC_TASKS) if model == MODELS[0] and method == 'plan' else set()):
                        folder = source_folder(project, builder, model, method, k)
                        files += [folder / 'record.json', folder / 'hidden.json']
                        files += sorted(folder.glob('output-*.json'))
    freeze(OUT, config(), sorted({str(p.relative_to(ROOT)) for p in files}), {
        'public_tasks': list(PUBLIC_TASKS), 'test_tasks': list(TEST_TASKS),
        'conditions': list(CONDITIONS), 'valid_responses': 12, 'seed': 20261113,
        'selection': 'One valid response; invalid patch deploys original library. No behavioral selection.',
        'scope': 'Posthoc implementation intervention; fixed source outputs; all requirements previously visible.',
        'budget': 'New user authorization USD10; stage cap9, stop8.6; original scale study stays paused.'})


def archive_missing(folder, messages):
    lost = folder / 'call'
    settled = {c['id'] for c in calls(OUT / 'budget.sqlite3') if c['actual'] is not None}
    requests = list(lost.rglob('request.json'))
    for path in requests:
        request = read(path)
        assert request['body']['messages'] == messages
    # Let the provider replay an already settled response, never sample it again.
    if any(read(p)['call_id'] in settled for p in requests):
        return
    if lost.exists():
        parent = OUT / 'discarded-transport' / folder.relative_to(OUT)
        dest = parent / str(max((int(p.name) for p in parent.glob('[0-9]*')), default=0) + 1)
        dest.mkdir(parents=True)
        if (folder / 'record.json').exists():
            shutil.copy2(folder / 'record.json', dest / 'record.json')
        dump(dest / 'receipt.json', {'messages_sha256': digest(messages), 'valid_responses_retained': 0,
                                   'reason': 'Retry missing transport only; unknown reservations retained.'})
        shutil.move(str(lost), str(dest / 'call'))


def revise(client, project, builder, condition, resume=False):
    folder = library_folder(project, builder, condition)
    target = folder / 'record.json'
    public = read(OUT / 'public-inputs.json')[project][builder]
    messages = messages_for(project, builder, condition, public)
    if target.exists():
        record = read(target)
        assert read(folder / 'messages.json') == messages
        if record['status'] == 'complete' or not resume:
            return record
        assert record['status'] == 'transport_incomplete'
        archive_missing(folder, messages)
    else:
        dump(folder / 'messages.json', messages)
    original = original_package(project, builder)
    record = {'project': project, 'builder': builder, 'condition': condition,
              'original_sha256': digest(original), 'messages_sha256': digest(messages), 'started_utc': now()}
    try:
        raw = client.call(builder, messages, folder / 'call', f'library-repair:{condition}', seed=20261113)
    except (ProviderError, BudgetStop) as error:
        record.update(status='transport_incomplete', error=str(error), finished_utc=now())
        dump(target, record)
        print(project, builder, condition, record['status'], flush=True)
        return record
    dump(folder / 'output.json', {'text': raw})
    try:
        package = repaired_package(original, parse_json(raw))
        record.update(deployed='revision', validation_error=None)
    except (ValueError, KeyError, TypeError, AssertionError, TimeoutError, subprocess.TimeoutExpired) as error:
        package = original
        record.update(deployed='original_fallback', validation_error=str(error)[:3000])
    dump(folder / 'package.json', package)
    record.update(status='complete', valid_responses=1, package_sha256=digest(package), finished_utc=now())
    dump(target, record)
    print(project, builder, condition, record['deployed'], flush=True)
    return record


def verify_frozen():
    manifest = read(OUT / 'review-manifest.json')
    for path, sha in manifest['sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--resume-transport', action='store_true')
    args = parser.parse_args()
    assert not (OUT / 'grading-started.json').exists()
    freeze_inputs()
    cfg = config()
    ledger = Ledger(OUT / 'budget.sqlite3', cfg['budget_usd'], cfg['stop_new_requests_usd'])
    client = StreamingOpenRouter(cfg, ledger)
    jobs = [(p, b, c) for p in PROJECTS for b in BUILDERS for c in CONDITIONS]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda j: revise(client, *j, resume=args.resume_transport), jobs))
    dump(OUT / 'cost-checkpoint.json', totals(OUT / 'budget.sqlite3'))
    assert all(r['status'] == 'complete' for r in records), 'Missing transports: resume before scoring'
    dump(OUT / 'generation-complete.json', {'records': records, 'records_sha256': digest(records), 'finished_utc': now()})
    Ledger(OUT / 'budget.sqlite3', cfg['budget_usd'], 0)
    dump(OUT / 'cost-checkpoint.json', totals(OUT / 'budget.sqlite3'))


if __name__ == '__main__':
    main()
