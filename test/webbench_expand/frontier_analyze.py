"""Audit and summarize the independent normal-reasoning pilot and fixed control."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from pathlib import Path
from gui_dna.provider import parse_json
from test.ledger_read import totals
from .core import ROOT, PROJECTS, BUILDERS, slug, digest, dump
from .frontier import OUT as SOURCE, BUILD, MODEL, TASKS
from .generate import messages_for, output_files
from .schema import validate
from .analyze import used_response
from .evaluate_pinned import grade

OUT = ROOT / 'artifacts/webbench-expand-frontier-2'


def main():
    manifest = json.loads((OUT / 'review-manifest.json').read_text())
    for name, sha in manifest['sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    controls = json.loads((ROOT / 'artifacts/webbench-expand-controls/results.json').read_text())['rows']
    records, rows, lookup, mismatches = [], [], {}, []
    providers, finishes, usage = Counter(), Counter(), Counter()
    rejected = 0
    for project in PROJECTS:
        for task in TASKS:
            for builder in BUILDERS:
                package = json.loads((BUILD / 'libraries' / project / slug(builder) / 'package.json').read_text())
                for method in ('free_lib', 'plan'):
                    folder = OUT / 'runs' / project / slug(builder) / slug(MODEL) / method / f'task-{task}'
                    record = json.loads((folder / 'record.json').read_text())
                    records.append(record)
                    assert record['status'] == 'complete' and digest(package) == record['package_sha256']
                    messages = json.loads((folder / 'messages.json').read_text())
                    assert messages == messages_for(project, f'task-{task}', method, package)
                    if method == 'plan':
                        code_messages = json.loads((folder.parent.parent / 'free_lib' / f'task-{task}' / 'messages.json').read_text())
                        assert messages[1] == code_messages[1]
                    hidden = json.loads((folder / 'hidden.json').read_text())
                    row = {k: record[k] for k in ('project', 'builder', 'model', 'method', 'task')}
                    row.update(first=hidden['first']['all_passed'], final=hidden['final']['all_passed'],
                               attempts=len(record['attempts']), versions=len(record['versions']))
                    rows.append(row)
                    lookup[project, builder, method, task] = row
                    for attempt in record['attempts']:
                        response = used_response(folder, attempt['attempt'])
                        finishes[response['choices'][0]['finish_reason']] += 1
                        providers[response.get('provider', 'unknown')] += 1
                        for key in ('prompt_tokens', 'completion_tokens', 'cost'):
                            usage[method + '/' + key] += response['usage'].get(key, 0)
                        usage[method + '/reasoning_tokens'] += response['usage'].get('completion_tokens_details', {}).get('reasoning_tokens', 0)
                        if method == 'plan':
                            try:
                                validate(package['plan_schema'], parse_json(response['choices'][0]['message']['content']))
                            except (ValueError, KeyError, TypeError):
                                rejected += 1
                                assert f'version-{attempt["attempt"]}' not in record['versions']
                    for version in record['versions']:
                        page = folder / version
                        source = json.loads((page / 'source-manifest.json').read_text())
                        assert all(hashlib.sha256((page / name).read_bytes()).hexdigest() == sha for name, sha in source['files_sha256'].items())
                        index = version.removeprefix('version-')
                        raw = json.loads((folder / f'output-{index}.json').read_text())['text']
                        if digest(output_files(method, package, parse_json(raw))) != source['output_sha256']:
                            mismatches.append(str(page.relative_to(ROOT)))
    barrier = json.loads((OUT / 'generation-complete.json').read_text())
    assert len(records) == 60 and digest(records) == barrier['records_sha256']
    protocol = {'selection': 'Each library: always task20 last executable page, reused on prespecified tasks4/8/12/16/20. Rule fixed in original frontier manifest before calls.',
        'generation_sha256': digest(barrier), 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'evaluator_sha256': hashlib.sha256(Path(__file__).with_name('evaluate_pinned.py').read_bytes()).hexdigest()}
    target = OUT / 'fixed-final/protocol.json'
    if target.exists():
        assert json.loads(target.read_text()) == protocol
    else:
        dump(target, protocol)
    groups, control_rows = [], []
    for project in PROJECTS:
        for builder in BUILDERS:
            source = OUT / 'runs' / project / slug(builder) / slug(MODEL) / 'plan/task-20'
            record = json.loads((source / 'record.json').read_text())
            page = source / record['versions'][-1] if record['versions'] else None
            pairs = []
            for task in TASKS:
                target = OUT / 'fixed-final' / project / slug(builder) / f'task-{task}'
                score = target / 'hidden.json'
                if not score.exists():
                    dump(score, grade(project, page, f'task-{task}', target / 'report.json') if page else {'all_passed': False, 'reason': 'No executable final plan'})
                fixed = json.loads(score.read_text())['all_passed']
                pair = {'task': f'task-{task}', 'free_lib': lookup[project, builder, 'free_lib', task]['final'],
                        'plan': lookup[project, builder, 'plan', task]['final'], 'fixed_final': fixed}
                for index in range(2):
                    pair[f'example-{index}'] = next(r['passed'] for r in controls if r['project'] == project and
                        r['builder'] == builder and r['control'] == f'example-{index}' and r['task'] == f'task-{task}')
                pairs.append(pair)
                control_rows.append({'project': project, 'builder': builder, **pair})
            groups.append({'project': project, 'builder': builder, 'n': len(pairs),
                **{name: sum(r[name] for r in pairs) for name in ('free_lib', 'plan', 'fixed_final', 'example-0', 'example-1')},
                'plan_wins_vs_code': sum(r['plan'] and not r['free_lib'] for r in pairs),
                'plan_losses_vs_code': sum(r['free_lib'] and not r['plan'] for r in pairs),
                'plan_wins_vs_fixed': sum(r['plan'] and not r['fixed_final'] for r in pairs),
                'plan_losses_vs_fixed': sum(r['fixed_final'] and not r['plan'] for r in pairs)})
    costs = {str(stage.relative_to(ROOT)): totals(stage / 'budget.sqlite3') for stage in (SOURCE, OUT)}
    combined = {key: round(sum(v[key] for v in costs.values()), 6) for key in ('settled_usd', 'exposure_usd')}
    combined.update(calls=sum(v['calls'] for v in costs.values()), unsettled_calls=sum(v['unsettled_calls'] for v in costs.values()))
    result = {'scope': 'GPT-5 medium, five prespecified milestones per project; same library/input/12000 cap/2 repairs; distinct from the 600-candidate cohort. Not a low-vs-medium causal test or multi-seed evidence.',
        'model': MODEL, 'groups': groups, 'rows': rows, 'fixed_control_rows': control_rows, 'usage': dict(usage),
        'providers': dict(providers), 'finish_reasons': dict(finishes), 'cost': combined, 'costs_by_stage': costs,
        'audit': {'frozen_entries': len(manifest['sha256']), 'matched_user_pairs': 30, 'candidates': len(records),
                  'rejected_plan_attempts': rejected, 'regeneration_differences': mismatches}}
    dump(ROOT / 'test/results/webbench-expand-frontier.json', result)
    lines = ['# GPT-5 medium：三项目独立小试', '',
             '| 项目 | 建库者 | 同库代码 | 方案 | 固定最终页 | 示例0 | 示例1 | 方案对代码 W/L |',
             '|---|---|---:|---:|---:|---:|---:|---|']
    for g in groups:
        lines.append(f"| {g['project']} | {g['builder']} | {g['free_lib']}/5 | {g['plan']}/5 | {g['fixed_final']}/5 | {g['example-0']}/5 | {g['example-1']}/5 | {g['plan_wins_vs_code']}/{g['plan_losses_vs_code']} |")
    lines.extend(['', result['scope']])
    (ROOT / 'test/results/webbench-expand-frontier.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
