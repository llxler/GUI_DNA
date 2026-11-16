"""Thirty matched generation chains, followed by an explicit scoring barrier."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import subprocess
from gui_dna.budget import Ledger, BudgetStop
from gui_dna.provider import parse_json, ProviderError
from test.streaming_provider_v2 import StreamingOpenRouter
from .core import *
from .browser import public_feedback


def one(client, job):
    folder = ROOT / job['folder']
    assert not (folder / 'record.json').exists(), 'Preserve previous attempt chain'
    package = read(package_path(job['project'], job['builder'])) if job['builder'] else None
    thread = messages(job['project'], job['method'], package)
    dump(folder / 'messages.json', thread)
    record = {**job, 'attempts': [], 'versions': [], 'status': 'in_progress'}
    dump(folder / 'record.json', record)
    for attempt in range(3):
        if datetime.now(timezone.utc) >= datetime.fromisoformat('2026-11-16T06:40:00+00:00'):
            record['status'] = 'time_incomplete'; break
        try:
            raw = client.call(job['model'], thread, folder / f'call-{attempt}',
                'matched-feedback-' + job['method'], seed=job['seed'])
        except (BudgetStop, ProviderError) as error:
            record.update(status='transport_or_budget_incomplete', error=str(error)); break
        dump(folder / f'output-{attempt}.json', {'text': raw})
        version = None; reports = {}
        try:
            files = validate_files(output_files(job['method'], package, parse_json(raw)))
            version = f'version-{attempt}'
            write_files(folder / version, files)
            dump(folder / version / 'source-manifest.json', {'files_sha256': {n: hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()}})
            record['versions'].append(version)
        except (ValueError, KeyError, TypeError, AttributeError, TimeoutError, subprocess.TimeoutExpired) as error:
            feedback = [{'format_or_compile': f'{type(error).__name__}: {error}'[:2400]}]
            version = None
        else:
            # Runner failures stop the stage; they are not model repair feedback.
            feedback, reports = public_feedback(job['project'], folder / version,
                'public/' + str(folder.relative_to(OUT / 'runs')) + '/' + version)
        record['attempts'].append({'attempt': attempt, 'version': version, 'feedback': feedback,
            'public_passes': sum(r['all_passed'] for r in reports.values()), 'public_total': len(PUBLIC)})
        dump(folder / 'record.json', record)
        if not feedback:
            break
        thread += [{'role': 'assistant', 'content': raw}, {'role': 'user', 'content':
            'Public format/compiler/behavior feedback:\n' + json.dumps(feedback, ensure_ascii=False) + '\nReturn the complete corrected JSON output.'}]
    if record['status'] == 'in_progress':
        record['status'] = 'complete'
    dump(folder / 'record.json', record)
    print(job['project'], job['builder'] or 'none', job['seed'], job['method'], record['status'],
        'responses', len(record['attempts']), flush=True)
    return record


def main():
    verify()
    assert not (OUT / 'generation-started.json').exists()
    plan = read(ROOT / 'artifacts/review-20261116/budget-plan.json')
    assert plan['stages'][OUT.name] == {'cap': 4., 'stop': 3.7}
    cfg = configuration(); ledger = Ledger(OUT / 'budget.sqlite3', 4., 3.7)
    client = StreamingOpenRouter(cfg, ledger)
    dump(OUT / 'generation-started.json', {'started_utc': now(), 'snapshot_sha256': sha(OUT / 'snapshot.json')})
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            records = list(pool.map(lambda j: one(client, j), jobs()))
    finally:
        # Tighten, never reopen, even when a request or browser runner fails.
        Ledger(OUT / 'budget.sqlite3', 4., 0.)
    assert all(r['status'] == 'complete' for r in records), 'Incomplete chain: do not grade held-out tests'
    paths = [p for p in (OUT / 'runs').rglob('*') if p.is_file()]
    dump(OUT / 'candidate-snapshot.json', {'finished_utc': now(), 'sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths}})
    dump(OUT / 'generation-complete.json', {'finished_utc': now(), 'candidates': len(records),
        'records_sha256': digest(records), 'candidate_snapshot_sha256': sha(OUT / 'candidate-snapshot.json')})


if __name__ == '__main__':
    main()
