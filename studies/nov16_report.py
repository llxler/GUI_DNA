"""Generate dated result sections and local paper tables from verified summaries."""
from pathlib import Path
from test.history_replay.run import ROOT,read,dump
from test.matched_feedback_frontier.analyze import effective_out


def fraction(group):return f"{group['passed']}/{group['total']}"


def endpoint(data,method,label,name):return data['groups'][f'{method}/{label}/{name}']


def transition(data,method,name,latex=False):
    a=fraction(endpoint(data,method,'first',name));b=fraction(endpoint(data,method,'final',name))
    return a+(r'$\to$' if latex else ' → ')+b


def public(data,method,latex=False):
    row=data['public_summary'][method]
    return f"{row['first_all_passed']}/{row['total']}"+(r'$\to$' if latex else ' → ')+f"{row['final_all_passed']}/{row['total']}"


def main():
    oss=read(ROOT/'test/results/matched-feedback.json')
    gpt=read(ROOT/'test/results/matched-feedback-frontier.json')
    search=read(ROOT/'test/results/schema-search.json')
    reuse=read(ROOT/'test/results/compiler-reuse-audit.json')
    costs=read(ROOT/'test/results/review-20261116-costs.json')
    proof=read(ROOT/'test/results/nov16-replay.json')
    assert oss['candidates']==30 and gpt['candidates']==15 and search['configurations']==158
    assert all(s['stop_usd']==0 for s in costs['stages'].values())
    labels={'free':'无库代码','free_lib':'同库代码','plan':'组装方案'}
    english={'free':'Code','free_lib':'Code + library','plan':'Plan'}
    cohorts=[('GPT-OSS-120B',oss),('GPT-5 medium',gpt)]
    assert all(u['cached_tokens_reported']==u['reasoning_tokens_reported']==u['requests']
        for _,data in cohorts for u in data['usage'].values()),'Disclose missing usage breakdowns before reporting totals'
    resumed=(effective_out()/'continuation.json').exists()
    md=['## 29. 匹配公开反馈与实际编译器复用（2026-11-16）','',
        '本轮把完整目标、公开测试、输出上限和修复机会预先匹配，再分别观察当前文件、留测文件和完整历史。它是看到旧历史结果后的探索性跟进，不能与原全隐藏主表合并，也不是浏览器工具代理或独立来源迁移。', '',
        '### 29.1 输入边界与比较单位','',
        '使用第18节原calculator/table/bom六套冻结库，不重新建库。每项目一个init到task-20的累计完整目标；公开文件固定为init与task-4/8/12/16，所有做法得到相同测试源码和逐文件反馈，其余16个文件不进入本次生成消息。研究者此前看过旧成绩，不能将该划分称为从未见过留测的确认性设计。', '',
        'GPT-OSS-120B low（Near AI）每条件两条生成链，实际发送seed 2026111601/2026111602：方案12、同库代码12、无库6。观察早期账单后、任何本轮隐藏评分之前另冻结GPT-5 medium（OpenAI）补充组，每条件一次：方案6、同库代码6、无库3；GPT-5不发送seed和temperature。无库候选跨建库者共用，不能翻倍计算样本。两个模型分别报告。', '',
        '所有方法每次20,000输出token、首次加最多两次公开反馈修复，公开五文件全过则提前停止；实际调用数、推理与输出量不一定相等。两同库做法user消息逐字相同，代码可以直接调用并修改整个编译器。首次按原始第0响应，最终按最后响应，格式失败计入，不回退到更早可执行版本。两组全部生成后才评分；BOM始终串行。', '',
        '### 29.2 首次与最终结果','',
        '| 模型 | 做法 | 公开五文件全过 | 当前task-20 | 留测16文件全过 | 完整21文件全过 |',
        '|---|---|---|---|---|---|']
    for name,data in cohorts:
        for method in labels:
            md.append('| '+' | '.join([name,labels[method],public(data,method),*[transition(data,method,e) for e in ('current','withheld','history')]])+' |')
    md += ['', '每格为首次→最终；一个页面必须通过相应端点的全部断言，不把被首败截断的测试当作逐断言均值。重复请求、共享库与三个项目均有依赖，不按45个候选做独立项目显著性检验。',
        f'最终可执行页面为{sum(v["final_executable"] for _,d in cohorts for v in d["public_summary"].values())}/45；其余原始格式失败保留在分母。三个GPT-5无库最终页均通过公开五文件，但留测首次决定性失败分别为calculator/task-11的modes、table/task-10的单格选择、BOM/task-10的后退菜单。不能用公开通过代替全部目标通过。', '']
    if resumed:
        continuation=read(effective_out()/'continuation.json')
        md.append(f'GPT-5初始阶段因并发最坏费用预留阈值留下{len(continuation["incomplete_records"])}条不完整链，原账本关闭后另立续补目录与账本。已完整链不重跑，已有响应/公开报告逐字复用、仅缺失请求付费；续补串行，输入与修复上限不变。原/新账本合并，复制请求不重复计费，原阶段未评分。')
    for name,data in cohorts:
        controls=', '.join(f'{e} {fraction(endpoint(data,"fixed_example","control",e))}' for e in ('current','withheld','history'))
        md.append(f'{name}阶段的12个固定文档示例：{controls}；不按成绩选择示例。该阶段保留{data["public_feedback_reports"]}份公开反馈报告、{data["unique_hidden_reports"]}份去重的留测/当前/历史报告。')
        paired=data['method_pairs']['final/history']
        md.append(f'完整历史按项目/库/生成模型/运行标签配对：双方通过{paired["both"]}，仅方案{paired["plan_only"]}，仅同库代码{paired["code_only"]}，双方不通过{paired["neither"]}，共{paired["total"]}对；不把相同库上的重复请求当独立项目。')
    md += ['', '### 29.3 实际用量与费用','',
        '| 模型 | 做法 | 请求 | 输入token | 缓存输入token | 输出token | 其中推理token | length结束 | 结算美元 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,data in cohorts:
        for method in labels:
            u=data['usage'][method]
            md.append(f'| {name} | {labels[method]} | {u["requests"]} | {u["prompt_tokens"]} | {u.get("cached_prompt_tokens",0)} | {u["completion_tokens"]} | {u["reasoning_tokens"]} | {u.get("length_terminated_responses",0)} | {u["cost_usd"]:.6f} |')
    md += ['',f'本次新增API结算${costs["settled_usd"]:.6f}、保守敞口${costs["exposure_usd"]:.6f}；所有本次账本stop=0。原六库建库时间点另有已结算$1.959928、含未知预留$2.735815，不重算为零成本；本表仅列新生成。缓存、响应长度与推理量影响实际费用，相同上限不等于相同计算量；本地运行与人工时间未计价。','',
        '### 29.4 同库代码实际怎样使用编译器','',
        '为解释旧三项目240组完整历史判定中239组一致，另对保留的构建程序做零API执行审计。包装compile时保存调用计划、输入文件及返回文件的独立快照，再核对最终完整源码与原保存页逐字一致。只有输入库未变、计划合法、最终页等于某次冻结编译返回值时，才计为精确合法复用；files形式的运行时复用不推断。包装改变输出或异常的记录独立保留，不能据此认定复用。','',
        '| 队列/版本 | 路径分类 | 记录数 |','|---|---|---:|']
    for group,values in reuse['groups'].items():
        for classification,count in sorted(values.items()):md.append(f'| {group} | {classification} | {count} |')
    md += ['',f'共审计{reuse["cases"]}个记录位置、{reuse["distinct_observations"]}份不同构建观察；这不改变任何浏览器成绩，也不证明自由代码的能力上界或某种调用路径的因果必要性。首次/最终是同一生成链的两个时间点，不能当成独立样本。', '',
        '## 30. 五库非布尔选项与字段省略搜索（2026-11-16）','',
        '这是第27节单库完整枚举以外的有界搜索。每库以两个文档示例和原GPT-OSS/task-20最终方案为锚点，生成单处枚举、整数边界/中点、数组结构及可选字段省略/补入变化；已有布尔值不直接翻转。保留不同锚点，余项按方案SHA-256排序取到每库最多32个。它不是整个模式的均匀随机采样，也不覆盖多处同时变化。', '',
        '| 项目 | 建库者 | 合法候选池 | 实际配置 | 当前task-20通过 | 完整历史通过 |',
        '|---|---|---:|---:|---:|---:|']
    for lib in search['libraries']:
        prefix=lib['project']+'/'+lib['builder']+'/'
        md.append(f'| {lib["project"]} | {lib["builder"]} | {lib["population_size"]} | {lib["selected_count"]} | {fraction(search["groups"][prefix+"current"])} | {fraction(search["groups"][prefix+"history"])} |')
    md += ['',f'全部{search["configurations"]}个配置在评分前冻结，共{search["comparisons"]}项端点比较、{search["unique_reports"]}份去重报告；零API。三个最终参考在两端点全过；calculator/table空白当前失败。BOM空白当前意外通过，原入口在BOM候选评分前停止。单独续评阶段保留该异常，追加空白完整历史失败的负对照后，才串行评原64个BOM配置，未更换原候选或断言。BOM在两组匹配反馈生成/评分结束后运行，原库、原方案和原成绩均保留。', '',
        'BOM task-20三个测试用toBeDefined检查page.frame返回值，null仍通过，随后无frame就提前返回。原空白报告及本地null/undefined matcher探针共同保留；BOM当前通过只能称官方测试通过，不能单独作为目标功能可达见证。其他端点的通过给出对应合法配置的执行见证；搜索失败仍是未知，不能扩展成五库整个schema不可达证明。这里仅评价task-20及完整20任务的历史，不是重新覆盖全部120库/任务配对，因此原53/120当前文件与14/120完整历史见证时间点不回填。', '',
        '## 31. 本轮复验与论文交付范围（2026-11-16）','',
        '上次未完成的正式anonymous-replay-20261115.zip已经补齐：159,991个清单条目、52份匿名账本，11个入口独立解包复算一致；不覆盖旧包、不上传。今天新增实验和诊断另存20261116快照，最终文件数/哈希及独立入口结果以test/results/replay-bundle-20261116-final-2.json与replay-validation-20261116-final-2.json为准。匿名包不包含论文PDF。', '',
        f'本日独立重算入口test.replay_nov16核对{proof["snapshots"]}份源/输入快照、{proof["calibration_reports"]}份参考/空白报告、匹配反馈的公开/隐藏报告、schema搜索和编译器调用观察，并只读核账；匿名重写使用original/exported哈希映射。它重构保存观察，不重新运行每张浏览器页面。', '',
        '新增逐任务图对应旧三项目480张最终方案/同库代码页：53张两个端点都过、130张仅旧当前文件过、297张都不过。240组方法配对的当前文件结果为双方85、仅方案8、仅代码5、双方不通过142；完整历史为双方26、仅代码1、双方不通过213。图中每列是不同保存页，不能当作同一程序的时间演化。', '',
        '论文新增选择与库充分性的区分，修正init被统称为初始布局的表述。另逐格核对明确列出的关键表，包括本轮反馈结果、实际token/费用和配置搜索；实际表数、单元格数、逐格结果与源哈希见paper-cell-audit.json；这不等于全部表格、正文、引用或独立人工审核完成。最新构建/字体/正文页数见paper-format-20261116.json；论文源和PDF仍仅本地，匿名URL与作者最终审核保留待办。', '']
    sensitivity=proof['bom_task20_posthoc_sensitivity']['groups']
    note='另作事后来源敏感性诊断：对第18节所有原主方法统一排除BOM/task-20文件，'
    note+='、'.join(labels[m]+fraction(sensitivity[m]['original'])+'→'+fraction(sensitivity[m]['retained']) for m in ('plan','free_lib','free'))
    note+='。原分数不回填；这只量化该文件对原汇总的影响，不证明其余断言都充分，也不是原预定17文件子集。'
    md.insert(md.index('## 31. 本轮复验与论文交付范围（2026-11-16）'),note+'\n')
    results=ROOT/'实验结果.md';text=results.read_text();marker='\n## 29. 匹配公开反馈与实际编译器复用'
    if marker in text:text=text.split(marker)[0]
    results.write_text(text.rstrip()+'\n\n'+'\n'.join(md))
    tex=[r'\section{Matched Public Feedback on Complete Web-Bench Targets}',r'\label{app:matched-feedback}', '',
        r'This exploratory follow-up uses the original six model-built libraries for calculator, table and BOM. Each target contains all public requirements through task 20. The public split is fixed to the initial file and tasks 4, 8, 12 and 16; every method receives the same test source and per-file failure feedback. The remaining 16 task files do not enter this generation process. The split follows inspection of historical results and is not a researcher-blind confirmatory design. No library is rebuilt.', '',
        r'GPT-OSS-120B low (Near AI) makes two generation chains per condition with transmitted seeds 2026111601 and 2026111602: 12 plans, 12 same-library programs and six shared no-library pages. After observing initial billing and public progress, but before any new hidden scoring, a separate GPT-5 medium (OpenAI) cohort adds one request chain per condition: six plans, six same-library programs and three no-library pages. GPT-5 receives neither seed nor temperature. No-library pages are shared across the two builders and counted once. Model cohorts remain separate.', '',
        r'All methods allow 20,000 output tokens per response and at most two repairs, stopping early only when all five public files pass. Actual computation differs. The same-library user messages are byte-identical; unrestricted code may call and modify the complete compiler. First denotes raw response zero and final the last response, including format failure; no earlier executable version is selected as a fallback. Both cohorts finish generation before new hidden scoring. BOM runs serially.', '',
        r'\begin{table}[h]',r'\centering\small',r'\caption{Matched public-feedback comparison. Each cell is first$\to$final full-page passes. Shared libraries, repeated requests and only three projects limit inference; these are not independent project replicates.}',r'\label{tab:matched-feedback}',
        r'\begin{tabular}{@{}llrrrr@{}}',r'\toprule',r'Model & Method & Public (5) & Current (1) & Withheld (16) & Full history (21) \\',r'\midrule']
    for name,data in cohorts:
        for method in labels:
            tex.append(' & '.join([name,english[method],public(data,method,True),*[transition(data,method,e,True) for e in ('current','withheld','history')]])+r' \\')
    tex += [r'\bottomrule\end{tabular}',r'\end{table}','',
        r'Each endpoint requires every selected assertion to pass on the same immutable page. Initial-file checks include layout and basic behavior. A first decisive failure stops a scoring job, so truncated assertion means are not reported. Twelve fixed documentation examples are also scored without outcome-based selection. These are public-feedback generators, not agents with browser-tool access.', '',
        r'\begin{table}[h]',r'\centering\small',r'\caption{Actual generation use. Cached tokens are included in prompt tokens; reasoning tokens are included in completion tokens. Fees exclude the previously constructed libraries and local compute.}',r'\label{tab:matched-feedback-usage}',
        r'\begin{tabular}{@{}llrrrrrr@{}}',r'\toprule',r'Model & Method & Calls & Prompt & Cached & Completion & Reasoning & Cost (\$) \\',r'\midrule']
    for name,data in cohorts:
        for method in labels:
            u=data['usage'][method]
            tex.append(' & '.join([name,english[method],str(u['requests']),f"{u['prompt_tokens']:,}",f"{u.get('cached_prompt_tokens',0):,}",
                f"{u['completion_tokens']:,}",f"{u['reasoning_tokens']:,}",f"{u['cost_usd']:.6f}"])+r' \\')
    tex += [r'\bottomrule\end{tabular}',r'\end{table}','',
        f"New settled fees are \\${costs['settled_usd']:.6f}, with \\${costs['exposure_usd']:.6f} conservative exposure and all new ledgers closed. The original six-library construction checkpoint separately records \\$1.959928 settled and \\$2.735815 including unresolved reservations. Equal response ceilings and feedback opportunities do not establish equal realized compute or a pure feedback effect relative to the older protocols.",'',
        r'\subsection{Actual build-time compiler reuse}',r'\label{app:compiler-reuse}',
        r'We audit 240 original final same-library programs and the first/final outputs of the 18 new same-library candidates (276 record positions). The pure VM wraps calls to the frozen compiler, snapshots their input plans and files and their returned file maps, then compares the complete final source with the saved page. Exact legal reuse requires unchanged input library files, schema-valid data and a final file map equal to a captured compiler return. In-place edits are detected using independent snapshots. Instrumentation errors or changed outputs are excluded from this classification; files-form runtime reuse is left unclassified.', '']
    group_labels={'original/final':'Original final outputs',
        'matched_oss/first':'GPT-OSS first outputs', 'matched_oss/final':'GPT-OSS final outputs',
        'matched_gpt5/first':'GPT-5 first outputs', 'matched_gpt5/final':'GPT-5 final outputs'}
    class_labels={'exact_legal_frozen_compile':'exact legal compiler reuse',
        'files_output_runtime_reuse_unclassified':'file-form outputs, runtime path unclassified',
        'no_executable_response':'no executable output',
        'other_build_or_uncertified_reuse':'other build or uncertified reuse',
        'exact_outside_schema_compile':'exact compiler reuse outside the schema'}
    for group,values in reuse['groups'].items():
        heading=group_labels.get(group,group.replace('_',' '))
        parts=[f"{class_labels.get(k,k.replace('_',' '))}: {v}" for k,v in sorted(values.items())]
        tex.append(r'\paragraph{'+heading+'} '+'; '.join(parts)+'.')
    tex += ['',r'This is a post-hoc execution-path audit, not a new generation or browser score. It does not establish the capacity of unrestricted code, explain why a model chose a path causally, or prove general compiler equivalence. The corresponding original complete-history outcomes agree in 239 of 240 method pairs (26 joint passes, 213 joint failures and one code-only pass).', '',
        r'\begin{figure}[p]',r'\centering',r'\includegraphics[width=\textwidth]{figures/history_endpoint_map.pdf}',
        r'\caption{Historical current-file versus later same-page full-history outcomes for 480 original model-built pages. Rows identify builder / output method / generator. Each column uses its own saved page $C_k$; it is not a trajectory of a single program. There are 53 joint passes, 130 current-only passes and 297 joint failures. Related tasks and common library implementations make cells dependent.}',r'\label{fig:history-endpoints}',r'\end{figure}','',
        r'\section{Bounded Non-Boolean and Omission Search}',r'\label{app:schema-search}',
        r'After the one-library finite audit, we explore the other five original libraries without API calls. Three anchors per library are its two documentation examples and the original GPT-OSS final-task plan. Schema-only proposals change one enum, an integer boundary/midpoint, an array structure, or optional-field omission/insertion. Existing Boolean leaves are not directly flipped. We retain distinct anchors and take remaining plans in SHA-256 order up to 32 per library. This is neither uniform full-schema sampling nor a search over arbitrary simultaneous changes. All selected plans and compiled sources are frozen before scoring; failed compilation would remain in the denominator.', '',
        r'\begin{table}[h]',r'\centering\small',r'\caption{Bounded five-library search. Current is task 20; full history includes the initial file and tasks 1--20. Configurations are dependent; BOM current-file passes have a known vacuous-test risk; see \cref{app:schema-search}.}',r'\label{tab:schema-search}',
        r'\begin{tabular}{@{}llrrrr@{}}',r'\toprule',r'Project & Builder & Proposal pool & Selected & Current & Full history \\',r'\midrule']
    for lib in search['libraries']:
        prefix=lib['project']+'/'+lib['builder']+'/'
        tex.append(' & '.join([lib['project'],'GPT-5' if lib['builder']=='openai/gpt-5' else 'Sonnet 4.5',str(lib['population_size']),str(lib['selected_count']),
            fraction(search['groups'][prefix+'current']),fraction(search['groups'][prefix+'history'])])+r' \\')
    tex += [r'\bottomrule\end{tabular}',r'\end{table}','',
        f"The 158 selected configurations yield 316 endpoint comparisons and {search['unique_reports']} distinct reports. The unchanged final references pass both endpoints. Calculator/table blank current controls fail. The BOM blank current control unexpectedly passes; the initial runner stops before any BOM configuration is scored. A separately frozen continuation retains this exception, adds a failing blank full-history control and evaluates the unchanged BOM configurations serially after both matched-feedback stages. No original score changes. For other endpoints, a passing legal configuration is an execution witness; failure of this bounded search leaves reachability unresolved. The older 53/120 current-file and 14/120 full-history witness checkpoints are retained rather than replaced by this final-task-only diagnostic.",'']
    tex += ['',r'\paragraph{Vacuous current-file success.} The three official BOM task-20 tests call \code{page.frame("content")}, check \code{toBeDefined()}, then return early when the frame is absent. The missing-frame value is null, which satisfies this matcher. We retain the blank-page browser report and a local matcher probe (null passes, undefined fails). Consequently a BOM current-file pass alone does not certify the target feature. Full history rejects the blank page. This observation concerns these three assertions, not every BOM file or the entire benchmark; historical scores are not silently revised.', '']
    tex += [f"A separate post-hoc sensitivity check excludes BOM task 20 from every original main method: plans change from {fraction(sensitivity['plan']['original'])} to {fraction(sensitivity['plan']['retained'])}, same-library code from {fraction(sensitivity['free_lib']['original'])} to {fraction(sensitivity['free_lib']['retained'])}, and no-library code from {fraction(sensitivity['free']['original'])} to {fraction(sensitivity['free']['retained'])}. Original scores remain intact. This is distinct from the earlier prespecified 17-file subset and does not certify the remaining assertions.", '']
    if resumed:
        tex.insert(3,r'The initial GPT-5 ledger stops admitting requests at its worst-case reservation threshold. After closing it, a separate continuation preserves complete chains and replays settled responses and public reports with exact input checks, paying only for missing requests. Continuation is serial; model, prompts and repair limits are unchanged. Both ledgers are counted once, and neither incomplete generation nor copied calls are treated as new model outcomes. Hidden scoring waits for the complete final cohort.')
    (ROOT/'DNA_latex/nov16_study.tex').write_text('\n'.join(tex))
    main_table=[r'\begin{table}[t]',r'\centering\small',
        r'\caption{Final full-history passes after matched public feedback on complete targets. No-library pages count once across builders. Repetitions share three projects and frozen libraries.}',
        r'\label{tab:matched-feedback-main}',r'\begin{tabular}{@{}lccc@{}}',r'\toprule',
        r'Model & Code & Code + library & Plan \\',r'\midrule']
    for name,data in cohorts:
        main_table.append(' & '.join([name,*[fraction(endpoint(data,m,'final','history')) for m in labels]])+r' \\')
    main_table += [r'\bottomrule\end{tabular}',r'\end{table}','']
    (ROOT/'DNA_latex/matched_feedback_main_table.tex').write_text('\n'.join(main_table))
    print('Wrote result sections 29–31 and local nov16_study.tex')


if __name__=='__main__':main()
