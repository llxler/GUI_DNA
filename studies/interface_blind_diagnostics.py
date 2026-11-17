"""Describe output/repair failures without changing any score or frozen candidate."""
from __future__ import annotations
from collections import Counter, defaultdict
import json
from pathlib import Path
from gui_dna.provider import parse_json

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'artifacts/interface-blind-final-2'


def code_shaped_root(value):
    if not isinstance(value, dict):
        return False
    return isinstance(value.get('files'), dict) or any(
        isinstance(k, str) and k.endswith(('.html', '.js', '.css')) for k in value)


def main():
    counts = defaultdict(Counter)
    flagged = []
    for path in sorted((STAGE / 'runs').rglob('record.json')):
        record = json.loads(path.read_text())
        key = (record['project'], record['builder'] or 'none', record['model'], record['method'])
        count = counts[key]
        count['candidates'] += 1
        if record['status'] != 'complete':
            count['transport_missing'] += 1
            continue
        count['complete'] += 1
        count['public_repairs'] += max(0, len(record['attempts']) - 1)
        count['no_executable'] += not bool(record['versions'])
        count['final_public_failed'] += bool(record['attempts'][-1]['feedback'])
        for attempt in record['attempts']:
            folder = path.parent / f'call-{attempt["attempt"]}'
            response = folder / 'response.json'
            # Rate-limit retries live in subdirectories; only one settled response is used.
            responses = [response] if response.exists() else list(folder.glob('http-retry-*/response.json'))
            for receipt in responses:
                data = json.loads(receipt.read_text())
                count['length_responses'] += any(c.get('finish_reason') == 'length' for c in data.get('choices', []))
        if record['method'] == 'plan' and record['versions']:
            number = record['versions'][-1].split('-')[-1]
            raw = json.loads((path.parent / f'output-{number}.json').read_text())['text']
            value = parse_json(raw)
            if code_shaped_root(value):
                count['executed_from_code_shaped_proposal'] += 1
                flagged.append({'candidate': str(path.parent.relative_to(STAGE)), 'top_level_keys': list(value),
                    'interpretation': 'File-map-shaped proposal accepted by the generated compiler; not proof that embedded code is executed.'})
    result = {'stage': str(STAGE.relative_to(ROOT)), 'groups': [
        {'project': k[0], 'builder': k[1], 'model': k[2], 'method': k[3], **v} for k, v in counts.items()],
        'code_shaped_proposals': flagged,
        'scope': 'Descriptive output diagnostics only. No score exclusions, repairs, or library changes. File-map detection is a limited syntactic flag, not a proof of language safety or causal failure attribution.'}
    (ROOT / 'test/results/interface-blind-diagnostics.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Code-shaped executed plan proposals:', len(flagged))
    print('Complete records:', sum(g.get('complete', 0) for g in result['groups']))


if __name__ == '__main__':
    main()
