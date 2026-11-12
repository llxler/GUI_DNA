"""Summarize reference-only calibration; never reads generated candidates."""
from __future__ import annotations
import hashlib
import json
from .core import ROOT, PROJECTS, dump


def main():
    old = ROOT / 'artifacts/webbench-expand-harness'
    pinned = ROOT / 'artifacts/webbench-expand-harness-157'
    sources = [old / 'calibration.json', old / 'final-reference-audit.json', old / 'bom-repeat.json',
        pinned / 'calibration.json', pinned / 'final-reference-audit.json', pinned / 'bom-repeat.json',
        pinned / 'serial-reference-audit.json']
    values = [json.loads(p.read_text()) for p in sources]
    initial_old, ref_old, repeats_old, initial, ref, repeats, serial = values

    def counts(data):
        return {project: {'n': sum(r['project'] == project for r in data['rows']),
            'passed': sum(r['score']['all_passed'] for r in data['rows'] if r['project'] == project),
            'failed_tasks': [r['task'] for r in data['rows'] if r['project'] == project and not r['score']['all_passed']]}
            for project in PROJECTS}

    selected = counts(ref)
    selected['bom'] = {'n': len(serial['rows']), 'passed': sum(r['score']['all_passed'] for r in serial['rows']),
                       'failed_tasks': [r['task'] for r in serial['rows'] if not r['score']['all_passed']]}
    result = {'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        'initial_reference': {key: {'passed': value['all_passed'], 'tests_passed': value['passed'],
            'tests_listed': value['total_listed'], 'expected_pass': value['expected_pass']} for key, value in initial.items()},
        'playwright_163_parallel_final_reference': counts(ref_old),
        'playwright_163_bom_serial_repeats': repeats_old,
        'playwright_157_parallel_final_reference': counts(ref),
        'playwright_157_bom_serial_repeats': repeats,
        'selected_runtime_final_reference': selected,
        'interpretation': 'The unchanged upstream final page passes every task file in each project under the selected execution setting. High prefix scores alone therefore cannot establish useful per-task planning. This does not prove generated libraries are behaviorally adequate.',
        'candidate_score_selection': False,
        'sensitivity_rule_fixed_before_candidate_scores': {'bom_excluded_tasks': [7, 14, 19], 'primary_keeps_all20': True}}
    dump(ROOT / 'test/results/webbench-expand-calibration.json', result)
    print(json.dumps(selected, indent=2))


if __name__ == '__main__':
    main()
