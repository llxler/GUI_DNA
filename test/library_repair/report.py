"""Render the completed availability diagnostic from audited counts only."""
from .core import ROOT, read


def main():
    data = read(ROOT / 'test/results/library-repair-available.json')
    proof = read(ROOT / 'test/results/library-repair-replay.json')
    assert proof['all_passed']
    mechanism = read(ROOT / 'test/results/library-repair-mechanism.json')
    space = read(ROOT / 'test/results/library-repair-space.json')
    space_counts = {r['condition']: r for r in space['groups']}
    groups = data['aggregates']
    def g(form, kind, cohort, condition, method='plan'):
        return next(x for x in groups if (x['format'], x['kind'], x['cohort'], x['condition'], x['method']) == (form, kind, cohort, condition, method))
    def fraction(row, key='passed'):
        return f"{row[key]}/{row['n']}"
    main_review, main_feedback = [g('strict', 'candidate', 'main', c) for c in ('review', 'feedback')]
    cost, audit = data['cost'], data['audit']
    lines = ['## 21. 冻结接口下的库实现修复：完整配对可用子集（2026-11-13）', '',
        f"**结论先行**：原定六库的12份修复只有6份完整返回；主实验未完成。另立零API诊断，纳入两条件都完整的三库（calculator两库、table的GPT-5库）。固定旧规划输出，严格格式主口径的主规划者方案由原库{fraction(main_review, 'baseline')}变为需求自查{fraction(main_review)}、开发反馈{fraction(main_feedback)}。这不是新生成成功率，也不代表六库整体。下面同时报告同库代码、固定最终页、退步和事后格式诊断。", '',
        '### 21.1 范围、输入与传输缺失', '',
        '- 由原建库者修复files/compiler，原schema、接口说明、文档例子不变。两条件都看全部公开需求和开发配置；feedback额外看到任务2/6/10/14/18的已有实际观察。评估任务为4/8/12/16/20。测试文件互斥不等于行为独立，累积需求及开发测试可能覆盖较早评估任务的行为。',
        '- 原六库阶段遭遇代理SSL/流中断；直连模型请求被服务端按地区拒绝，随后停止新增API，保留全部记录与未知预留。没有继续改路由或放宽账本。calculator的两库和table的GPT-5库均完成两条件；table/Sonnet和BOM两库的六份修复仍是传输缺失，不计为模型失败。',
        '- 四份GPT-5修复通过原验证器。两份Sonnet响应有前导说明，严格JSON契约下回退原库。另一个在新评分前冻结的事后诊断只提取唯一JSON代码块，不改代码、不补括号、不重抽；两份均可编译。此结果不替代严格口径。',
        '- 原六库阶段没有新候选评分。可用子集单独冻结于`artifacts/library-repair-available-20261113/`：90个旧候选、固定最终方案、开发检查，两修复条件和两格式口径共600项比较，按完整页面/项目/任务去重为204次浏览器检查；同页复用不当独立样本。原本无可执行版本仍在分母。原参考页30项校准全部通过。', '',
        '### 21.2 原输出重放：严格输出契约', '',
        '| 规划者组 | 做法 | 原库 | 自查后 | 自查改善/退步 | 加开发反馈后 | 反馈改善/退步 |',
        '|---|---|---:|---:|---:|---:|---:|']
    def markdown_rows(form):
        result = []
        for cohort in ('main', 'strong'):
            for kind, method, label in (('candidate', 'free_lib', '同库代码'), ('candidate', 'plan', '方案'), ('fixed', 'plan', '固定最终方案')):
                a, b = [g(form, kind, cohort, c, method) for c in ('review', 'feedback')]
                result.append(f"| {'GPT-OSS＋Mistral' if cohort == 'main' else 'GPT-5 medium'} | {label} | {fraction(a, 'baseline')} | {fraction(a)} | {a['wins']}/{a['losses']} | {fraction(b)} | {b['wins']}/{b['losses']} |")
        return result
    lines += markdown_rows('strict')
    lines += ['', '主规划者与GPT-5小试分别报告，不把同一项目的建库者/规划者/累积里程碑当作独立应用。所有数字描述这个事后可用子集，不进行跨项目显著性推断。', '',
        '### 21.3 唯一JSON代码块提取：事后格式诊断', '',
        '| 规划者组 | 做法 | 原库 | 自查后 | 自查改善/退步 | 加开发反馈后 | 反馈改善/退步 |',
        '|---|---|---:|---:|---:|---:|---:|']
    lines += markdown_rows('single_fence')
    lines += ['', '本次两格式口径的行为分数完全相同。提取规则是在看到输出包装问题后、尚未运行任何新候选行为评分时固定的，因此明确标为事后诊断。模型内容没变，但解析合同变了，不能选其中较好分数作为主结果。', '',
        '| 格式口径 | 固定开发配置原库 | 自查后 | 加反馈后 |', '|---|---:|---:|---:|']
    for form in ('strict', 'single_fence'):
        a, b = [g(form, 'development', 'main', c) for c in ('review', 'feedback')]
        lines.append(f"| {form} | {fraction(a, 'baseline')} | {fraction(a)} | {fraction(b)} |")
    lines += ['', 'schema/说明/例子逐字保留只保证接口字段没变，不能证明选项行为语义未被重新解释。固定开发配置本身也可能选错，因此不能把全部改善/失败归为库实现质量。字节级页面多样性另见`test/results/library-repair-diagnostics.json`，不同源码不等于不同正确行为。', '',
        '### 21.4 单一事件传播缺陷的四页干预', '',
        '所有新增候选通过都来自**table/GPT-5库的task-20**：三个规划者给出的方案完全相同，不是三个独立发现。旧页的表格右键监听器先显示菜单，事件继续冒泡到document监听器后又将菜单关闭；原报告首个失败是排序菜单项不可见。反馈修复在表格监听器增加`e.stopPropagation()`，编译器未变。', '',
        '观察这个结果后，再冻结四张页面进行一次额外本地评分：原页、原页只加这一行、完整反馈修复页、修复页只撤掉这一行。所有源与分数保留，不改变任何模型成绩。', '',
        '| 页面干预 | task-20全过 |', '|---|---:|']
    names = {'original': '原页', 'original_plus_stop': '原页只加stopPropagation', 'feedback': '完整反馈修复页', 'feedback_minus_stop': '修复页只撤掉stopPropagation'}
    for row in mechanism['rows']:
        lines.append(f"| {names[row['name']]} | {'是' if row['all_passed'] else '否'} |")
    lines += ['', '两张通过页均通过该文件全部3项；失败页在首个决定性失败后停止，后续缺失项不当作通过。这为**这个固定页面与任务**给出该行的必要/充分干预证据，不能外推为所有失败均是库错误或证明全部配置的行为正确。独立原始报告复算另核对这4项；源码与清单在`test/library_repair/mechanism.py`及`artifacts/library-repair-mechanism-20261113/`。', '',
        '同库代码的复用方式也解释了一个差异：GPT-OSS在task-20覆盖了`index.js`，保留旧的事件处理代码，换库前后该文件完全相同且均失败；Mistral的build程序和GPT-5未覆盖该文件的候选得到更新后的实现并通过。不能把这个更新传播差异解释成重新规划能力。逐输出核对见诊断JSON。', '',
        '### 21.5 固定样式下穷举全部交互开关', '',
        '看到事件传播缺陷后，另行冻结零API枚举：保持原最终方案的theme/palette/menuStyle/gridDensity四项样式字段不变，穷举interactions内全部7个布尔选项。每个方案均通过原封闭模式与编译器；原库与只加stopPropagation的版本分别评分，不根据结果选配置。两个全开页面精确复用上一小节的已存报告，其余254项首次评分，全部观察保留。', '',
        '| 实现 | 固定样式下的合法配置 | task-20全过 |', '|---|---:|---:|',
        f"| 原库 | {space_counts['original']['n']} | {space_counts['original']['passed']} |",
        f"| 只加stopPropagation | {space_counts['stop_only']['n']} | {space_counts['stop_only']['passed']} |", '',
        '这给出**固定样式切片、指定测试与运行环境下**的完整枚举观测，不能外推为整个schema无解、所有任务正确、128个独立任务或跨项目结论。它比只看某一个模型方案更直接地检查了“换一组交互开关能否避免该缺陷”。源码与冻结清单分别为`test/library_repair/finite_space.py`和`artifacts/library-repair-space-20261113/inputs.json`。', '',
        '### 21.6 费用、审计与尚未完成部分', '',
        f"本次27个预留请求中6份完整模型响应；5份已归档中断响应通过平台逐请求元数据确认费用后正常结算，16份费用未确认，仍保留全额预留。新增已结算 **${cost['settled_usd']:.6f}**，保守敞口 **${cost['exposure_usd']:.6f}**，均在用户本次$10授权内。账本cap $9、stop=0；未使用剩余授权追加实验。本地计算与人工时间未计价。查询接口及凭证规则见`test/library_repair/TRANSPORT.md`。", '',
        f"审计核对{audit['completed_responses']}份完整响应、{audit['snapshot_files']}个评分前快照文件、{audit['comparisons']}项比较和{audit['unique_browser_scores']}份原始报告，另有4页事件传播干预及254次新增枚举评分；独立入口从共462份不同的原始Playwright报告重新推导全过/不过。与原文件完全一致的比较有{audit['unchanged_comparisons']}项，其中{len(audit['unchanged_score_mismatches'])}项分数不一致；若有时序差异，完整保留，不择优重跑。", '',
        '**目前明确的是**：原输出能在不重新规划的情况下用于实现干预诊断；必须同时保留格式失败、实现修复退步和同库代码/固定页对照。**还不能确认的是**：六库整体效果、开发反馈的一般因果收益、严格接口语义保持、未见需求或非模板组合迁移，以及LLM规划是否必要。未完成的六份传输、非模板任务与充分反馈仍在TODO P2c/P6b；不能因这个子集可评分而勾掉原六库实验。', '',
        '零API入口：`uv run python -m test.library_repair.available analyze`、`uv run python -m test.replay_library_repair`、`uv run python -m test.library_repair.diagnostics`、`uv run python -m test.library_repair.finite_space analyze`。生成账本已关闭，不运行原`run`续发请求。']
    validation_path = ROOT / 'test/results/replay-validation-20261113-final.json'
    if validation_path.exists():
        validation = read(validation_path)
        if validation.get('all_passed') and validation.get('browser_smoke', {}).get('all_passed'):
            rows = validation['browser_smoke']['rows']
            lines += ['', f"交付复验：最终匿名快照的{validation['hashes_verified']}个文件哈希全部核对，{len(validation['checks'])}个汇总入口在独立目录重算一致。额外从解包副本离线重装锁定npm依赖，四张机制页面与官方参考页共{len(rows)}项实际浏览器结果均复现；新报告保存在`artifacts/replay-browser-20261113-final/`，不覆盖原分数。它共享本机OS、Chromium缓存与系统库，不是跨机器或全部历史浏览器重跑。验证见`test/results/replay-validation-20261113-final.json`；匿名包仅本地保存，未上传。"]
    section = '\n'.join(lines) + '\n'
    path = ROOT / '实验结果.md'
    text = path.read_text()
    marker = '\n## 21. '
    if marker in text:
        start = text.index(marker)
        end = text.find('\n## ', start + len(marker))
        text = text[:start] + '\n' + section + (text[end:] if end >= 0 else '')
    else:
        text = text.rstrip() + '\n\n' + section
    path.write_text(text)
    (ROOT / 'test/results/library-repair-available.md').write_text(section)

    tex = [r'\section{Implementation Revisions with Fixed Planner Outputs}', r'\label{app:library-repair}', '',
        'This post-hoc diagnostic asks whether changing an implementation changes the behavior of already generated outputs. This appendix preserves the November 13 snapshot: only six of twelve revision responses had returned completely. A separately disclosed continuation completes the six-library replay in \\cref{app:nov14}. Network interruptions and regional request refusals are retained as transport failures, not model failures. We close new requests and evaluate a separate matched-availability subset: both calculator libraries and the GPT-5 table library. No BOM library enters this subset. Selection requires a complete response in both revision conditions, without inspecting new scores; it nevertheless introduces project/provider availability bias.', '',
        'The original builder receives the full public requirements, original package and five fixed development plans. A review condition asks it to revise implementation files and compiler; a feedback condition additionally supplies saved observations for task files 2/6/10/14/18. Schema, documentation and example plans remain byte-identical. Each condition has one complete response, with a 26,000-token output cap including reasoning and no behavioral repair loop. GPT-5 uses medium reasoning. Compilation checks do not establish that option meanings are preserved.', '',
        'After freezing these responses, we replay the old GPT-OSS, Mistral and GPT-5 outputs on files 4/8/12/16/20, plus fixed final plans and separate development checks. There are 90 distinct old candidates and 600 comparisons across conditions, controls and two format conventions; exact page/task deduplication yields 204 browser evaluations. The pinned Playwright 1.57/Chromium 1200 runtime and assertions are unchanged; all 30 reference calibration checks pass. Disjoint test-file numbers do not imply disjoint semantics: requirements and behaviors are cumulative and all target requirements were already visible. These are replay outcomes, not new generation or unseen-requirement performance.', '',
        'Four GPT-5 revisions satisfy the original parser. Both Sonnet responses add prose before JSON and therefore fall back to the original library under the strict protocol. Before any new candidate scoring, we add a separately labeled diagnostic that extracts exactly one fenced JSON block and applies the same validation, without editing content or making another model request. Both Sonnet revisions then compile. This post-generation format adaptation never replaces the strict results.', '',
        r'\begin{table}[h]', r'\centering', r'\caption{Available-pair replay only. Review and feedback each revise the implementation once; planning outputs are fixed. Main pools GPT-OSS and Mistral. Rows remain correlated within two projects.}',
        r'\label{tab:library-repair}', r'\small', r'\begin{tabular}{@{}lllrrr@{}}', r'\toprule',
        r'Format & Cohort & Output & Original & Review & Feedback \\', r'\midrule']
    for form in ('strict', 'single_fence'):
        for cohort in ('main', 'strong'):
            for kind, method, label in (('candidate', 'free_lib', 'Code + library'), ('candidate', 'plan', 'Plan'), ('fixed', 'plan', 'Fixed final')):
                a, b = [g(form, kind, cohort, c, method) for c in ('review', 'feedback')]
                tex.append(f"{'Strict' if form == 'strict' else 'JSON fence'} & {'Main' if cohort == 'main' else 'GPT-5'} & {label} & {fraction(a, 'baseline')} & {fraction(a)} & {fraction(b)} " + r'\\')
    tex += [r'\bottomrule', r'\end{tabular}', r'\end{table}', '',
        f"Strict development checks pass {fraction(g('strict', 'development', 'main', 'review'), 'baseline')} with original packages, {fraction(g('strict', 'development', 'main', 'review'))} after review and {fraction(g('strict', 'development', 'main', 'feedback'))} with feedback. Under the single-fence diagnostic, the corresponding revised scores are {fraction(g('single_fence', 'development', 'main', 'review'))} and {fraction(g('single_fence', 'development', 'main', 'feedback'))}. A fixed development plan can itself select the wrong configuration; changes cannot all be attributed to implementation defects. Single samples and possible reinterpretation of options also prevent a general causal claim about feedback.", '',
        'Every newly passing candidate is from the GPT-5 table library on task 20. All three planners submit the same final plan. Its original table context-menu listener displays a menu, but the event then bubbles to a document listener that hides it. The feedback revision adds \\code{e.stopPropagation()} while keeping the compiler unchanged. After observing this case, we freeze a separate four-page intervention: the original page fails, adding only this line makes all three assertions pass, the full revised page passes, and removing only the line makes it fail again. Failures stop at the first decisive assertion. This isolates a concrete implementation defect for this page/task; it neither attributes every failure to the library nor establishes planning value.', '',
        'Reuse granularity explains one code result: the GPT-OSS file override retains its own unchanged \\code{index.js} and still fails after the library revision. The Mistral build program and GPT-5 candidate that does not override this file receive the updated implementation and pass. This concerns propagation of an implementation change, not a newly generated planning decision.', '',
        f"We then freeze a separate post-hoc enumeration of all seven Boolean interaction switches, holding the final plan's four style fields fixed. Every configuration passes the original schema and compiler. The original implementation passes {space_counts['original']['passed']}/128 configurations on task 20; adding only \\code{{stopPropagation}} passes {space_counts['stop_only']['passed']}/128. Two exact all-enabled pages reuse the prior intervention reports; 254 additional browser checks complete the enumeration. These are observations for one fixed-style slice and test environment, not an impossibility proof for the entire schema, 128 independent tasks, or evidence of cross-project transfer.", '',
        f"The ledger settles \\${cost['settled_usd']:.6f}, including five interrupted calls whose charges are subsequently confirmed by provider metadata. Exposure including sixteen unresolved reservations is \\${cost['exposure_usd']:.6f}, below this stage's authorized \\$10; new requests are closed. All 600 comparisons and 204 raw reports, plus four mechanism interventions and 254 new enumeration scores, are audited with an independent recomputation from stored reports. Among {audit['unchanged_comparisons']} comparisons whose entire file map equals its original, {len(audit['unchanged_score_mismatches'])} differ in outcome; observations are retained without best-of reruns. The remaining three library pairs, non-template transfer and semantic interface guarantees remain unresolved."]
    (ROOT / 'DNA_latex/library_repair.tex').write_text('\n'.join(tex) + '\n')
    print('Updated experiment section 21 and local paper appendix')


if __name__ == '__main__':
    main()
