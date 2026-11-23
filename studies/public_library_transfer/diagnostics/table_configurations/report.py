"""Audit per-setting browser outcomes and actual target selections for the two table libraries."""
import argparse
from fractions import Fraction

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, read, sha
from .run import OUT, PLANNERS, RESULT


def summary(settings, actual):
    passes = {r['id']: set(r['passed_tasks']) for r in settings}
    maximum = max(map(len, passes.values()))
    oracle = sorted(set.union(*passes.values()))
    expected = Fraction(sum(map(len, passes.values())), len(settings))
    first = [s['id'] for s in settings if s['first_example']]
    if len(first) != 1:
        raise ValueError('Expected exactly one public first example per library')
    cover = {}
    for planner, rows in actual.items():
        observed = {r['task'] for r in rows if r['passed']}
        covering = [i for i, targets in passes.items() if observed <= targets]
        cover[planner] = {'passed': len(observed), 'passed_tasks': sorted(observed),
                          'all_actual_passes_covered_by_one_fixed_page': bool(covering),
                          'covering_setting_ids': covering, 'actual_only_vs_first': sorted(observed - passes[first[0]]),
                          'first_only_vs_actual': sorted(passes[first[0]] - observed),
                          'discordant_replays': [r['task'] for r in rows if r['passed'] != (r['task'] in passes[r['setting']])],
                          'rows': rows}
    return {'first_example_setting': first[0], 'first_example_passed': len(passes[first[0]]),
            'best_fixed_passed': maximum, 'all_best_fixed_setting_ids': [i for i, v in passes.items() if len(v) == maximum],
            'uniform_expected_passed_of_20': float(expected), 'uniform_expected_fraction': str(expected),
            'uniform_success_probability_fraction': str(expected / 20),
            'uniform_passed_cells': sum(map(len, passes.values())), 'uniform_total_cells': 20 * len(settings),
            'oracle_passed': len(oracle), 'oracle_passed_tasks': oracle, 'deployments': cover}


def verify_row(root, row, contract_hash):
    fingerprint = digest(row['files'])
    browser.verify_page(ROOT / row['page'], row['files'], 'table')
    receipt = root / 'browser/scores/table' / f'task-{row["task"]}' / fingerprint / 'score.json'
    expected = {'project': 'table', 'task': row['task'], 'files_digest': fingerprint, 'contract_digest': contract_hash}
    value = browser.verify_receipt(root, receipt, expected)
    if any(row[k] != value[k] for k in ('report_sha256', 'report', 'passed')):
        raise ValueError(f'Official score differs from reported outcome: {receipt}')
    return {'report': str((root / row['report']).relative_to(ROOT)), 'sha256': row['report_sha256'],
            **({'reused_from': value['source_report']} if 'source_report' in value else {})}


def reconstruct():
    sealed = OUT / 'generation-sealed.json'
    seal = read(sealed)
    scores = read(OUT / 'scoring.json')
    contract_hash = digest(browser.verify_contract('table'))
    if (scores['seal_sha256'] != sha(sealed) or contract_hash != seal['contract_sha256']
            or len(seal['rows']) != len(scores['rows']) or len(scores['rows']) != 200):
        raise ValueError('Inconsistent 200-cell frozen experiment')
    for name, expected in seal['sources'].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f'Source changed after registration: {name}')
    groups = {1: {}, 2: {}}
    for original, row in zip(seal['rows'], scores['rows']):
        if any(row[k] != v for k, v in original.items()):
            raise ValueError('Scored row differs from its original frozen page')
        by_id = groups[row['rep']]
        setting = by_id.setdefault(row['setting'], {'id': row['setting'], 'configuration': row['config'],
                                      'files_digest': digest(row['files']), 'first_example': row['first_example'],
                                      'passed_tasks': [], 'official_reports': {}})
        if digest(row['files']) != setting['files_digest'] or str(row['task']) in setting['official_reports']:
            raise ValueError('Expected one unchanged fixed page per setting and a unique result per task')
        setting['official_reports'][str(row['task'])] = verify_row(OUT, row, contract_hash)
        if row['passed']:
            setting['passed_tasks'].append(row['task'])
    libraries = []
    for rep, by_id in groups.items():
        settings = list(by_id.values())
        by_files = {v['files_digest']: v for v in settings}
        if len(by_files) != (2 if rep == 1 else 8) or any(len(s['official_reports']) != 20 for s in settings):
            raise ValueError('Incomplete or duplicate fixed settings')
        selected = {}
        for planner, root in PLANNERS.items():
            projected = read(root / 'browser/project-scores/table.json')
            if projected['generation_sha256'] != sha(root / 'project-seals/table.json'):
                raise ValueError('Original deployment results differ from their freeze')
            rows = [r for r in projected['rows'] if r['arm'] == 'plan' and r['rep'] == rep
                    and r['builder'] == 'gpt-6.2-astra' and r['planner'] == planner]
            if sorted(r['task'] for r in rows) != list(browser.TASKS) or any(r['status'] != 'valid' for r in rows):
                raise ValueError('Actual target deployment failed to provide the complete observed target set')
            selected[planner] = []
            for row in sorted(rows, key=lambda r: r['task']):
                match = by_files[digest(row['files'])]
                selected[planner].append({'task': row['task'], 'setting': match['id'], 'passed': row['passed'],
                                          'official_report': verify_row(root, row, contract_hash)})
        libraries.append({'rep': rep, 'builder': 'gpt-6.2-astra', 'configurations': settings, **summary(settings, selected)})
    return {'project': 'table', 'post_hoc': True, 'model_calls': 0, 'tasks': list(browser.TASKS),
            'planned_cells': len(scores['rows']), 'seal': str(sealed.relative_to(ROOT)), 'seal_sha256': sha(sealed),
            'scoring': str((OUT / 'scoring.json').relative_to(ROOT)), 'scoring_sha256': sha(OUT / 'scoring.json'),
            'libraries': libraries}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    result = reconstruct()
    if args.write:
        core.save(RESULT, result)
    if result != read(RESULT):
        raise SystemExit('Published enumeration differs from original reports')
    for lib in result['libraries']:
        print(lib['rep'], lib['first_example_passed'], lib['best_fixed_passed'], lib['uniform_expected_fraction'], lib['oracle_passed'])
