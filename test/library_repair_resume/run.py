"""Resume only missing responses without changing any original experiment files."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import shutil
import subprocess

from gui_dna.budget import Ledger, BudgetStop
from gui_dna.provider import ProviderError, parse_json
from test.ledger_read import totals
from test.review_stage import freeze
from test.streaming_provider_v2 import StreamingOpenRouter
from test.library_repair.core import (ROOT, OUT as OLD, PROJECTS, BUILDERS, CONDITIONS,
    config, read, dump, digest, slug, messages_for, original_package, repaired_package)
from test.library_repair.run import now, verify_frozen

HERE = ROOT / 'test/library_repair_resume'
OUT = ROOT / 'artifacts/library-repair-resume-20261114'


def cfg():
    return {**config(), 'budget_usd': 8., 'stop_new_requests_usd': 7.5}


def folder(project, builder, condition):
    return OUT / 'libraries' / project / slug(builder) / condition


def prepare():
    verify_frozen()
    assert totals(OLD / 'budget.sqlite3')['stop_usd'] == 0
    assert not (OUT / 'review-manifest.json').exists(), 'Preparation is one-time'
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OLD / 'public-inputs.json', OUT / 'public-inputs.json')
    public = read(OUT / 'public-inputs.json')
    imported, missing, files = [], [], []
    for project in PROJECTS:
        for builder in BUILDERS:
            for condition in CONDITIONS:
                source = OLD / 'libraries' / project / slug(builder) / condition
                target = folder(project, builder, condition)
                expected = messages_for(project, builder, condition, public[project][builder])
                assert read(source / 'messages.json') == expected
                row = {'project': project, 'builder': builder, 'condition': condition,
                       'source': str(source.relative_to(ROOT))}
                if read(source / 'record.json')['status'] == 'complete':
                    shutil.copytree(source, target)
                    imported.append(row)
                    files.extend(p for p in target.rglob('*') if p.is_file())
                else:
                    target.mkdir(parents=True)
                    shutil.copy2(source / 'messages.json', target / 'messages.json')
                    missing.append(row)
                files.append(target / 'messages.json')
    assert len(imported) == len(missing) == 6
    dump(OUT / 'continuation.json', {'created_utc': now(), 'imported': imported, 'missing': missing,
        'prior_subset_scored': True, 'old_ledger': str((OLD / 'budget.sqlite3').relative_to(ROOT)),
        'new_authorization_usd': 20, 'stage_cap_usd': 8, 'unallocated_usd': 12})
    files += [OUT / 'continuation.json', OUT / 'public-inputs.json', HERE / 'run.py', HERE / 'PROTOCOL.md']
    files += [ROOT / p for p in read(OLD / 'review-manifest.json')['sha256']]
    freeze(OUT, cfg(), sorted({str(p.relative_to(ROOT)) for p in files}),
           {'scope': 'Six missing responses only; previously scored three-pair subset disclosed',
            'normal_proxy_only': True, 'first_request': 'table/Sonnet/review', 'workers_after_first': 2})
    Ledger(OUT / 'budget.sqlite3', 8, 7.5)
    print('Frozen six imported responses and six missing prompts', flush=True)


def verify():
    verify_frozen()
    for path, sha in read(OUT / 'review-manifest.json')['sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path


def one(client, job):
    project, builder, condition = [job[k] for k in ('project', 'builder', 'condition')]
    target = folder(project, builder, condition)
    if (target / 'record.json').exists():
        return read(target / 'record.json')
    messages = read(target / 'messages.json')
    assert messages == messages_for(project, builder, condition, read(OUT / 'public-inputs.json')[project][builder])
    original = original_package(project, builder)
    record = {'project': project, 'builder': builder, 'condition': condition,
              'original_sha256': digest(original), 'messages_sha256': digest(messages), 'started_utc': now()}
    try:
        raw = client.call(builder, messages, target / 'call', f'library-repair:{condition}', seed=20261113)
    except (ProviderError, BudgetStop) as error:
        record.update(status='transport_incomplete', error=str(error), finished_utc=now())
        dump(target / 'record.json', record)
        print(project, builder, condition, record['status'], flush=True)
        return record
    dump(target / 'output.json', {'text': raw})
    try:
        package = repaired_package(original, parse_json(raw))
        record.update(deployed='revision', validation_error=None)
    except (ValueError, KeyError, TypeError, AssertionError, TimeoutError, subprocess.TimeoutExpired) as error:
        package = original
        record.update(deployed='original_fallback', validation_error=str(error)[:3000])
    dump(target / 'package.json', package)
    record.update(status='complete', valid_responses=1, package_sha256=digest(package), finished_utc=now())
    dump(target / 'record.json', record)
    print(project, builder, condition, record['deployed'], flush=True)
    return record


def generate():
    verify()
    assert not (OUT / 'generation-stopped.json').exists()
    client = StreamingOpenRouter(cfg(), Ledger(OUT / 'budget.sqlite3', 8, 7.5))
    jobs = read(OUT / 'continuation.json')['missing']
    assert (jobs[0]['project'], jobs[0]['condition']) == ('table', 'review')
    first = one(client, jobs[0])
    if first['status'] == 'complete':
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda job: one(client, job), jobs[1:]))
    records = [read(folder(p, b, c) / 'record.json') if (folder(p, b, c) / 'record.json').exists()
               else {'project': p, 'builder': b, 'condition': c, 'status': 'not_requested'}
               for p in PROJECTS for b in BUILDERS for c in CONDITIONS]
    if all(r['status'] == 'complete' for r in records):
        dump(OUT / 'generation-complete.json', {'records': records, 'records_sha256': digest(records), 'finished_utc': now()})
    Ledger(OUT / 'budget.sqlite3', 8, 0)
    dump(OUT / 'generation-stopped.json', {'finished_utc': now(), 'complete': all(r['status'] == 'complete' for r in records)})
    dump(OUT / 'cost-checkpoint.json', totals(OUT / 'budget.sqlite3'))
    print('complete responses', sum(r['status'] == 'complete' for r in records), '/12', totals(OUT / 'budget.sqlite3'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'generate'])
    {'prepare': prepare, 'generate': generate}[parser.parse_args().phase]()
