"""Reconstruct the finite population and raw initial-file observations."""
from collections import Counter
import itertools
from pathlib import Path
import re

from test.history_replay.run import ROOT, read, dump, sha, digest, cases_by_file

OUT = ROOT / 'artifacts/finite-schema-audit-20261115'


def verify_report_hash(path, original_sha256):
    actual = sha(path)
    if actual == original_sha256:
        return
    manifest = ROOT / 'REPLAY-MANIFEST.json'
    assert manifest.exists(), 'Original report bytes changed without an export mapping'
    mapping = read(manifest)[str(path.relative_to(ROOT))]
    assert mapping['original_sha256'] == original_sha256
    assert mapping['exported_sha256'] == actual


def reconstruct():
    inputs = read(OUT / 'inputs.json')
    complete = read(OUT / 'evaluation-complete.json')
    assert complete['inputs_sha256'] == digest(inputs)
    schema = read(ROOT / inputs['package'])['plan_schema']
    assert schema['required'] == [] and schema['additionalProperties'] is False
    domains = {k: [None, *([False, True] if s['type'] == 'boolean' else s['enum'])]
               for k, s in schema['properties'].items()}
    population = [{k: v for k, v in zip(domains, values) if v is not None}
                  for values in itertools.product(*domains.values())]
    assert [row['plan'] for row in inputs['rows']] == population
    assert len({digest(p) for p in population}) == len(population) == 1215
    outcomes, first_failures, division_zero_errors = {}, Counter(), 0
    for key, job in inputs['jobs'].items():
        report = OUT / 'scores' / key / 'report.json'
        saved = read(OUT / 'scores' / key / 'score.json')
        verify_report_hash(report, saved['report_sha256'])
        raw = read(report)
        assert not [e for e in raw.get('errors', []) if 'maximum allowed failures' not in e.get('message', '')]
        cases = cases_by_file(raw)
        assert set(cases) == {'init'}
        passed = bool(cases['init']) and all(c['passed'] for c in cases['init'])
        failures = [c for c in cases['init'] if any(s in ('failed', 'timedOut') for s in c['statuses'])]
        assert passed or failures
        assert saved['all_passed'] == passed
        outcomes[key] = passed
        if failures: first_failures[failures[0]['title']] += 1
        stack = list(raw.get('suites', []))
        observed_division_error = False
        while stack:
            suite = stack.pop(); stack += suite.get('suites', [])
            for spec in suite.get('specs', []):
                if spec['title'] != 'Error handling - division by zero': continue
                for test in spec.get('tests', []):
                    for attempt in test.get('results', []):
                        message = re.sub(r'\x1b\[[0-9;]*m', '', attempt.get('error', {}).get('message', ''))
                        observed_division_error |= attempt['status'] == 'failed' and 'Expected: "Infinity"' in message and 'Received: "Error"' in message
        division_zero_errors += observed_division_error
    assert set(outcomes) == {r['score_key'] for r in inputs['rows']}
    calibration = {}
    for name, expected in [('reference', True), ('blank', False)]:
        report = OUT / 'calibration' / name / 'report.json'
        saved = read(OUT / 'calibration' / name / 'score.json')
        verify_report_hash(report, saved['report_sha256'])
        cases = cases_by_file(read(report))
        observed = bool(cases.get('init')) and all(c['passed'] for c in cases['init'])
        assert observed == expected == saved['all_passed']
        calibration[name] = observed
    history = read(ROOT / 'test/results/history-replay.json')
    affected = [r for r in history['rows'] if r['cohort'] == 'expansion' and r['project'] == 'calculator'
                and r['builder'] == 'openai/gpt-5' and r['method'] == 'plan' and r['label'] == 'final']
    assert len(affected) == 40 and not any(r['history_passed'] for r in affected)
    history_jobs = read(ROOT / 'artifacts/history-replay-20261115/inputs.json')['jobs']
    enumerated_sources = {digest(j['files']) for j in inputs['jobs'].values()}
    assert all(digest(history_jobs[r['score_key']]['files']) in enumerated_sources for r in affected)
    necessary_condition_exhausted = not any(outcomes.values())
    return {'posthoc': True, 'library': 'calculator/openai/gpt-5', 'schema_domains_including_omission': domains,
            'configurations': len(population), 'unique_complete_sources': len(outcomes),
            'init_passed_configurations': sum(outcomes[r['score_key']] for r in inputs['rows']),
            'init_passed_sources': sum(outcomes.values()), 'first_failure_titles': dict(sorted(first_failures.items())),
            'division_zero_error_instead_of_infinity_sources': division_zero_errors,
            'raw_browser_reports': len(outcomes) + len(calibration), 'calibration': calibration,
            'affected_original_final_plan_records': len(affected),
            'original_final_plan_sources_matched_to_population': len(affected),
            'init_necessary_condition_failed_for_entire_enumerated_population': necessary_condition_exhausted,
            'scope': 'All semantic configurations of this one frozen finite schema, including optional-field omission. Official init includes layout and basic calculations and is necessary for full history. Zero success is an executable bounded audit, not a formal proof, a current-task impossibility result or a statement about the other five libraries. Same source is scored once; all raw failures retained.'}


if __name__ == '__main__':
    result = reconstruct()
    dump(ROOT / 'test/results/finite-schema-audit.json', result)
    print({k: result[k] for k in ('configurations', 'unique_complete_sources', 'init_passed_configurations', 'raw_browser_reports')})
