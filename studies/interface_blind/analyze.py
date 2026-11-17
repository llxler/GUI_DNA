"""Read-only project/builder/model summaries, preserving missing outcomes."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from test.ledger_read import calls, totals
from .core import ROOT, BUILDERS, PLANNERS, PROJECTS, digest, dump, slug


def paired(rows, first, second):
    pairs = [(r[first], r[second]) for r in rows if r[first] is not None and r[second] is not None]
    return {'n': len(pairs), 'won': sum(a and not b for a, b in pairs),
            'lost': sum(b and not a for a, b in pairs), 'tied': sum(a == b for a, b in pairs),
            'difference_pp': 100 * sum(int(a) - int(b) for a, b in pairs) / len(pairs) if pairs else None}


def summarize(stage, build):
    groups = []
    planners = json.loads((stage / 'review-manifest.json').read_text())['config']['models']
    costs = {'build': totals(build / 'budget.sqlite3'), 'generation': totals(stage / 'budget.sqlite3')}
    for i, ledger in enumerate(json.loads((build / 'build-complete.json').read_text()).get('extra_ledgers', [])):
        costs[f'build_previous_{i}'] = totals(ledger)
    prior_stage, index = stage, 0
    while (prior_stage / 'continuation.json').exists():
        prior_stage = Path(json.loads((prior_stage / 'continuation.json').read_text())['source'])
        costs[f'generation_previous_{index}'] = totals(prior_stage / 'budget.sqlite3')
        index += 1
    build_info = []
    for project in PROJECTS:
        for builder in BUILDERS:
            path = build / 'libraries' / project / slug(builder)
            record = json.loads((path / 'record.json').read_text())
            info = {**record}
            package_path = path / 'package.json'
            if package_path.exists():
                package = json.loads(package_path.read_text())
                assert digest(package) == record['package_sha256']
                info.update(file_count=len(package['files']), source_bytes=sum(len(s.encode()) for s in package['files'].values()),
                            compiler_bytes=len(package['compiler'].encode()), plan_schema=package['plan_schema'], design=package['design'])
            build_info.append(info)
            for model in planners:
                rows = []
                first_rows = []
                missing = []
                for k in range(1, 21):
                    row, first = {'task': f'task-{k}'}, {'task': f'task-{k}'}
                    for method in ('free', 'free_lib', 'plan'):
                        folder = stage / 'runs' / project / ('no_library' if method == 'free' else slug(builder)) / slug(model) / method / f'task-{k}'
                        rec_path, hidden_path = folder / 'record.json', folder / 'hidden.json'
                        row[method] = first[method] = None
                        if not rec_path.exists():
                            missing.append({'task': f'task-{k}', 'method': method, 'reason': 'no candidate/library'})
                            continue
                        rec = json.loads(rec_path.read_text())
                        if rec['status'] != 'complete' or not hidden_path.exists():
                            missing.append({'task': f'task-{k}', 'method': method, 'reason': rec['status'] if rec['status'] != 'complete' else 'ungraded'})
                            continue
                        hidden = json.loads(hidden_path.read_text())
                        row[method] = bool(hidden['final']['all_passed'])
                        first[method] = bool(hidden['first']['all_passed'])
                    rows.append(row)
                    first_rows.append(first)
                groups.append({'project': project, 'builder': builder, 'model': model, 'rows': rows,
                    'first_rows': first_rows, 'missing': missing,
                    'totals': {m: {'passed': sum(r[m] is True for r in rows), 'n': sum(r[m] is not None for r in rows)}
                               for m in ('free', 'free_lib', 'plan')},
                    'paired_plan_vs_free_lib': paired(rows, 'plan', 'free_lib'),
                    'paired_plan_vs_free': paired(rows, 'plan', 'free')})
    return {'stage': str(stage.relative_to(ROOT)), 'build_stage': str(build.relative_to(ROOT)),
            'protocol': 'Cumulative requirements, full-page generation, no human schema/shell; library-assisted methods have identical user input. Unrestricted code inherits frozen library files and may replace any of them.',
            'costs': costs, 'libraries': build_info, 'groups': groups,
            'limitations': ['Two projects, two planners, one sample; correlated tasks; no project-level significance claim.',
                            'Builders see the entire public requirement sequence; not held-out requirement transfer.',
                            'The public form requirements themselves specify classes and inheritance.',
                            'Libraries are not behaviorally verified; first public-valid output frozen without hidden selection.',
                            'Free baselines are reused across builders and must not be counted twice.']}


def markdown(data):
    lines = ['# 模型自行设计接口的两项目对照', '',
             '所有做法独立从累计需求生成完整页面；同库自由代码和方案的 user 消息相同。缺失不是模型失败。',
             '普通自由代码在两个建库者之间复用，不重复计为独立样本；下表逐建库者报告。', '',
             '| 项目 | 建库者 | 规划者 | 自由代码 | 同库自由代码 | 方案 | 方案 vs 同库 胜/负/平 |',
             '|---|---|---|---:|---:|---:|---:|']
    for group in data['groups']:
        counts = [f"{group['totals'][m]['passed']}/{group['totals'][m]['n']}" for m in ('free', 'free_lib', 'plan')]
        p = group['paired_plan_vs_free_lib']
        lines.append(f"| {group['project']} | {group['builder']} | {group['model']} | " + ' | '.join(counts) + f" | {p['won']}/{p['lost']}/{p['tied']} |")
    lines += ['', '| 阶段 | 已结算美元 | 含预留敞口 | 未结算调用 |', '|---|---:|---:|---:|']
    for name, value in data['costs'].items():
        lines.append(f"| {name} | {value['settled_usd']:.6f} | {value['exposure_usd']:.6f} | {value['unsettled_calls']} |")
    lines += ['', '解释边界：', '', *['- ' + value for value in data['limitations']], '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, default=ROOT / 'artifacts/interface-blind-final-2')
    parser.add_argument('--build', type=Path, default=ROOT / 'artifacts/interface-blind-build-2')
    parser.add_argument('--output', type=Path, default=ROOT / 'test/results/interface-blind')
    args = parser.parse_args()
    data = summarize(args.stage.resolve(), args.build.resolve())
    dump(args.output.with_suffix('.json'), data)
    text = markdown(data)
    args.output.with_suffix('.md').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
