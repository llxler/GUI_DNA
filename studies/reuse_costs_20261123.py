"""Observed API spending as a library or its direct comparator serves twenty targets."""
import argparse
from collections import defaultdict
from decimal import Decimal

from studies.ledger_read import calls
from studies.study_io import ROOT, dump, read, sha

OUTPUT = ROOT / 'studies/results/reuse-costs-20261123.json'
STUDIES = {'table': 'table-library-sources', 'svg-chart': 'svg-chart-interfaces',
           'expression-editor': 'expression-editor-sources'}


def monetary(rows):
    return (sum(r['actual'] or 0 for r in rows),
            sum(r['actual'] if r['actual'] is not None else r['reserved'] for r in rows))


def units(value):
    return int(Decimal(str(value)) * 1_000_000)


def reconstruct():
    results = {}
    for project, label in STUDIES.items():
        stem = label + '-20261123'
        out = ROOT / 'artifacts' / stem
        study_path = ROOT / 'studies/results' / (stem + '.json')
        study = read(study_path)
        ledger = {r['id']: r for r in calls(out / 'budget.sqlite3')}
        seen, target, preparation = set(), defaultdict(list), defaultdict(list)
        for file in out.rglob('request.json'):
            key = file.relative_to(out).parts
            if key[0] not in {'candidates', 'runs', 'preparation'}:
                continue
            rid = read(file)['call_id']
            assert rid not in seen and rid in ledger
            seen.add(rid)
            if key[0] == 'preparation':
                preparation[key[1]].append(ledger[rid])
            else:
                target[key[1], int(key[2].removeprefix('task-'))].append(ledger[rid])
        assert seen == set(ledger)
        prep = {a: monetary(preparation[a]) for a in ('ai', 'direct', 'reference')}
        if project == 'svg-chart':
            previous = ROOT / 'artifacts/svg-chart-sources-20261121/budget.sqlite3'
            prep['ai'] = monetary([r for r in calls(previous) if r['purpose'] == 'library:svg-chart'])
        if project == 'table':
            from studies.table_library_sources.report import historical_build_cost
            history = historical_build_cost()
            prep['ai'] = (units(history['settled_usd']), units(history['exposure_usd']))

        groups = {}
        for a in ('direct', 'reference', 'ai'):
            key = 'reference_typed' if project == 'svg-chart' and a == 'reference' else a
            lo, hi = prep[a]
            series = []
            for n in range(1, 21):
                delta_lo, delta_hi = monetary(target[key, n])
                lo += delta_lo
                hi += delta_hi
                passed = (study['cells'][key][str(n)]['passed'] if project == 'svg-chart'
                          else study['targets'][f'task-{n}'][a]['after_public_repair']['passed'])
                series.append({'through_task': n, 'current_passed': passed, 'cumulative_settled_microusd': lo,
                               'cumulative_exposure_microusd': hi})
            groups[a] = {'preparation_settled_microusd': prep[a][0], 'preparation_exposure_microusd': prep[a][1],
                         'observed_current_files': sum(r['current_passed'] is not None for r in series),
                         'passed_current_files': sum(r['current_passed'] is True for r in series), 'ordered': series}
        results[project] = {'evidence_sha256': sha(study_path), 'workflows': groups}
    return {'projects': results, 'unit': 'Micro-USD per actual ledger reservation. Settled excludes unresolved calls, '
            'exposure includes them. Preparation is charged once from target 1. Target costs include allowed public repairs. '
            'Target order is the official numbering. Current-file passes are counted separately at each target. '
            'Reference workflows exclude unpriced upstream labor and local compute. Archived AI development charges are '
            'attributed to reuse and are not new charges. Alternative prose chart documentation is a separate diagnostic.'}


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--write', action='store_true')
    args = cli.parse_args()
    result = reconstruct()
    if args.write:
        if OUTPUT.exists():
            assert read(OUTPUT) == result
        dump(OUTPUT, result)
    else:
        assert read(OUTPUT) == result
    for project, data in result['projects'].items():
        print(project, [(a, x['ordered'][-1]['cumulative_settled_microusd']) for a, x in data['workflows'].items()])
