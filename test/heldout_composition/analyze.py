"""Audit saved inputs/outputs and summarize the synthetic diagnostic separately."""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from gui_dna.provider import parse_json
from test.interface_blind.core import ROOT, digest, dump, slug
from test.ledger_read import totals
from test.webbench_expand.analyze import used_response
from .core import BUILDERS, PLANNERS, STRONG, builder_messages, messages_for, output_files
from .domain import PROJECTS, heldout, strong_tasks
from .fixtures import cases
from .run import feedback_message


def stage_costs(stage):
    ledgers = [stage / 'budget.sqlite3']
    continuation = stage / 'continuation.json'
    if continuation.exists():
        ledgers += [ROOT / path for path in json.loads(continuation.read_text())['source_ledgers']]
    return {str(p.relative_to(ROOT)): totals(p) for p in dict.fromkeys(ledgers)}


def audit_record(folder, record, initial, package, build=False):
    assert json.loads((folder / 'messages.json').read_text()) == initial
    messages = list(initial)
    usage, providers, finishes = Counter(), Counter(), Counter()
    for attempt in record['attempts']:
        index = attempt['attempt']
        response = used_response(folder, index)
        matching = [p for p in (folder / f'call-{index}').rglob('response.json') if json.loads(p.read_text()) == response]
        assert len(matching) == 1
        request = json.loads(matching[0].with_name('request.json').read_text())
        assert request['body']['messages'] == messages
        assert request['body']['max_tokens'] == (20000 if build else 6000)
        raw = json.loads((folder / f'output-{index}.json').read_text())['text']
        assert raw == response['choices'][0]['message']['content']
        providers[response.get('provider', 'unknown')] += 1
        finishes[response['choices'][0]['finish_reason']] += 1
        for key in ('prompt_tokens', 'completion_tokens', 'cost'):
            usage[key] += response['usage'].get(key, 0)
        usage['reasoning_tokens'] += response['usage'].get('completion_tokens_details', {}).get('reasoning_tokens', 0)
        messages += [{'role': 'assistant', 'content': raw},
                     {'role': 'user', 'content': feedback_message(build, attempt['feedback'])}]
    differences = []
    for version in record.get('versions', []):
        page = folder / version
        source = json.loads((page / 'source-manifest.json').read_text())
        assert all(hashlib.sha256((page / n).read_bytes()).hexdigest() == h for n, h in source['files_sha256'].items())
        index = version.removeprefix('version-')
        raw = json.loads((folder / f'output-{index}.json').read_text())['text']
        if digest(output_files(record['method'], package, parse_json(raw))) != source['output_sha256']:
            differences.append(str(page.relative_to(ROOT)))
    return usage, providers, finishes, differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-build')
    parser.add_argument('--main-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-run')
    parser.add_argument('--strong-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-strong')
    parser.add_argument('--controls', type=Path, default=ROOT / 'artifacts/heldout-composition-controls')
    args = parser.parse_args()
    build, main_stage, strong = [p.resolve() for p in (args.build_stage, args.main_stage, args.strong_stage)]
    control = json.loads((args.controls / 'results.json').read_text())['rows']
    assert len(control) == 364
    for row in control:
        path = ROOT / row['report_path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['report_sha256']
        assert json.loads(path.read_text())['all_passed'] == row['passed']
    libraries, packages, usage, providers, finishes, differences = [], {}, Counter(), Counter(), Counter(), []
    build_records = []
    matched = 0
    for stage in (build, main_stage, strong):
        manifest = json.loads((stage / 'review-manifest.json').read_text())
        for name, sha in manifest['sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    for project in PROJECTS:
        for builder in BUILDERS:
            folder = build / 'libraries' / project / slug(builder)
            record = json.loads((folder / 'record.json').read_text())
            build_records.append(record)
            package = json.loads((folder / 'package.json').read_text()) if record['status'] != 'failed' else None
            u, p, f, d = audit_record(folder, record, builder_messages(project), None, True)
            for key, value in u.items():
                usage['build/' + key] += value
            providers.update(p)
            finishes.update(f)
            item = {'project': project, 'builder': builder, 'status': record['status'], 'attempts': len(record['attempts']),
                    'development_passes': record.get('development_passes', 0), 'development_total': 5}
            if package:
                assert digest(package) == record['package_sha256']
                assert parse_json(json.loads((folder / f'output-{record["selected_attempt"]}.json').read_text())['text']) == package
                reports = [json.loads((folder / f'validation-{record["selected_attempt"]}' / f'dev-{i}' / 'public-report.json').read_text()) for i in range(5)]
                assert sum(r['all_passed'] for r in reports) == record['development_passes']
                packages[project, builder] = package
                item.update(package_sha256=digest(package), files=len(package['files']),
                            file_bytes=sum(len(s.encode()) for s in package['files'].values()),
                            compiler_bytes=len(package['compiler'].encode()), schema_properties=list(package['plan_schema']['properties']),
                            selected_attempt=record['selected_attempt'])
            libraries.append(item)
    assert digest(build_records) == json.loads((build / 'build-complete.json').read_text())['records_sha256']
    cohorts = {}
    for stage, models, task_fn, expected, label in ((main_stage, PLANNERS, heldout, 220, 'main'),
                                                 (strong, (STRONG,), strong_tasks, 24, 'strong')):
        rows, lookup = [], {}
        barrier = json.loads((stage / 'generation-complete.json').read_text())
        snapshot = json.loads((stage / 'candidate-files-sha256.json').read_text())
        assert snapshot['generation_sha256'] == hashlib.sha256((stage / 'generation-complete.json').read_bytes()).hexdigest()
        for name, sha in snapshot['files'].items():
            assert hashlib.sha256((stage / name).read_bytes()).hexdigest() == sha
        records = {}
        for path in sorted((stage / 'runs').rglob('record.json')):
            record = json.loads(path.read_text())
            records[str(path.parent.relative_to(stage))] = digest(record)
            assert record['status'] == 'complete'
            task = next(t for t in heldout(record['project']) if t['id'] == record['task'])
            package = packages.get((record['project'], record['builder']))
            if not record.get('unavailable_library'):
                initial = messages_for(record['project'], task, record['method'], package)
                u, p, f, d = audit_record(path.parent, record, initial, package)
                for key, value in u.items():
                    usage[label + '/' + record['method'] + '/' + key] += value
                providers.update(p)
                finishes.update(f)
                differences.extend(d)
                if record['method'] == 'plan':
                    other = path.parent.parent.parent / 'free_lib' / record['task'] / 'messages.json'
                    assert json.loads(other.read_text())[1] == initial[1]
                    matched += 1
            hidden = json.loads(path.with_name('hidden.json').read_text())
            expected_cases = cases(record['project'], task['policy'])
            assert hidden['cases_sha256'] == digest(expected_cases)
            for key, version in (('first', record['versions'][0] if record['versions'] else None),
                                 ('final', record['versions'][-1] if record['versions'] else None)):
                score = hidden[key]
                if version:
                    report = path.parent / version / 'hidden-report.json'
                    assert hashlib.sha256(report.read_bytes()).hexdigest() == score['report_sha256']
                    raw = json.loads(report.read_text())
                    assert raw['cases_total'] == len(expected_cases)
                    if raw['all_passed']:
                        assert raw['checked_steps'] == sum(len(c['steps']) + 1 for c in expected_cases)
                    assert score['all_passed'] == (raw['cases_passed'] == raw['cases_total'])
                    assert score['all_passed'] == raw['all_passed'] and (not raw['all_passed'] or not raw['failures'])
                else:
                    assert score['all_passed'] is False
            row = {k: record[k] for k in ('project', 'builder', 'model', 'method', 'task')}
            row.update(first=bool(hidden['first']['all_passed']), final=bool(hidden['final']['all_passed']),
                       attempts=len(record['attempts']), versions=len(record['versions']), unavailable_library=record.get('unavailable_library', False))
            rows.append(row)
            lookup[record['project'], record['builder'], record['model'], record['method'], record['task']] = row
        assert len(rows) == expected and records == barrier['records_by_path_sha256']
        groups = []
        for project in PROJECTS:
            for builder in BUILDERS:
                for model in models:
                    pairs = []
                    for task in task_fn(project):
                        item = {'task': task['id']}
                        for method in (('free', 'free_lib', 'plan') if label == 'main' else ('free_lib', 'plan')):
                            item[method] = lookup[project, None if method == 'free' else builder, model, method, task['id']]['final']
                        selected = [r for r in control if r['project'] == project and r['builder'] == builder and r['task'] == task['id']]
                        for name in [f'dev-{i}' for i in range(5)] + ['delta']:
                            item[name] = next(r['passed'] for r in selected if r['control'] == name)
                        item['fixed_final'] = next(r['passed'] for r in selected if r['control'] == 'fixed-final' and r['model'] == model)
                        pairs.append(item)
                    names = [name for name in pairs[0] if name != 'task']
                    g = {'project': project, 'builder': builder, 'model': model, 'n': len(pairs),
                         **{name: sum(row[name] for row in pairs) for name in names}}
                    for against in ('free_lib', 'delta', 'fixed_final'):
                        g['vs_' + against] = {'wins': sum(r['plan'] and not r[against] for r in pairs),
                                             'losses': sum(r[against] and not r['plan'] for r in pairs),
                                             'ties': sum(r['plan'] == r[against] for r in pairs)}
                    groups.append(g)
        cohorts[label] = {'rows': rows, 'groups': groups, 'distinct_candidates': len(rows),
                          'method_totals': {method: {'n': sum(r['method'] == method for r in rows),
                                                     'first': sum(r['first'] for r in rows if r['method'] == method),
                                                     'final': sum(r['final'] for r in rows if r['method'] == method)}
                                            for method in sorted({r['method'] for r in rows})}}
    cost = {kind: stage_costs(stage) for kind, stage in (('build', build), ('main', main_stage), ('strong', strong))}
    all_ledgers = {name: value for group in cost.values() for name, value in group.items()}
    result = {'scope': 'Synthetic Web-Bench-inspired policy composition; human-authored behavior axes and DOM contract, model-proposed interface. Not official benchmark scores, broad project transfer, or evidence that LLM planning is necessary.',
              'stages': {'build': str(build.relative_to(ROOT)), 'main': str(main_stage.relative_to(ROOT)), 'strong': str(strong.relative_to(ROOT)),
                         'controls': str(args.controls.resolve().relative_to(ROOT))},
              'libraries': libraries, 'cohorts': cohorts, 'fixed_control_rows': control,
              'usage': dict(usage), 'providers': dict(providers), 'finishes': dict(finishes),
              'costs': cost, 'total_cost': {key: round(sum(row[key] for row in all_ledgers.values()), 6) for key in ('settled_usd', 'exposure_usd')},
              'audit': {'all_saved_hashes_verified': True, 'matched_library_inputs': matched, 'candidate_records': 244,
                        'fixed_control_scores': len(control), 'regeneration_differences': differences}}
    dump(ROOT / 'test/results/heldout-composition.json', result)
    lines = ['# 自建库与未见行为组合（合成诊断）', '', result['scope'], '']
    for label, cohort in cohorts.items():
        lines += ['## ' + label, '', '| 应用 | 建库者 | 规划者 | 同库代码 | 方案 | 无模型差分 | 固定最终页 | 方案对代码W/L |', '|---|---|---|---:|---:|---:|---:|---|']
        for g in cohort['groups']:
            q = g['vs_free_lib']
            lines.append(f"| {g['project']} | {g['builder']} | {g['model']} | {g['free_lib']}/{g['n']} | {g['plan']}/{g['n']} | {g['delta']}/{g['n']} | {g['fixed_final']}/{g['n']} | {q['wins']}/{q['losses']} |")
        lines += ['', json.dumps(cohort['method_totals']), '']
    (ROOT / 'test/results/heldout-composition.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
