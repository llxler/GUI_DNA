"""Resume only a missing transport, retaining every completed model attempt.

The original frozen runner remains unchanged. This adapter never regenerates a
completed output or recomputes its feedback. Receipts bind the adapter and the
exact interrupted record and messages. Valid format/load failures still consume
the original three-attempt allowance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from gui_dna.budget import BudgetStop
from gui_dna.provider import ProviderError, parse_json
from test.ledger_read import calls
from .core import (ROOT, SEED, config, digest, dump, slug, compile_plan, validate_package,
                   public_check, write_files)
from .run import provider


def continuation_messages(folder, record, build):
    messages = json.loads((folder / 'messages.json').read_text())
    assert len(record['attempts']) <= 3
    for expected, attempt in enumerate(record['attempts']):
        assert attempt['attempt'] == expected and attempt['feedback']
        raw = json.loads((folder / f'output-{expected}.json').read_text())['text']
        suffix = ('\nReturn the complete corrected package as JSON. No behavioral tests were run.' if build
                  else '\nReturn the full corrected JSON output.')
        messages += [{'role': 'assistant', 'content': raw}, {'role': 'user',
                     'content': 'Public format/compiler/load feedback:\n' + '\n'.join(attempt['feedback']) + suffix}]
    return messages


def resume_one(client, out, path, build):
    folder = path.parent
    record = json.loads(path.read_text())
    assert record['status'] == 'transport_incomplete'
    messages = continuation_messages(folder, record, build)
    start = len(record['attempts'])
    assert start < 3
    lost = folder / f'call-{start}'
    # Every billed response must have been saved as a completed attempt. Refuse
    # to throw away a settled response if a later local write was interrupted.
    settled = {r['id'] for r in calls(out / 'budget.sqlite3') if r['actual'] is not None}
    for request_path in lost.rglob('request.json'):
        request = json.loads(request_path.read_text())
        assert request['body']['messages'] == messages
        assert request['call_id'] not in settled, 'Recover the settled response; do not send another request'
    batch = out / 'discarded-transport' / folder.relative_to(out)
    number = max((int(p.name) for p in batch.glob('[0-9]*')), default=0) + 1
    batch /= str(number)
    batch.mkdir(parents=True)
    shutil.copy2(path, batch / 'record.json')
    dump(batch / 'resume-receipt.json', {'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'record_sha256': digest(record), 'messages_sha256': digest(messages), 'next_attempt': start,
        'retained_completed_attempts': len(record['attempts']),
        'policy': 'Retry only incomplete transport; preserve all prior outputs and feedback exactly, same three valid attempts total.'})
    if lost.exists():
        shutil.move(str(lost), str(batch / lost.name))
    record.pop('error', None)
    record['status'] = 'failed' if build else 'complete'
    package = None
    if not build and record['builder']:
        package = json.loads((ROOT / 'artifacts/webbench-expand-build/libraries' / record['project'] / slug(record['builder']) / 'package.json').read_text())
        assert digest(package) == record['package_sha256']
    model = record['builder'] if build else record['model']
    purpose = 'library-interface-blind' if build else f'plan-interface-blind:{record["method"]}'
    for attempt in range(start, 3):
        try:
            raw = client.call(model, messages, folder / f'call-{attempt}', purpose, seed=SEED)
        except BudgetStop:
            record['status'] = 'transport_incomplete'
            dump(path, record)
            raise
        except ProviderError as error:
            record.update(status='transport_incomplete', error=str(error))
            break
        dump(folder / f'output-{attempt}.json', {'text': raw})
        try:
            parsed = parse_json(raw)
            if build:
                feedback = validate_package(parsed, folder / f'validation-{attempt}')
            else:
                method = record['method']
                files = compile_plan(package, parsed) if method == 'plan' else ({**package['files'], **parsed['files']} if method == 'free_lib' else parsed['files'])
                version = f'version-{attempt}'
                write_files(folder / version, files)
                record['versions'].append(version)
                dump(folder / version / 'source-manifest.json', {'files_sha256': {n: hashlib.sha256(v.encode()).hexdigest() for n, v in files.items()}, 'output_sha256': digest(files)})
                feedback = public_check(folder / version)
        except (ValueError, KeyError, TypeError, TimeoutError, subprocess.TimeoutExpired) as error:
            feedback = [str(error)[:1600]]
        record['attempts'].append({'attempt': attempt, 'feedback': feedback})
        if not feedback:
            if build:
                dump(folder / 'package.json', parsed)
                record.update(status='frozen', package_sha256=digest(parsed), selected_attempt=attempt)
            break
        suffix = ('\nReturn the complete corrected package as JSON. No behavioral tests were run.' if build
                  else '\nReturn the full corrected JSON output.')
        messages += [{'role': 'assistant', 'content': raw}, {'role': 'user',
                     'content': 'Public format/compiler/load feedback:\n' + '\n'.join(feedback) + suffix}]
    dump(path, record)
    print(f'resumed {folder.relative_to(out)}: {record["status"]}, total attempts={len(record["attempts"])}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['build', 'generate'])
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    build = args.phase == 'build'
    out = ROOT / ('artifacts/webbench-expand-build' if build else 'artifacts/webbench-expand-run')
    assert not (out / 'grading-started.json').exists()
    manifest = json.loads((out / 'review-manifest.json').read_text())
    assert manifest['config'] == config(build)
    for name, sha in manifest['sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    paths = [p for p in (out / ('libraries' if build else 'runs')).rglob('record.json')
             if json.loads(p.read_text())['status'] == 'transport_incomplete']
    client = provider(config(build), out)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(lambda p: resume_one(client, out, p, build), paths))
    print('Run the original phase entry again to verify its frozen inputs and write its completion barrier.', flush=True)


if __name__ == '__main__':
    main()
