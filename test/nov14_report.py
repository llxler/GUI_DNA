"""Render completed November 14 diagnostics from audited result files."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / 'test/results' / name).read_text())


def replace_section(number, text):
    path = ROOT / '实验结果.md'
    source = path.read_text()
    marker = f'\n## {number}. '
    if marker in source:
        start = source.index(marker)
        end = source.find('\n## ', start + len(marker))
        source = source[:start] + '\n' + text.rstrip() + '\n' + (source[end:] if end >= 0 else '')
    else:
        source = source.rstrip() + '\n\n' + text.rstrip() + '\n'
    path.write_text(source)


def main():
    full, toggle, factorial = [read(n) for n in ('library-repair-full.json', 'library-toggle-control.json', 'prefix-factorial.json')]
    proof, cost, prefix = [read(n) for n in ('nov14-replay.json', 'review-20261114-costs.json', 'prefix-history-audit.json')]
    entry = read('library-repair-entrypoint.json')
    assert proof['all_passed']
    assert all(d['current'] and not d['history'] for d in factorial['endpoint_divergences'])
    plan_failure_text = '; '.join(f"{r['n']} cases in {r['file']} ({r['title']})"
        for r in proof['prefix_factorial']['earlier_failure_groups'] if r['method'] == 'plan')
    def repair(form, kind, cohort, condition, method='plan'):
        return next(r for r in full['aggregates'] if (r['format'], r['kind'], r['cohort'], r['condition'], r['method']) == (form, kind, cohort, condition, method))
    def frac(r, key='passed'):
        return f"{r[key]}/{r['n']}"
    a, b = [repair('strict', 'candidate', 'main', c) for c in ('review', 'feedback')]
    lines = ['## 22. 六库实现修复续作与完整旧输出重放（2026-11-14）', '',
        f"**结论先行**：补齐六份传输缺失后，六库两条件共12份完整响应齐备。严格格式口径下，主规划者方案从原库{frac(a, 'baseline')}变为需求自查{frac(a)}、开发反馈{frac(b)}；同库代码和固定最终方案同样保留为对照。结果描述旧输出重放，不能叫新的规划成功率。第21节三库时间点快照保留，不回填成此前已完成。", '',
        '### 22.1 续作边界', '',
        '- 新阶段复制原六份完整记录，包括严格格式失败，逐字保留消息、输出、部署结果；只补table/Sonnet和两套BOM库的六份缺失。原模型、供应商约束、推理强度、seed及26000输出上限不变。正常代理连接完成本次调用，没有改路由或放宽旧账本。',
        '- 续作时已观察第21节三库子集成绩；原公开开发观察与修复输入逐字保持，未加入这些成绩。十二份完整响应在本次整合评分前冻结，但不能声称全部六库都在首次评分前生成。',
        f"- 重放180个不同旧候选，加固定最终方案与开发检查，严格与唯一JSON代码块两口径共{full['audit']['comparisons']}项比较。按完整页面/项目/任务去重为{full['audit']['unique_browser_scores']}份报告，其中{full['audit']['reused_browser_scores']}份逐字复用第21节，{full['audit']['new_browser_scores']}份新增；不按得分决定是否复用。", '',
        '### 22.2 严格契约与格式诊断', '',
        '| 格式 | 规划者 | 做法 | 原库 | 自查后 | 自查改善/退步 | 反馈后 | 反馈改善/退步 |', '|---|---|---|---:|---:|---:|---:|---:|']
    repair_tex = []
    for form in ('strict', 'single_fence'):
        for cohort in ('main', 'strong'):
            for kind, method, name, english in (('candidate', 'free_lib', '同库代码', 'Code'), ('candidate', 'plan', '方案', 'Plan'), ('fixed', 'plan', '固定最终', 'Fixed')):
                x, y = [repair(form, kind, cohort, c, method) for c in ('review', 'feedback')]
                label = '主两模型' if cohort == 'main' else 'GPT-5 medium'
                lines.append(f"| {form} | {label} | {name} | {frac(x, 'baseline')} | {frac(x)} | {x['wins']}/{x['losses']} | {frac(y)} | {y['wins']}/{y['losses']} |")
                repair_tex.append(f"{'Strict' if form == 'strict' else 'Fence'} & {'Main' if cohort == 'main' else 'GPT-5'} & {english} & {frac(x, 'baseline')} & {frac(x)} & {frac(y)} " + r'\\')
    lines += ['', '逐库的主方案比较（每格10个相关里程碑输出）：', '',
              '| 项目/建库者 | 原库 | 严格自查 | 严格反馈 | 提取自查 | 提取反馈 |',
              '|---|---:|---:|---:|---:|---:|']
    for pair in full['selected_pairs']:
        values = [next(r for r in full['groups'] if all(r[k] == v for k, v in pair.items())
                       and (r['format'], r['kind'], r['cohort'], r['condition'], r['method'])
                       == (form, 'candidate', 'main', condition, 'plan'))
                  for form, condition in (('strict', 'review'), ('strict', 'feedback'),
                                          ('single_fence', 'review'), ('single_fence', 'feedback'))]
        builder = 'GPT-5' if pair['builder'] == 'openai/gpt-5' else 'Sonnet'
        lines.append(f"| {pair['project']}/{builder} | {frac(values[0], 'baseline')} | " + ' | '.join(frac(v) for v in values) + ' |')
    secondary = repair('single_fence', 'candidate', 'main', 'feedback')
    lines += ['', f"唯一代码块口径的主方案反馈结果包含{secondary['wins']}项改善、{secondary['losses']}项退步。逐库净收益不能替代成普遍修复收益；同一库的不同规划者和任务也不是独立重复。"]
    fallback = [r for r in full['libraries'] if r['deployed'] == 'original_fallback']
    lines += ['', f"12份响应中{len(fallback)}份严格输出回退原库；其中{sum(r['single_fence_extracted'] for r in fallback)}份可由此前固定的唯一JSON代码块规则提取并编译。两口径均完整报告，不择优作为主结果。原schema、说明和例子不变，仍不保证配置语义等价。", '',
        f"与原页面完全相同的比较共{full['audit']['unchanged_comparisons']}项，{len(full['audit']['unchanged_score_mismatches'])}项评分不同；完整差异保存在JSON，不选择较高分。逐库/规划者/任务结果见`test/results/library-repair-full.json`。", '',
        f"本次补缺新增已结算${full['cost']['settled_usd']:.6f}、保守敞口${full['cost']['exposure_usd']:.6f}，账本stop=0。此前阶段另有已结算${full['prior_generation_cost']['settled_usd']:.6f}、敞口${full['prior_generation_cost']['exposure_usd']:.6f}，未知预留保持不变，不能重复计入今天新增成本。", '',
        '**目前明确的是**：原六库的完整配对已补齐，格式与实现干预可以分别复验。**还不能确认的是**：反馈的一般因果收益、严格接口语义保持、独立项目泛化或新规划能力。开发和评估编号不同仍有累计语义重叠。', '',
        '入口：`test.library_repair_resume.replay analyze`；完整原始来源、续作协议见`test/library_repair_resume/PROTOCOL.md`。']
    lines += ['', '### 22.3 入口文件缺失：固定单例的反向与恢复干预', '',
        '观察完整六库结果后发现table/Sonnet的两份修订都漏掉`files["index.js"]`。原HTML继续引用它，而编译器只在遍历到该键时生成入口实现。另冻结原GPT-OSS/task-4方案的六张页面：原页及删除入口、两修订及各自仅恢复原占位键再编译；不修改方案、其他文件或编译器。恢复的是`// INDEX_JS_PLACEHOLDER`，不是把原正确实现覆盖到修订上。', '',
        '| 页面 | 有index.js | 官方task-4全过 |', '|---|---:|---:|']
    for row in entry['rows']:
        lines.append(f"| {row['name']} | {'是' if row['entry_present'] else '否'} | {'是' if row['passed'] else '否'} |")
    lines += ['', f"六张页面的{entry['audit']['unique_reports']}份报告中{entry['audit']['reused_reports']}份精确复用，其余新增。此干预仅解释该固定方案/task-4的结果，不回写模型成绩，不证明所有退步都来自此缺陷。源码与预先冻结范围见`test/library_repair_resume/entrypoint.py`和`ENTRYPOINT.md`；独立复算同时核对页面差异仅为入口文件。"]
    replace_section(22, '\n'.join(lines))

    lines = ['## 23. 六套模型接口的条件布尔配置对照（2026-11-14，零API）', '',
        f"**结论先行**：在六个原GPT-OSS最终方案锚点上冻结非布尔字段和键集合，测试{toggle['audit']['configurations']}个配置、{toggle['audit']['comparisons']}项里程碑比较。三个切片完整枚举，另三个均匀无放回抽32项；这不是整个schema的随机基线。原第20节{toggle['historical_witness_pairs']}/120个已观测可达配对，结合本次见证为{toggle['union_witness_pairs']}/120；旧统计文件与原候选成绩不改。", '',
        '| 项目/建库者 | 已出现布尔数 | 切片大小 | 测试配置 | 平均通过任务/5 | 原锚点/5 | 样本中最多/5 |', '|---|---:|---:|---:|---:|---:|---:|']
    toggle_tex = []
    for lib in toggle['libraries']:
        builder = 'GPT-5' if lib['builder'] == 'openai/gpt-5' else 'Sonnet'
        lines.append(f"| {lib['project']}/{builder} | {len(lib['boolean_paths'])} | {lib['population']} | {lib['sampled']} | {lib['mean_tasks_passed']:.3f} | {lib['anchor_tasks_passed']} | {lib['best_sample_tasks']} |")
        toggle_tex.append(f"{lib['project']} & {builder} & {len(lib['boolean_paths'])} & {lib['sampled']}/{lib['population']} & {lib['mean_tasks_passed']:.3f} & {lib['anchor_tasks_passed']} " + r'\\')
    lines += ['', '- 锚点为原GPT-OSS task-20的最后可执行方案。保留布局、数值、字符串、键集合及数组长度，仅改变其中已出现的布尔叶子；省略字段继续省略。calculator/GPT-5锚点没有显式布尔字段，所以它的切片只有原配置一个，不能说整个接口没有选择。',
        '- 统一评分task-4/8/12/16/20；调用前冻结的枚举/抽样种子与配置列表均保留。编译失败计失败，不补抽。样本中的最好配置只是事后找到的见证，不能当作无需评测的生成基线。',
        f"- {toggle['audit']['unique_reports']}份不同页面/任务报告中，{toggle['audit']['reused_reports']}份精确复用第21节，{toggle['audit']['new_reports']}份新增。相同页面的多配置仍按配置分布计权，但不是独立浏览器样本。",
        f"- 新找到此前没有见证的配对{len(toggle['new_witnesses'])}项；逐项及通过方案见`test/results/library-toggle-control.json`。没有找到见证不等于不可达；完整枚举结论也仅限这个锚点切片和评分环境。", '',
        '**目前明确的是**：可以在模型自建的接口上量化保留结构后的配置敏感性，并给出可复算见证。**还不能确认的是**：全模式上界、非布尔结构变化后的表现、未见交互需求或模型规划必要性。', '',
        '入口：`test.library_toggle_control.analyze`，协议见`test/library_toggle_control/PROTOCOL.md`。']
    replace_section(23, '\n'.join(lines))

    def endpoint(prefix, method, scope, label='final'):
        return next(r for r in factorial['aggregates'] if (r['prefix'], r['method'], r['scope'], r['label']) == (prefix, method, scope, label))
    lines = ['## 24. 同库累计需求下的前缀×输出形式对照（2026-11-14）', '',
        '**结论先行**：新阶段统一需求、库源码、feature元数据、方案模式与输出上限，并将两种方法的自身历史都表示为完整HTML。下表分别报告当前任务与全部历史断言，不能与旧120配对的四协议表直接合并。', '',
        '| 前缀 | 做法 | 首次输出当前任务 | 最终当前任务 | 首次输出全部历史 | 最终全部历史 |', '|---|---|---:|---:|---:|---:|']
    factorial_tex = []
    for p in ('self', 'reference'):
        for method in ('free_lib', 'plan'):
            values = [endpoint(p, method, scope, label) for scope, label in (('current', 'first'), ('current', 'final'), ('history', 'first'), ('history', 'final'))]
            lines.append(f"| {'自身' if p == 'self' else '参考'} | {'同库代码' if method == 'free_lib' else '方案'} | " + ' | '.join(frac(v) for v in values) + ' |')
            factorial_tex.append(f"{'Self' if p == 'self' else 'Reference'} & {'Code' if method == 'free_lib' else 'Plan'} & " + ' & '.join(frac(v) for v in values) + r' \\')
    lines += ['', '### 24.1 参考前缀与协议开发记录', '',
        f"- 初始布局与此前全部任务文件在20张原参考输入页上共{prefix['pairs']}个配对、{prefix['tests']}条断言，分别{prefix['passed_pairs']}与{prefix['passed_tests']}通过。保留{prefix['unique_raw_reports']}份报告，不排除失败断言；入口`test.prefix_history_audit.analyze`。这验证所列断言，不是自然语言行为的形式证明。",
        '- 首个实现遗漏了方案顶层字段的明确结构，公开编译反馈暴露持续嵌套/类型歧义。在任何隐藏评分前关闭旧阶段，保留120份已结算调用、55个完整候选链及其他中断候选记录。另立v2向两种做法共同提供明确模式；输入改变，旧代码候选也不复用。修订发生在观察格式输出之后，因此是探索性协议修正，不冒充确认性预注册。',
        '- 正式v2为GPT-OSS-120B low/Near AI与Mistral Small 3.2/DeepInfra，2模型×2前缀×2做法×20任务=160候选。参考条件的40组user消息逐字相同；自身条件的输入页来自各自上一可执行输出。两种方法都有完整库源码和累计需求，均12000输出token、最多两次公开修复。',
        '- 首次输出指version-0，若未编译则为失败；最终指公开修复流程保留的最后可执行版本，未按隐藏分数挑选。所有160候选在任何正式隐藏评分前冻结。当前task文件与init+task-1..task-k分别评分；首个决定性失败后停止，不报告被截断的断言平均数。', '',
        '### 24.2 分模型结果与边界', '',
        '| 模型 | 前缀 | 做法 | 当前任务 | 全部历史 |', '|---|---|---|---:|---:|']
    for model in ('openai/gpt-oss-120b', 'mistralai/mistral-small-3.2-24b-instruct'):
        for p in ('self', 'reference'):
            for method in ('free_lib', 'plan'):
                selected = [r for r in factorial['groups'] if (r['model'], r['prefix'], r['method'], r['label']) == (model, p, method, 'final')]
                values = [next(r for r in selected if r['scope'] == scope) for scope in ('current', 'history')]
                lines.append(f"| {'GPT-OSS' if 'gpt-oss' in model else 'Mistral'} | {p} | {method} | {frac(values[0])} | {frac(values[1])} |")
    lines += ['', f"当前任务与历史全过不一致的最终候选有{len(factorial['endpoint_divergences'])}个，逐项原报告都保留。全部首次/最终及两端点共{factorial['audit']['comparisons']}项比较，去重为{factorial['audit']['unique_raw_reports']}份页面/测试集合报告；配对胜负、序列分数、调用token与供应商记录见`test/results/prefix-factorial.json`。", '',
        '当前通过但历史失败时，历史执行中首个决定性失败分布如下；相同失效会在后续前缀重复，不能视为独立缺陷数：', '',
        '| 做法 | 历史测试文件 | 断言 | 候选数 |', '|---|---|---|---:|']
    for failure in proof['prefix_factorial']['earlier_failure_groups']:
        lines.append(f"| {failure['method']} | {failure['file']} | {failure['title']} | {failure['n']} |")
    lines += ['',
        '**目前明确的是**：这个新对照匹配了累计信息和参考输入，历史兼容性也有独立检验。**还不能确认的是**：纯错误继承因果效应、更多模型/种子和跨项目优势；参考页同时改变质量与来源，输出形式也包含编译合同差异。原库由参考实现和人工槽位构成，本结果不能替代模型自建库或非模板迁移证据。', '',
        f"今天所有新增付费阶段，包括中止的协议开发，已结算${cost['settled_usd']:.6f}、保守敞口${cost['exposure_usd']:.6f}；授权$20。正式前缀阶段${factorial['cost']['settled_usd']:.6f}，中止阶段${factorial['abandoned_protocol_cost']['settled_usd']:.6f}。只读账本入口：`test.authorized_costs --date 20261114`；此前未知预留继续留在旧账本，不计为零。", '',
        '独立复算三批结果及费用：`test.replay_nov14`。原始评分不会因论文排版或结果分析改变。']
    replace_section(24, '\n'.join(lines))

    tex = [r'\section{Completed Library Interventions and Matched Prefixes}', r'\label{app:nov14}', '',
        r'\subsection{Completing the six-library intervention}',
        'A separately budgeted continuation obtains the six missing responses for the table/Sonnet and two BOM libraries. The six already complete responses, including strict-format failures, are copied unchanged. Prompts, models, provider constraints, seeds, reasoning and token limits are unchanged; no previous candidate scores enter a revision request. The three-pair results in \\cref{app:library-repair} had already been observed, so this is a disclosed continuation, not a new preregistered replication.',
        f"All twelve responses are frozen before the combined replay. Its 180 old candidates, fixed controls and development checks yield {full['audit']['comparisons']} comparisons over strict and single-fence parsing, with {full['audit']['unique_browser_scores']} distinct page/task reports ({full['audit']['reused_browser_scores']} exact prior reports reused; {full['audit']['new_browser_scores']} newly scored). Schema, descriptions and examples remain unchanged, without guaranteeing semantic equivalence. Target requirements were visible at construction, and cumulative development/evaluation semantics overlap.", '',
        r'\begin{table}[h]\centering\small',
        r'\caption{Completed six-library replay. Main pools the two original planners; GPT-5 is separate. Old outputs are fixed, so these are implementation-intervention outcomes, not new planning accuracy.}',
        r'\begin{tabular}{@{}lllrrr@{}}\toprule Format & Cohort & Output & Original & Review & Feedback \\ \midrule',
        *repair_tex, r'\bottomrule\end{tabular}\end{table}', '',
        f"{len(fallback)} responses fall back to the original package under the strict contract; {sum(r['single_fence_extracted'] for r in fallback)} are compilable under the previously fixed single-fence diagnostic. Both are reported, without selecting the better convention. In the single-fence main-plan feedback condition, {secondary['wins']} gains and {secondary['losses']} regressions offset each other: repairs do not provide a general improvement. Among {full['audit']['unchanged_comparisons']} comparisons with byte-identical old pages, {len(full['audit']['unchanged_score_mismatches'])} differ in outcome; all observations are retained. The continuation settles \\${full['cost']['settled_usd']:.6f}; earlier interrupted-call reservations remain separate.", '',
        r'\paragraph{A packaging regression.} Both Sonnet table revisions omit the \code{index.js} placeholder, although their compilers generate the entry module only while visiting that key. A post-hoc intervention freezes the original GPT-OSS task-4 plan and six pages: original, original without its entry module, each revision, and each revision with only the original placeholder restored before compilation. Other output files remain byte-identical within each intervention pair; the original implementation is not copied into the revised page.',
        r'\begin{table}[h]\centering\small\begin{tabular}{@{}lcc@{}}\toprule Page & Entry present & Task 4 passes \\ \midrule',
        *[f"{r['name'].replace('_', ' ')} & {'Yes' if r['entry_present'] else 'No'} & {'Yes' if r['passed'] else 'No'} " + r'\\' for r in entry['rows']],
        r'\bottomrule\end{tabular}\caption{Single fixed-plan entrypoint intervention. Three exact earlier reports are reused; three new pages are scored. This post-hoc case does not change any model result or establish a general repair mechanism.}\end{table}', '',
        r'\subsection{Conditional Boolean configuration controls}',
        'For each original model-built library, we keep the saved GPT-OSS final plan as an anchor and vary only its explicitly present Boolean leaves. Non-Boolean values, object keys and array lengths stay fixed. We exhaust slices with at most five Boolean leaves and otherwise uniformly sample 32 distinct assignments with a fixed seed. The same configurations are evaluated on task files 4/8/12/16/20. Missing optional fields remain absent; notably, the GPT-5 calculator anchor has no explicit Boolean field. This is not uniform sampling of the complete plan language.', '',
        r'\begin{table}[h]\centering\small',
        r'\caption{Original-library Boolean slices. Mean and anchor counts are tasks passed out of five. Configuration outcomes share applications and sometimes exact pages; they are not independent applications.}',
        r'\begin{tabular}{@{}llrrrr@{}}\toprule Project & Builder & Bits & Tested / slice & Mean & Anchor \\ \midrule',
        *toggle_tex, r'\bottomrule\end{tabular}\end{table}', '',
        f"The {toggle['audit']['configurations']} configurations produce {toggle['audit']['comparisons']} comparisons and {toggle['audit']['unique_reports']} distinct reports, including {toggle['audit']['reused_reports']} exact reused reports. The search adds {len(toggle['new_witnesses'])} new witnessed pairs: the union is {toggle['union_witness_pairs']}/120, compared with {toggle['historical_witness_pairs']}/120 previously; historical scores remain unchanged. A best sampled configuration is only a post-hoc search witness; failure to find one is not a proof of unreachability. Exhaustive claims apply only to the three fixed-anchor slices.", '',
        r'\subsection{Matched cumulative information and reference prefixes}',
        f"We first audit the original twenty starting pages against initial-layout assertions and every earlier task file: all {prefix['pairs']} page/file pairs and {prefix['tests']} assertions pass. This extends the earlier last-task-only calibration without asserting a formal specification guarantee.",
        'The new factorial crosses self-generated versus reference-prefix HTML with unrestricted same-library code versus checked plans. Both outputs receive identical cumulative requirements, feature metadata, full library source and plan schema; reference-prefix user messages are byte-identical. Self-prefix plans pass their compiled HTML onward, matching the history representation of code. Two planners (GPT-OSS low and Mistral Small), twenty tasks and four conditions yield 160 candidates, each with a 12,000-token cap and at most two public repairs. All generation ends before hidden grading.',
        r'Both endpoints evaluate the same current candidate $C_k$. Let $T_j(C_k)$ mean that every assertion in task file $j$ passes on that page, with $T_0$ denoting initial layout. We measure',
        r'\[ I_{\mathrm{current}}(k)=\mathbf{1}\{T_k(C_k)\},\qquad I_{\mathrm{history}}(k)=\prod_{j=0}^{k}\mathbf{1}\{T_j(C_k)\}. \]',
        'An initial implementation omitted the explicit flat plan-object shape and produced repeated public compiler failures. It was stopped before hidden grading, retaining 120 paid calls and 55 completed candidate chains. The corrected protocol shares an explicit schema with both output methods and regenerates all candidates. Because this correction followed format observations, this is exploratory protocol development, not an untouched preregistration; the abandoned costs and outputs are retained.', '',
        r'\begin{table}[h]\centering\small',
        r'\caption{Matched-prefix factorial, pooled descriptively over two models. Initial compilation failures count as first-output failures; final uses the last executable public-repair version. History requires init and every task file through the current task.}',
        r'\label{tab:prefix-factorial}',
        r'\begin{tabular}{@{}llrrrr@{}}\toprule & & \multicolumn{2}{c}{Current task} & \multicolumn{2}{c}{Full history} \\ Prefix & Output & First & Final & First & Final \\ \midrule',
        *factorial_tex, r'\bottomrule\end{tabular}\end{table}', '',
        r'\begin{figure}[h]\centering',
        r'\includegraphics[width=\textwidth]{figures/matched_prefix_endpoints.pdf}',
        r'\caption{Final outputs under matched cumulative information. Each row is one dependent twenty-task sequence. Current-task and full-history checks use separate executions; every observed endpoint is retained, including any timing disagreement.}',
        r'\label{fig:matched-prefix-endpoints}\end{figure}', '',
        f"Current and historical assertions are scored separately, stopping at the first decisive failure for exact candidate-level outcomes. {factorial['audit']['comparisons']} first/final endpoint comparisons use {factorial['audit']['unique_raw_reports']} distinct page/test-set reports; {len(factorial['endpoint_divergences'])} final candidates differ between endpoints, with every raw observation retained. This single-seed, two-model, single-project study does not identify a pure causal effect of inherited errors: reference pages also change implementation quality and source, and output form includes compilation constraints. It uses the original supplied library and does not establish autonomous abstraction or cross-project transfer.",
        f'In this run all endpoint disagreements are current-task passes with historical failures. First decisive plan failures are: {plan_failure_text}. These are repeated observations along dependent prefixes, not independent defects. Coverage checks therefore do not establish preservation of earlier interaction semantics.',
        f"The corrected factorial settles \\${factorial['cost']['settled_usd']:.6f}, and its abandoned protocol-development stage \\${factorial['abandoned_protocol_cost']['settled_usd']:.6f}. Across the November 14 continuation and new stages, settled cost is \\${cost['settled_usd']:.6f} and exposure \\${cost['exposure_usd']:.6f}, below the \\$20 authorization. Prior unresolved reservations are not discarded or counted as new calls. Independent reconstruction reads saved raw reports and ledgers; it is not a replay of every browser trajectory."]
    (ROOT / 'DNA_latex/nov14_study.tex').write_text('\n'.join(tex) + '\n')
    print('Updated sections 22–24 and local paper appendix')


if __name__ == '__main__':
    main()
