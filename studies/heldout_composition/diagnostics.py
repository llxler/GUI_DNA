"""Describe saved failures and repair attempts without another model/browser call."""
from collections import Counter
import json
from pathlib import Path

from gui_dna.provider import parse_json

ROOT = Path(__file__).resolve().parents[2]


def main():
    summary = json.loads((ROOT / 'test/results/heldout-composition.json').read_text())
    failures, groups, versions = [], {}, Counter()
    for label in ('main', 'strong'):
        stage = ROOT / summary['stages'][label]
        counts, forms, feedback = Counter(), Counter(), Counter()
        for path in sorted((stage / 'runs').rglob('record.json')):
            record = json.loads(path.read_text())
            method = record['method']
            counts[method + '/candidates'] += 1
            counts[method + '/extra_attempts'] += max(0, len(record['attempts']) - 1)
            counts[method + '/repaired_candidates'] += len(record['attempts']) > 1
            counts[method + '/without_executable'] += not bool(record['versions'])
            hidden = json.loads(path.with_name('hidden.json').read_text())
            counts[method + '/first_response_passes'] += bool(record['versions'] and record['versions'][0] == 'version-0' and hidden['first']['all_passed'])
            for attempt in record['attempts']:
                feedback.update(attempt['feedback'])
            for v in record['versions']:
                report = path.parent / v / 'hidden-report.json'
                if report.exists():
                    versions[json.loads(report.read_text())['browser_version']] += 1
            if record['versions'] and method == 'free_lib':
                index = record['versions'][-1].removeprefix('version-')
                output = parse_json(json.loads((path.parent / f'output-{index}.json').read_text())['text'])
                forms['program' if 'program' in output else 'files'] += 1
            if hidden['final']['all_passed']:
                continue
            report = json.loads((path.parent / record['versions'][-1] / 'hidden-report.json').read_text())
            first = report['failures'][0]
            expected, actual = first.get('expected', {}), first.get('actual', {})
            changed = sorted(k for k in expected if expected[k] != actual.get(k))
            action = first.get('action', [None])[0]
            category = {('edit', ('clipboard',)): 'clipboard_live_reference',
                        ('sort', ('selected',)): 'selection_after_sort',
                        ('delete', ('selected',)): 'selection_after_delete'}.get((action, tuple(changed)), 'other')
            failures.append({'cohort': label, 'record': str(path.relative_to(ROOT)),
                             'model': record['model'], 'project': record['project'], 'task': record['task'],
                             'method': method, 'first_failure_category': category,
                             'first_failure': first, 'failure_count': len(report['failures'])})
        groups[label] = {'attempts': dict(counts), 'final_free_lib_output_forms': dict(forms), 'public_feedback': dict(feedback)}
    result = {'cohorts': groups, 'final_failures': failures,
              'first_failure_counts': dict(Counter(f['first_failure_category'] for f in failures)),
              'scored_version_browser_counts': dict(versions),
              'scope': 'First failing observation per candidate, not an exhaustive causal attribution. Existing scores only.'}
    (ROOT / 'test/results/heldout-composition-diagnostics.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'final_failures'}, indent=2))


if __name__ == '__main__':
    main()
