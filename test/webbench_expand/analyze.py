"""Read saved records and scores, preserving project/model/library strata."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from gui_dna.provider import parse_json
from .core import ROOT, PROJECTS, BUILDERS, PLANNERS, dump, digest, slug
from test.ledger_read import totals

BUILD = ROOT / 'artifacts/webbench-expand-build'
BASE = ROOT / 'artifacts/webbench-expand-run'
CONTROLS = ROOT / 'artifacts/webbench-expand-controls'


def used_response(folder, attempt):
    responses = [json.loads(p.read_text()) for p in (folder / f'call-{attempt}').rglob('response.json')]
    responses = [r for r in responses if r.get('choices') and r['choices'][0].get('finish_reason') not in (None, 'error') and r.get('usage', {}).get('cost') is not None]
    assert len(responses) == 1, (folder, attempt, len(responses))
    return responses[0]


def main():
    rows, lookup, providers, finishes = [], {}, Counter(), Counter()
    used_cost, tokens, code_forms = Counter(), Counter(), Counter()
    records = []
    for path in sorted((BASE / 'runs').rglob('record.json')):
        record = json.loads(path.read_text())
        assert record['status'] == 'complete'
        records.append(record)
        hidden = json.loads(path.with_name('hidden.json').read_text())
        row = {k: record[k] for k in ('project', 'builder', 'model', 'method', 'task')}
        row.update(first=bool(hidden['first']['all_passed']), final=bool(hidden['final']['all_passed']),
                   attempts=len(record['attempts']), executable_versions=len(record['versions']),
                   final_public_ok=bool(record['attempts'] and not record['attempts'][-1]['feedback']))
        rows.append(row)
        if record['method'] == 'free_lib' and record['versions']:
            index = record['versions'][-1].removeprefix('version-')
            parsed = parse_json(json.loads((path.parent / f'output-{index}.json').read_text())['text'])
            form = 'program' if 'program' in parsed else 'files'
            row['code_output_form'] = form
            code_forms[record['model'] + '/' + form] += 1
        lookup[tuple(row[k] for k in ('project', 'builder', 'model', 'method', 'task'))] = row
        for attempt in record['attempts']:
            response = used_response(path.parent, attempt['attempt'])
            providers[record['model'] + '/' + response.get('provider', 'unknown')] += 1
            finishes[response['choices'][0]['finish_reason']] += 1
            used_cost[record['method']] += response['usage']['cost']
            tokens[record['method'] + '/prompt'] += response['usage'].get('prompt_tokens', 0)
            tokens[record['method'] + '/completion'] += response['usage'].get('completion_tokens', 0)
    barrier = json.loads((BASE / 'generation-complete.json').read_text())
    assert len(rows) == barrier['candidates'] and barrier['transport_incomplete'] == 0
    # The generation barrier uses job order, which differs from lexicographic paths.
    libraries, groups = [], []
    control = json.loads((CONTROLS / 'results.json').read_text())
    for project in PROJECTS:
        for builder in BUILDERS:
            folder = BUILD / 'libraries' / project / slug(builder)
            record = json.loads((folder / 'record.json').read_text())
            lib = {'project': project, 'builder': builder, 'status': record['status'], 'attempts': len(record['attempts'])}
            if record['status'] == 'frozen':
                package = json.loads((folder / 'package.json').read_text())
                assert digest(package) == record['package_sha256']
                lib.update(files=len(package['files']), source_bytes=sum(len(s.encode()) for s in package['files'].values()),
                           compiler_bytes=len(package['compiler'].encode()), schema_bytes=len(json.dumps(package['plan_schema']).encode()),
                           schema_properties=list(package['plan_schema']['properties']), selected_attempt=record['selected_attempt'],
                           package_sha256=record['package_sha256'])
            libraries.append(lib)
            if record['status'] != 'frozen':
                continue
            for model in PLANNERS:
                pairs = []
                for k in range(1, 21):
                    task = f'task-{k}'
                    item = {'task': task}
                    for method in ('free', 'free_lib', 'plan'):
                        b = None if method == 'free' else builder
                        item[method] = lookup[project, b, model, method, task]['final']
                    c = [r for r in control['rows'] if r['project'] == project and r['builder'] == builder and r['task'] == task]
                    for name in ('example-0', 'example-1'):
                        item[name] = next(r['passed'] for r in c if r['control'] == name)
                    item['fixed_final'] = next(r['passed'] for r in c if r['control'] == 'final-plan' and r['model'] == model)
                    pairs.append(item)
                g = {'project': project, 'builder': builder, 'model': model, 'n': len(pairs)}
                for name in ('free', 'free_lib', 'plan', 'example-0', 'example-1', 'fixed_final'):
                    g[name] = sum(r[name] for r in pairs)
                for against in ('free_lib', 'example-0', 'example-1', 'fixed_final'):
                    g['vs_' + against] = {'wins': sum(r['plan'] and not r[against] for r in pairs),
                        'losses': sum(r[against] and not r['plan'] for r in pairs),
                        'ties': sum(r['plan'] == r[against] for r in pairs)}
                stable = [r for r in pairs if project != 'bom' or r['task'] not in ('task-7', 'task-14', 'task-19')]
                g['predefined_sensitivity'] = {'n': len(stable),
                    **{name: sum(r[name] for r in stable) for name in ('free', 'free_lib', 'plan', 'example-0', 'example-1', 'fixed_final')},
                    'plan_wins_vs_free_lib': sum(r['plan'] and not r['free_lib'] for r in stable),
                    'plan_losses_vs_free_lib': sum(r['free_lib'] and not r['plan'] for r in stable)}
                groups.append(g)
    summary = {'scope': 'Three new Web-Bench projects; builders see all public requirements; strict format only, no heldout-composition claim. Prefixes/models are not independent projects.',
               'stages': {'build': str(BUILD.relative_to(ROOT)), 'run': str(BASE.relative_to(ROOT))},
               'distinct_candidates': len(rows), 'projects': list(PROJECTS), 'libraries': libraries, 'groups': groups,
               'evaluation': {'playwright': '1.57.0', 'chromium_build': '1200', 'bom_serial': True,
                   'sensitivity_rule': 'Before candidate hidden scores: exclude BOM task-7/14/19, identified by reference calibration; retain all20 in primary.'},
               'method_totals': {method: {'n': sum(r['method'] == method for r in rows),
                   'first': sum(r['first'] for r in rows if r['method'] == method),
                   'final': sum(r['final'] for r in rows if r['method'] == method)} for method in ('free', 'free_lib', 'plan')},
               'providers_used': dict(providers), 'finish_reasons_used': dict(finishes),
               'used_response_cost_usd': dict(used_cost), 'used_response_tokens': dict(tokens),
               'final_executable_free_lib_forms': dict(code_forms),
               'costs': {'build': totals(BUILD / 'budget.sqlite3'), 'run': totals(BASE / 'budget.sqlite3')},
               'rows': rows, 'fixed_control_rows': control['rows']}
    dump(ROOT / 'test/results/webbench-expand.json', summary)
    lines = ['# Web-Bench 三项目扩展', '', summary['scope'], '',
             '| 项目 | 建库者 | 规划者 | 自由 | 同库代码 | 方案 | 示例0 | 示例1 | 固定最终页 | 方案对同库 W/L/T |',
             '|---|---|---|---:|---:|---:|---:|---:|---:|---|']
    for g in groups:
        q = g['vs_free_lib']
        lines.append(f"| {g['project']} | {g['builder']} | {g['model']} | {g['free']}/20 | {g['free_lib']}/20 | {g['plan']}/20 | {g['example-0']}/20 | {g['example-1']}/20 | {g['fixed_final']}/20 | {q['wins']}/{q['losses']}/{q['ties']} |")
    lines.extend(['', '无库列跨建库者复用，不可重复计数；示例控制跨规划者复用。两建库者、两规划者和20项前缀不增加独立项目数。', '', json.dumps(summary['method_totals'], ensure_ascii=False)])
    (ROOT / 'test/results/webbench-expand.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
