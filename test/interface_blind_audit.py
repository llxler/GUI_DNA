"""Audit original frozen inputs and saved request boundaries without API calls.

Run on the original workspace. Anonymous exports intentionally have different
source hashes and use REPLAY-MANIFEST.json instead of these historical hashes.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from test.interface_blind.core import ROOT, dump
from test.behavior_feedback import SOURCE_FRAME


def read(path):
    return json.loads(Path(path).read_text())


def main():
    manifests = sorted((ROOT / 'artifacts').glob('interface-blind*/review-manifest.json'))
    manifests.append(ROOT / 'artifacts/behavior-feedback/review-manifest.json')
    frozen = 0
    for manifest in manifests:
        for name, expected in read(manifest)['sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, (manifest, name)
            frozen += 1
    base = ROOT / 'artifacts/interface-blind-final-2'
    records = sorted((base / 'runs').rglob('record.json'))
    assert len(records) == 400
    reasons, providers = Counter(), Counter()
    matched = 0
    for path in records:
        record = read(path)
        assert record['status'] == 'complete', path
        assert path.with_name('hidden.json').exists(), path
        for attempt in record['attempts']:
            number = attempt['attempt']
            raw = read(path.parent / f'output-{number}.json')['text']
            responses = [read(p) for p in (path.parent / f'call-{number}').rglob('response.json')]
            used = [r for r in responses if r.get('choices') and r['choices'][0]['message']['content'] == raw]
            assert len(used) == 1, (path, number, len(used))
            response = used[0]
            reasons.update(c['finish_reason'] for c in response['choices'])
            providers[response['provider']] += 1
        if record['method'] == 'plan':
            other = path.parent.parent.parent / 'free_lib' / record['task'] / 'messages.json'
            first = [m for m in read(path.with_name('messages.json')) if m['role'] == 'user']
            second = [m for m in read(other) if m['role'] == 'user']
            assert first == second, path
            matched += 1
    assert matched == 160
    assert set(reasons) == {'stop'}, reasons
    behavior = ROOT / 'artifacts/behavior-feedback'
    assert (behavior / 'generation-complete.json').exists(), 'Finish public repairs first'
    recovery = read(behavior / 'resume-serialization.json') if (behavior / 'resume-serialization.json').exists() else None
    if recovery:
        assert hashlib.sha256((ROOT / recovery['adapter']).read_bytes()).hexdigest() == recovery['adapter_sha256']
        assert hashlib.sha256((behavior / 'review-manifest.json').read_bytes()).hexdigest() == recovery['original_manifest_sha256']
    split = read(ROOT / 'test/results/behavior-feedback-split.json')['projects']
    feedback_count = 0
    marker = 'This separate repair protocol provides public behavior tests. Their observed feedback is:\n'
    for request in (behavior / 'runs').rglob('request.json'):
        relative = request.relative_to(behavior / 'runs')
        project, task = relative.parts[0], relative.parts[4]
        allowed = {(x['line'], x['title']) for x in split[project][task]['public']}
        for message in read(request)['body']['messages']:
            content = message['content']
            if message['role'] != 'user' or not content.startswith(marker):
                continue
            feedback = content[len(marker):].split('\nRepair these behaviors', 1)[0]
            # Compiler diagnostics are plain strings, not test reports.
            if not feedback.startswith('{'):
                continue
            value = json.loads(feedback)
            if 'tests' not in value:
                continue
            assert {(x['line'], x['title']) for x in value['tests']} <= allowed, request
            for case in value['tests']:
                for error in case['errors']:
                    assert not any(SOURCE_FRAME.match(line) or line.lstrip().startswith('at ') for line in error.splitlines()), request
                    assert '/home/' not in error, request
            feedback_count += 1
    rows = [read(p) for p in (behavior / 'runs').rglob('record.json')]
    assert len(rows) == 80
    result = {'frozen_manifests': len(manifests), 'frozen_hash_entries': frozen,
              'primary_candidates': len(records), 'matched_user_messages': matched,
              'primary_used_response_finish_reasons': dict(reasons), 'primary_response_providers': dict(providers),
              'serialization_recovery_verified': bool(recovery), 'behavior_candidates': len(rows), 'behavior_status': dict(Counter(r['status'] for r in rows)),
              'saved_public_feedback_messages_checked': feedback_count,
              'scope': 'Original frozen bytes and saved request boundaries; no claim of behavior correctness or pretraining isolation.'}
    dump(ROOT / 'test/results/interface-blind-audit.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
