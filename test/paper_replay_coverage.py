"""Inventory local manuscript tables and the exact limits of replay coverage.

This is a provenance index, not a numerical comparison of LaTeX cells. It reads
the local ignored manuscript; the generated index can accompany a source bundle.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'DNA_latex'


def evidence(status, modules, sources, runtime, missing):
    return dict(source_coverage=status, replay_modules=modules.split(),
                sources=sources.split(), runtime=runtime, remaining=missing)


PRIMARY = evidence('partial', 'test.replay_primary_tables test.review_metrics',
    'test/results/primary-replay.json test/results/review-metrics.json',
    'TodoMVC/Web-Bench: locked Playwright 1.63 + Chromium; List-16: Python Playwright.',
    'Accuracy source aggregates are checked. This entry does not by itself reconstruct every auxiliary source/cohort or per-model paired column appearing across these tables; see the replay output for the exact records checked. No full original browser replay or literal TeX-cell comparison.')
NEW = evidence('recomputed_sources', 'test.replay_new_tables',
    'test/results/new-tables-replay.json', 'Web-Bench expansion: locked Playwright 1.57; synthetic: Python Playwright.',
    'Reconstructs saved candidate/control outcomes and ledger totals. Not a fresh browser run or literal TeX-cell comparison.')
NOV14 = evidence('recomputed_sources', 'test.replay_nov14',
    'test/results/nov14-replay.json', 'Locked Playwright 1.57 for expansion repair/toggles; 1.63 for dom1 prefixes.',
    'Reconstructs saved raw reports and ledgers, including reused reports. No fresh execution of every page or literal TeX-cell comparison.')
NOV15 = evidence('recomputed_sources', 'test.replay_nov15',
    'test/results/nov15-replay.json', 'History: original 1.63/1.57; interaction diagnostics: Python Playwright.',
    'Reconstructs raw reports, configuration proposals and ledgers. History was newly executed locally; the anonymous summary check does not itself rerun browsers or compare literal TeX cells.')
STATIC = evidence('specification', '', 'AGENTS.md', 'No numeric outcome replay applies.',
    'Descriptive protocol/source inventory; manual comparison with the stated specification remains necessary.')


def mapping():
    m = {name: PRIMARY for name in ('tab:main', 'tab:models', 'tab:todomvc-full', 'tab:webbench-full', 'tab:samples', 'tab:seeds')}
    for name in ('tab:suites', 'tab:list16-lib', 'tab:todomvc-tests'):
        m[name] = STATIC
    for name in ('tab:interface-main', 'tab:heldout-main', 'tab:expansion', 'tab:expansion-frontier', 'tab:heldout-full'):
        m[name] = NEW
    for name in ('tab:history-main', 'tab:history-replay', 'tab:task-history', 'tab:interaction-transfer',
                 'tab:interaction-library-shape', 'tab:interaction-controls', 'tab:development-feedback'):
        m[name] = NOV15
    m['tab:prefix-factorial'] = NOV14
    m['tab:list16'] = evidence('recomputed_sources', 'test.replay_scale_table test.replay_table_details test.replay_nov15', 'test/results/scale-table-replay.json test/results/table-details-replay.json',
        'Python Playwright; original generation remains paused.',
        'Accuracy and paired intervals reconstructed for complete groups; cost and response tokens separately reconstructed over all attempted records. No writable Ledger, fresh browser run or literal TeX-cell comparison.')
    m['tab:webbench-full'] = evidence('recomputed_sources', 'test.replay_primary_tables test.replay_table_details test.replay_nov15',
        'test/results/primary-replay.json test/results/table-details-replay.json',
        'Locked Playwright 1.63; retained transport classification and original six-stage costs.',
        'Passes, calls/rejections, sequential current-file score and costs independently reconstructed. This sequential score is not the complete-history endpoint; no new browser execution or literal TeX-cell comparison.')
    m['tab:intervals'] = evidence('recomputed_sources', 'test.paired_intervals test.review_metrics',
        'test/results/paired-intervals.json test/results/review-metrics.json', 'No new browser dependency.',
        'Recomputes bootstrap summaries from saved scores; does not remove task/model dependence or check literal TeX cells.')
    m['tab:repair'] = evidence('recomputed_sources', 'test.repair_breakdown test.replay_primary_tables test.replay_scale_table',
        'test/results/repair-breakdown.json', 'No new browser dependency.',
        'First/final classifications from retained records; no new execution or literal TeX-cell check.')
    m['tab:relax'] = evidence('recomputed_sources', 'test.replay_nov15 test.replay_review_tables',
        'test/results/review-tables-replay.json',
        'Duo: historical CRA/Jest/npm pins; TodoMVC: locked Playwright 1.63.',
        'Strict live backups and the same original relaxed responses are reconstructed, with Duo verdicts checked against raw Jest reports. Gemma is absent from the early strict summary and uses its live backups. No historical Jest/browser reinstall or literal TeX-cell comparison.')
    m['tab:interfaces'] = evidence('recomputed_sources', 'test.interface_blind.analyze',
        'test/results/interface-blind.json', 'Locked Playwright 1.63.',
        'Source records and first/final hidden scores are recomputed; not every raw browser assertion is reconstructed by this entry, and literal TeX cells are not compared.')
    m['tab:library-repair'] = evidence('recomputed_sources', 'test.replay_library_repair',
        'test/results/library-repair-replay.json', 'Locked Playwright 1.57.',
        'Three-library-pair timestamp remains separate from the later six-library result. Raw-report reconstruction, not full browser reexecution or literal TeX-cell comparison.')
    for name in ('tab:cost', 'tab:expansion-libraries', 'tab:expansion-sensitivity', 'tab:heldout-usage'):
        m[name] = evidence('recomputed_sources', 'test.replay_nov15 test.replay_table_details',
            'test/results/table-details-replay.json',
            'Read-only SQLite, source packages, adopted responses and saved hidden scores; no new browser dependency.',
            'Explicit original cost-stage set, displayed library-size/attempt and sensitivity columns, or adopted-response token usage are independently reconstructed. Not a fresh browser run or a comparison of every TeX cell.')
    for name in ('tab:round1', 'tab:round2'):
        m[name] = evidence('recomputed_sources', 'test.replay_nov15 test.replay_pilot_tables',
            'test/results/pilot-tables-replay.json', 'Retained per-case Python Playwright evaluations; read-only ledger/request identities.',
            'Both pilot tables and posthoc linker outcomes are independently reconstructed, including round-1 generation fees. Not a fresh browser run; surrounding prose and every token/timing claim remain outside this check.')
    return m


def table_inventory():
    sources, tables = {}, []
    def visit(name, ancestors=()):
        path = PAPER / (name if name.endswith('.tex') else name + '.tex')
        if path in ancestors:
            raise ValueError('Recursive TeX input')
        text = path.read_text()
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        ordinal = 0
        for match in re.finditer(r'\\input\{([^}]+)\}|\\begin\{table\*?\}.*?\\end\{table\*?\}', text, re.S):
            if match.group(1):
                visit(match.group(1), ancestors + (path,))
                continue
            ordinal += 1
            labels = re.findall(r'\\label\{([^}]+)\}', match.group())
            caption = re.search(r'\\caption\{([^\n]+)', match.group())
            tables.append(dict(id=labels[0] if labels else f'{path.stem}:table-{ordinal}',
                               file=str(path.relative_to(ROOT)), line=text[:match.start()].count('\n') + 1,
                               caption_start=caption.group(1)[:180] if caption else 'No caption'))
    visit('main')
    return sources, tables


def unlabeled(row):
    cap, name = row['caption_start'], Path(row['file']).name
    if name == 'nov14_study.tex':
        return NOV14
    if 'Complete matched cohort' in cap:
        return evidence('partial', 'test.review_metrics', 'test/webbench_dna/results/clean-prefix.json',
            'Locked Playwright 1.63; original transport continuation preserved.',
            'Matched counts are reconstructed from the saved clean-prefix summary; raw responses and every browser report are not independently reconciled by that entry.')
    if 'Full-task passes under prompt interventions' in cap or 'Requirements-only body construction' in cap:
        return evidence('recomputed_sources', 'test.replay_nov15 test.replay_review_tables', 'test/results/review-tables-replay.json',
            'Locked Playwright 1.63; prior evaluator corrections retained.',
            'Accuracy, denominators and rejections reconstructed from records and retained hidden scores. Surrounding reference-choice agreement and all condition-level costs are outside this check; no fresh browser run or literal TeX-cell check.')
    if 'Frozen source size' in cap:
        return evidence('recomputed_sources', 'test.review_metrics', 'test/results/review-metrics.json',
            'Local source files only.', 'Sizes are reconstructed; human effort is unknown and not inferred from bytes.')
    if name == 'interface_study.tex':
        if 'Four model-proposed' in cap:
            return evidence('recomputed_sources', 'test.interface_blind.analyze', 'test/results/interface-blind.json',
                'Local source and read-only SQLite.', 'Source sizes and stage fees reconstructed; not a literal TeX-cell check.')
        if 'Separate behavior-feedback' in cap:
            return evidence('recomputed_sources', 'test.behavior_feedback_analyze', 'test/results/behavior-feedback.json',
                'Locked Playwright 1.63.', 'Saved before/after scores are reaggregated; no fresh browser execution or literal TeX-cell check.')
        return evidence('recomputed_sources', 'test.replay_nov15 test.replay_review_tables', 'test/results/review-tables-replay.json',
            'Locked Playwright 1.63.', 'Original current-task fixed controls reconstructed from 320 raw Playwright reports, independently of the new history endpoint. No fresh browser execution or literal TeX-cell comparison.')
    raise ValueError(f'Unmapped manuscript table: {row}')


def main():
    sources, rows = table_inventory()
    mapped = mapping()
    for row in rows:
        row.update(mapped[row['id']] if row['id'] in mapped else unlabeled(row))
        for module in row['replay_modules']:
            assert (ROOT / (module.replace('.', '/') + '.py')).exists(), module
        row['source_paths_present'] = {p: (ROOT / p).exists() for p in row['sources']}
    descriptions = {
        'specification': '规范/来源描述，仍需人工逐项核对，不适用准确率复算。',
        'recomputed_sources': '对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。',
        'partial': '部分来源、配对子列或辅助口径尚未全部覆盖，具体范围见同名JSON及重算输出。',
        'not_recomputed': '尚无对应的独立包重算入口；需保留原始协议和历史时间点另行复算。',
    }
    for row in rows:
        row['remaining_zh'] = descriptions[row['source_coverage']]
        if row['id'] == 'tab:round2':
            row['remaining_zh'] += '已使用独立只读入口，未调用会打开可写主账本的旧汇总器。'
        if row['id'] == 'tab:cost':
            row['remaining_zh'] += '原始阶段名单已明确固定，不能换用当前全账本总额。'
        if row['id'] == 'tab:relax':
            row['remaining_zh'] += '另需历史CRA/Jest运行环境；当前Chromium复验不能代替它。'
    result = dict(scope='Table-to-source coverage inventory only; not independent numerical verification of every LaTeX cell. The local manuscript is intentionally excluded from Git and anonymous source bundles.',
                  manuscript_sources_sha256=sources, table_count=len(rows),
                  source_coverage_counts=dict(Counter(r['source_coverage'] for r in rows)), rows=rows)
    path = ROOT / 'test/results/paper-table-coverage.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    lines = ['# 论文逐表复验范围', '', '这是来源对应表，不是所有LaTeX单元格均已验证的证明。`recomputed_sources`只表示相关来源在现有独立入口中重算；`partial`保留未覆盖列；`not_recomputed`明确列出缺口。全文及附录表格均登记，未编号表以源文件顺序标识。', '',
             '| 表格 | 来源复算范围 | 入口 | 尚未覆盖 |', '|---|---|---|---|']
    for row in rows:
        lines.append('| ' + ' | '.join((row['id'], row['source_coverage'], ', '.join(row['replay_modules']) or '无独立入口', row['remaining_zh'])) + ' |')
    lines += ['', '浏览器运行时、来源路径及本地论文输入哈希见同名JSON。源码路径存在不等于运行器或整套浏览器已在独立环境复现；原第三轮保持暂停。', '']
    path.with_suffix('.md').write_text('\n'.join(lines))
    print(json.dumps({'tables': len(rows), 'coverage': result['source_coverage_counts'],
                      'missing_source_paths': sorted({p for r in rows for p, exists in r['source_paths_present'].items() if not exists})}, ensure_ascii=False))


if __name__ == '__main__':
    main()
