"""Render November 15 result tables from independently checked saved summaries."""
from collections import defaultdict
import argparse,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
METHOD={'free':'无库代码','free_lib':'同库代码','dna':'方案+检查','dna_unchecked':'方案无覆盖检查','plan':'方案','rule':'固定规则',
 'control/example':'固定示例','control/final':'固定最终方案',
 'control/example-0':'固定示例0','control/example-1':'固定示例1','control/final-plan':'固定最终方案'}
COHORT={'expert':'原供应库','interface':'自建库两项目','expansion':'自建库三项目','frontier':'GPT-5小试'}
SHORT={'openai/gpt-5':'GPT-5','anthropic/claude-sonnet-4.5':'Sonnet','openai/gpt-oss-120b':'GPT-OSS','mistralai/mistral-small-3.2-24b-instruct':'Mistral'}

def read(name):return json.loads((ROOT/'test/results'/name).read_text())
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|',*['| '+' | '.join(map(str,r))+' |' for r in rows]])
def tex(value):return str(value).replace('_',r'\_').replace('&',r'\&').replace('%',r'\%')
def latex_table(caption,label,headers,rows,align=None):
 align=align or 'l'*len(headers)
 return '\n'.join([r'\begin{table}[ht]',r'\centering\small',r'\caption{'+caption+'}',r'\label{'+label+'}',
  r'\begin{tabular}{@{}'+align+r'@{}}',r'\toprule',' & '.join(headers)+r' \\',r'\midrule',
  *[' & '.join(tex(v) for v in row)+r' \\' for row in rows],r'\bottomrule',r'\end{tabular}',r'\end{table}'])

def history_sections(h,d,w):
 final=[g for g in h['groups'] if g['level']=='overall' and g['label']=='final']
 rows=[[COHORT[g['cohort']],g['project'],METHOD.get(g['method'],g['method']),g['n'],
     g['old_current_passed'] if g['old_current_available'] else '未测',g['history_passed'],g['old_current_pass_history_fail'],g['old_current_fail_history_pass']] for g in final]
 text=f'''## 25. 既有Web-Bench页面的完整历史复验（2026-11-15，零API）

**结论先行**：当前测试文件通过不能替代完整历史行为通过。本轮按预先固定的旧候选集合，重评同一页面的init与task-1..k；旧当前文件成绩保留，下表并列新端点，不回写历史主表。不同建库协议继续分开报告。

### 25.1 范围、兼容性与校准修正

- 原dom1主七模型四做法560候选，加只计一次的20规则页；原两项目自建库400、新三项目600、GPT-5小试60，共1640个候选/规则页面记录（其中1620为模型候选）。首次/最终共3280端点，另加730固定控制，共{h['comparisons']}项比较、{h['unique_jobs']}份按项目/运行器/全部源文件/测试集合去重的原始浏览器报告。首次沿用旧协议的首次可执行版本，不冒充原始第一条模型响应。
- 原dom1使用Playwright1.63及原12s/3s超时，两项目用1.63及30s/5s，三项目和GPT-5用1.57及30s/5s；每页一个worker、零重试，首个决定性失败停止，只报告精确的页面全过，不计算被截断的断言平均分。BOM单队列串行。
- 六套真正最终参考页的init与全部20文件均过。初始准备误把原朴素rule/task-20控制标作正参考，该页原当前任务仅8/20；其失败校准完整保留。任何候选评分前，另立REFERENCE协议，调用原正确reference_plan及冻结库/编译器生成真实最终页并通过21文件。其他五页为对应官方最终参考页。此前原dom1中间参考前缀210配对/909断言校准另见第24节。
- 初始范围清单还漏列60个GPT-5固定示例端点，在校准及候选评分前补齐；旧草稿和最终清单均保留。不存在看候选失败再删断言。最终参考全过是兼容性见证，不是每个中间参考页的全量校准，也不是自然语言语义证明。

### 25.2 最终页的两个端点

{table(['阶段','项目','做法','n','旧当前过','新历史过','当前过/历史不过','反向差异'],rows)}

“反向差异”是旧当前任务失败但新完整历史通过；两次运行日期/调度不同，不能将它抹去或解释成逻辑蕴含失效。所有首次与最终、逐建库者/规划者结果见`test/results/history-replay.json`。

### 25.3 失败结构与结论边界

最终模型/规则页中，旧当前通过且新历史失败的观测有{d['discordant_final_observations']}项；其中{d['with_earlier_assertion_failure']}项首先观测到更早任务或初始布局失败（其中{d['with_initial_file_failure']}项是init），{d['with_same_sequence_earlier_page_history_pass_witness']}项在同一原序列的更早页面存在本次完整历史全过见证。首次失败遵循Playwright文件顺序，不等于需求时间顺序；重复前缀和相同源码不是独立缺陷，也不是纯遗忘因果实验。逐断言、不同源码数及原方案变体统计在`history-replay-diagnostics.json`。

**目前明确的是**：可以在不重抽模型、不改旧库和页面的情况下区分当前任务成功与累计行为保留；原当前分数不能当成完整应用正确率。**还不能确认的是**：未见自然语言需求泛化、完整库可达上界，以及由相邻页面差异唯一导致的错误继承。更多相关前缀不能替代独立项目。

入口：`test.history_replay.analyze`、`test.history_replay.diagnostics`、`test.replay_nov15`。冻结范围与正参考修正见`test/history_replay/README.md`，全部原报告另存`artifacts/history-replay-20261115`。
'''
 englishrows=[[g['cohort'],g['project'],g['method'].replace('control/','fixed '),g['n'],
   g['old_current_passed'] if g['old_current_available'] else '--',g['history_passed'],g['old_current_pass_history_fail'],g['old_current_fail_history_pass']] for g in final]
 appendix=r'''\section{Complete-History Replay of Saved Web-Bench Pages}
\label{app:history-replay}
We fix 1,640 original candidate/rule records: 560 supplied-library model candidates plus 20 shared rule pages, 400 candidates from the two-project interface study, 600 from the three-project study, and 60 GPT-5 medium candidates. First/final endpoints contribute 3,280 comparisons; 730 fixed controls bring the total to 4,010. These are repeated, dependent endpoints, not 4,010 independent tasks. Deduplication uses project, runtime, every served source file and the exact test set, yielding 1,650 browser jobs.

For page $C_k$, the history endpoint requires the initial test file and every task file through $k$ to pass on that same immutable page. It does not combine scores from different pages. We retain the original current-file observations from saved reports, and preserve all reverse discrepancies across run dates. First means the first executable version under the original protocols. Expert-domain pages use the original Playwright 1.63 timeouts (12\,s/3\,s); interface pages use 1.63 with 30\,s/5\,s; expansion and frontier pages use 1.57 with 30\,s/5\,s. There are no retries, BOM is serial, and a decisive failure stops a job; truncated assertion means are not reported.

\paragraph{Preparation and calibration.} A preparation draft omitted 60 fixed-example endpoints, corrected before calibration or candidate grading. The initial calibration also mislabeled the old weak rule's final page as an expert positive reference. Its failures are retained. Before any candidate grading, an additive protocol generated the true final reference from the original reference-plan function, frozen library and compiler; all 21 files passed. Five official final reference pages also passed all 21 files each. These are compatibility witnesses, not formal semantic proofs or calibration of every intermediate reference prefix. The earlier 210-pair intermediate-reference check remains separate (\cref{app:nov14}).
'''
 appendix+='\n'+latex_table('Final-page historical current-file observations and new same-page complete-history outcomes. Protocols remain separate; reverse differences are retained. Fixed controls without historical current observations show dashes.',
  'tab:history-replay',['Cohort','Project','Method','$n$','Old current','History','Current only','Reverse'],englishrows,'lllrrrrr')
 appendix+=f'''\n\\paragraph{{Failure descriptions.}} There are {d['discordant_final_observations']} final model/rule endpoints with historical current success and new history failure. Of these, {d['with_earlier_assertion_failure']} first expose an earlier-file/layout failure, and {d['with_same_sequence_earlier_page_history_pass_witness']} have an earlier page in the same saved sequence that passes the applicable full history in the new replay. Of the discordances, {d['with_initial_file_failure']} first fail the initial file; baseline defects, layout assertions and later interactions all contribute to this endpoint. These observations are correlated; the first observed failure follows test-runner file order, and neither count identifies independent defects or pure error inheritance. All source maps, raw reports and per-builder/model first/final outcomes are retained.\n'''
 wrows=[[r['project'],SHORT[r['builder']],f"{r['with_observed_witness']}/{r['n']}",', '.join(r['witness_tasks']) or '无'] for r in w['libraries']]
 text+='\n### 25.4 合法方案的完整历史见证（事后、零API）\n\n'
 text+=f"同样六库与20个前缀共120配对，在已存合法方案和固定控制中找到{w['with_observed_witness']}/120个完整历史通过见证；旧53/120只对应当前文件，两者不混用。所有正见证页从原冻结包及方案重新编译逐字核对，没有搜索新配置或重跑浏览器。主240方案的214个历史失败中，仅2个有其他合法页的完整历史见证，212个仍未知；未知不是不可达证明。\n\n"
 text+=table(['项目','建库者','完整历史见证配对','任务'],wrows)+'\n\n入口`test.history_replay.witnesses`；证据与逐候选分类在`history-replay-witnesses.json`。\n'
 appendix+=f"\n\\paragraph{{Observed legal-plan witnesses.}} Recompiling saved successful plans and fixed controls byte-for-byte against their original packages yields {w['with_observed_witness']}/120 witnessed library--prefix pairs under complete history, separate from the old 53/120 current-file bound. Among 214 failed final main plans, two have another legal full-history witness and 212 remain unclassified. No new configurations or browser runs are introduced; missing witnesses do not establish impossibility.\n"
 return text,appendix

def transfer_sections(t,cost):
 groups=[g for g in t['groups'] if g['level']=='aggregate']
 rows=[[g['project'],g['condition'],METHOD[g['method']],g['label'],f"{g['all_passed']}/{g['n']}",f"{g['passed_cases']}/{g['total_cases']}"] for g in groups]
 controls=[]
 for lib in t['libraries']:
  deployed=next(r for r in lib['controls'] if r['deployed_control'])
  fixed=[r for r in lib['controls'] if r['fixed_example']]
  controls.append([lib['project'],SHORT[lib['builder']],lib['condition'],len(lib['attempts']),f"{lib['development_passes']}/{lib['development_total']}",
    '/'.join(str(r['passed_cases']) for r in fixed),deployed['passed_cases'],'是' if lib['finite_subset_witness'] else '否'])
 text=f'''## 26. 局部开发原语到完整交互序列（2026-11-15，独立合成诊断）

**结论先行**：本批用外部规格固定两个应用的原语和共享状态语义，开发只给三份局部需求，留测改为完整应用上的交错轨迹。比较直接可配置页面与共享状态契约提示，保留整编译器可直接复用的代码、无库代码、固定示例和确定性合并。它补充第19节二元模板之外的交互证据，但只有两个熟悉来源应用，不构成跨未知项目泛化或新抽象学习算法。

### 26.1 来源、边界与先行校准

- TodoMVC公开规格blob `d040877fd8895c4f18fa5190e4b8ee474ffa8ac4`；js-framework-benchmark README blob `5472130a7d9ca1ffe9cc9f5d31542ed78e6bfcf5`。来源链接/获取回执与适配约定见`test/interaction_transfer/SOURCES.md`。本批不是两个来源的官方分数，不是官方Web-Bench任务，也不测行表性能。固定行标签、单调ID、交换位置和DOM选择器均为明确适配。
- 建库者仅见三个局部开发需求与公开检查，不见完整目标、隐藏轨迹、期望或参考源码。模型负责整页HTML/CSS/JS、接口与编译器，没有提供人工函数列表、状态字段、槽位或外壳；允许额外工作功能，不靠禁止额外按钮制造固定控制失败。
- 每应用一个完整目标、12条交错轨迹。todos检查滤后编辑/删除、重复文本身份、计数与未提交草稿持久化等；rows检查批量创建/追加/每十行更新/选择/交换/删除时的keyed DOM身份。24轨迹相关，不是24个独立应用或任务。
- 付费前参考实现通过12个公开场景及24个隐藏轨迹；两张空白页均失败。预定语义突变todos可见索引删除11/12、草稿持久化10/12、rows整树重建0/12，三种缺陷都被检出。评测器与参考代码分开，但均由AI辅助编写，不等于独立人工审计。

### 26.2 建库与生成结果

两建库者GPT-5 medium/Sonnet4.5×两提示direct/contracts×两应用=8库，均通过3/3开发需求。两提示实际token和修复次数不同，不声称实际计算量严格相等。每库最多3次20000-token响应；首个开发全过即冻结，否则保留最后可编译及失败。contracts是提示层过程对照，不把其名称当成已验证的不变量。

每库×两规划者GPT-5 medium/GPT-OSS120B low×方案/同库代码=32，另4份无库代码，共{t['distinct_candidates']}个不同候选。两同库做法user输入逐字相同，代码可一行调用整个冻结编译器。每候选最多3次8000-token响应，只给格式/加载反馈。全部36候选完成后才冻结评分，共{t['comparisons']}个首次/最终/控制端点，去重为{t['raw_reports']}份12轨迹报告。首次指原始version-0，无法编译计失败；最终是最后可执行，未用隐藏成绩挑选。

{table(['应用','建库提示','做法','首次/最终','应用全过','相关轨迹通过'],rows)}

### 26.3 不调用模型的控制

{table(['应用','建库者','提示','建库响应数','开发需求过','三个固定示例各过/12','三例合并过/12','有限子集完整见证'],controls)}

每库7个非空开发示例子集的合并全部在评分前冻结，共56控制。对象递归、数组稳定并集、标量冲突拒绝；三例全合并是预定可部署控制，任意子集成功仅算有限可达见证，不作为依赖隐藏分数的最优基线。固定示例可能已经实现完整应用，必须保留其成功。

### 26.4 费用、输出上限与还不能确认的事

建库11调用结算${t['costs']['build']['settled_usd']:.6f}，生成40调用${t['costs']['generation']['settled_usd']:.6f}；这两个阶段合计${t['costs']['build']['settled_usd']+t['costs']['generation']['settled_usd']:.6f}，无未知新预留，两本账本stop=0。今天另含下述探索性强基线，合计费用见26.6。原第三轮仍暂停，旧未知预留不改。建库请求配置12/11.5被底层Ledger收紧到实际cap10/stop9，未放宽账本。

共有{len(t['truncated_responses'])}个响应以length结束，逐请求路径/模型/推理token见`interaction-transfer.json`。这包括首次失败与后续修复，不能将长度截断直接解释成语义规划差异。候选token上限包含推理，同库编译器复用也降低代码输出量。

**目前明确的是**：开发输入、目标、隐藏交互序列与固定控制可分别审查，强同库复用和无需逐任务模型决策的对照能解释部分成功。**还不能确认的是**：两种提示的普遍优劣、真正的抽象发现、独立项目迁移或完整行为保证。后续优先独立需求来源和充分行为/工具反馈；不能通过重复本批轨迹增加表面样本数。

零API入口：`test.interaction_transfer.analyze`、`test.replay_nov15`、`test.authorized_costs --date 20261115`。冻结源码与依赖在`artifacts/interaction-transfer-calibration-20261115/frozen.json`；隐藏失败不反馈给原库或候选。
'''
 englishrows=[[g['project'],g['condition'],g['method'],g['label'],f"{g['all_passed']}/{g['n']}",f"{g['passed_cases']}/{g['total_cases']}"] for g in groups]
 controlrows=[[*r[:3],r[3],r[4],r[5],r[6],'yes' if r[7]=='是' else 'no'] for r in controls]
 appendix=r'''\section{Development Primitives to Held-Out Interaction Sequences}
\label{app:interaction-transfer}
This is a new synthetic diagnostic derived from the public TodoMVC specification~\citep{todomvc} and js-framework-benchmark specification~\citep{jsframeworkbenchmark}; it is not an official score on either source or Web-Bench. We record source blobs and all adaptations. The row-table adapter fixes deterministic labels, increasing IDs, swap positions and update suffixes, retains 1,000/10,000-row operations, and tests keyed DOM identity without benchmarking performance. Only two familiar source applications are represented.

\paragraph{Construction information.} Builders see three local development requirements and their public behavior checks per application. They do not see the full target description, hidden trajectories, expected outputs or reference source. They produce all page files, a closed JSON schema, documentation, three development plans and a compiler. No human-authored function list, state fields, plan slots or shell is supplied. Extra working features are allowed, so development examples may already solve the full application. Two prompt conditions request either direct configuration or composable operations/shared-state contracts; this is a prompt-level construction contrast, not a new abstraction-learning algorithm or proof of invariants.

\paragraph{Calibration and generation.} Before paid calls, references pass all 12 public scenarios and 24 hidden trajectories. Blank pages fail; fixed mutations for visible-index deletion, draft persistence and DOM-node replacement pass 11/12, 10/12 and 0/12 trajectories, respectively. Both the reference and independent state-oracle implementation are AI-assisted, not independently human-audited. Two builders (GPT-5 medium and Sonnet 4.5), two prompts and two applications yield eight libraries. Each allows three responses of at most 20,000 tokens with public development feedback; the first development-complete package is frozen. All eight pass 3/3 development requirements, using 11 responses in total. Equal limits do not imply equal actual computation.

Two generators (GPT-5 medium and GPT-OSS-120B low) produce plans and unrestricted same-library code for each library, plus four shared no-library candidates: 36 candidates. Both same-library methods receive byte-identical user input, and code can call the entire frozen compiler. Each candidate permits three 8,000-token responses with format/load feedback only; all candidates finish before any hidden scoring. First denotes raw version-0, including compilation failure; final denotes the last executable version. Each application has one full target and 12 correlated held-out interaction trajectories, not 12 independent tasks. The evaluator checks interleaved identity, filtering/editing, global counts, persistence and keyed DOM behavior in fresh browser contexts.
'''
 appendix+='\n'+latex_table('Full-application and related-trajectory outcomes. Each application/condition contains two builders and two generators for each same-library method; no-library candidates are shared across construction conditions.',
   'tab:interaction-transfer',['App','Build prompt','Method','Version','Full app','Trajectories'],englishrows,'llllrr')
 library_rows=[[lib['project'],SHORT[lib['builder']]+'/'+lib['condition'],f"{lib['source_bytes']/1024:.1f}",f"{lib['compiler_bytes']/1024:.1f}",', '.join(lib['schema_properties'])] for lib in t['libraries']]
 appendix+='\n'+latex_table('Frozen model-proposed interfaces and implementation size. Byte counts describe artifacts, not human effort; interface documentation and claimed contracts are model outputs, not proofs.',
  'tab:interaction-library-shape',['App','Builder/prompt','Source KiB','Compiler KiB','Top-level schema fields'],library_rows,'llrrP{7.0cm}')
 appendix+='\n'+latex_table('Development and no-model controls. Fixed columns give trajectories passed by the three unchanged examples. Full merge is prespecified; any-subset success is only a finite reachability witness.',
  'tab:interaction-controls',['App','Builder','Prompt','Calls','Dev.','Fixed examples','Full merge','Any subset'],controlrows,'lllrrlrl')
 appendix+=f'''\n\\paragraph{{Controls and limits.}} Every nonempty subset of the three development plans is recursively merged before hidden scoring (56 controls). Objects merge by key, arrays by stable union, equal scalars persist and conflicting scalars reject. The all-three merge is the deployable control; selecting a successful subset after scoring is not. There are {t['comparisons']} first/final/control comparisons and {t['raw_reports']} distinct complete-source browser reports, each evaluating all 12 trajectories. Construction costs \\${t['costs']['build']['settled_usd']:.6f}; generation costs \\${t['costs']['generation']['settled_usd']:.6f}. All fees are settled, including {len(t['truncated_responses'])} length-terminated responses; output limits include reasoning. The actual construction ledger ceiling is \\$10 (stop \\$9), automatically tightened from the requested \\$12/\\$11.5; the generation ledger ceiling is \\$6. Both ledgers are closed. These data do not establish cross-project significance, general prompt superiority, learned abstractions, or the necessity of model planning.\n'''
 return text,appendix

def exploratory_sections(u,f,cost):
    finals=[r for r in f['rows'] if r['label']=='final'];first=[r for r in f['rows'] if r['label']=='first']
    rows=[[r['project'],SHORT[r['model']],r['label'],r['attempts'],f"{r['development_passes']}/3",f"{r['passed_cases']}/12",'是' if r['all_passed'] else '否'] for r in f['rows']]
    text=f'''### 26.5 观察合并错误后的布尔并集控制（事后，零API）

原预定三例合并为6/8，两套todos/Sonnet库均因标量冲突拒绝。观察聚合结果、接口字段和合并错误后，另冻结对全部8库通用的布尔OR规则；对象/数组及非布尔标量规则不变，不使用目标、隐藏轨迹或评分。它通过{u['passed']}/{u['total']}套库；{u['reused_reports']}份报告按完整源码/项目/轨迹精确复用，{u['new_reports']}份新增。todos/Sonnet/direct仍有非布尔冲突，未继续调规则追求全过。原6/8成绩不回填。

这是探索性诊断，不是预注册强基线。完整目标要求启用已知能力，布尔并集在这里有意义；字段可能有反向极性或互斥关系，不能推广为通用规划器。源码/输入/观察暴露边界见`test/interaction_union/PROTOCOL.md`，结果`interaction-union.json`。

### 26.6 建库级公开反馈的无库完整页（事后，新增独立账本）

原无库候选只得到格式/加载反馈，而建库阶段得到公开开发行为反馈，且单响应上限分别8000和20000。因此观察原结果后，另冻结两应用×两原建库模型GPT-5 medium/Sonnet4.5的4个无库完整页：每响应20000-token、最多3次，执行同一组三个开发需求并反馈，首个开发全过即停。消息包含开发信息和完整目标，不含库/参考或隐藏结果；比原建库阶段多目标信息，不是纯反馈因子。全部4候选生成后才隐藏评分，原36候选不重写。

{table(['应用','模型','首次/最终','总响应数','最终开发需求过','隐藏轨迹过','应用全过'],rows)}

首次完整通过{sum(r['all_passed'] for r in first)}/4，最终{sum(r['all_passed'] for r in finals)}/4。每行的开发通过数是生成结束时的公开观察，不能当作首次版本已经通过。与原GPT-5无库输出分开保留，Sonnet不与原GPT-OSS行混池；不将模型、输出预算和反馈共同变化说成纯库效果。仍没有浏览器工具代理或跨未知应用验证。

新增已结算${f['costs']['settled_usd']:.6f}，全部{f['costs']['calls']}调用均已结算；今日三个付费阶段总计${cost['settled_usd']:.6f}、保守敞口${cost['exposure_usd']:.6f}，均stop=0，低于$20授权。原第三轮不恢复，旧未知预留不变。局部CPU与人工人时未计价。入口`test.development_feedback.analyze`；调用与推理token、供应商、length终止记录见`development-feedback.json`。

'''
    texrows=[[r['project'],SHORT[r['model']],r['label'],r['attempts'],f"{r['development_passes']}/3",f"{r['passed_cases']}/12",'yes' if r['all_passed'] else 'no'] for r in f['rows']]
    appendix='\n'+r'\subsection{Exploratory stronger controls after observing the initial results}'+'\n'
    appendix+=f'''The prespecified strict all-example merge succeeds on 6/8 libraries; the two TodoMVC/Sonnet failures are scalar conflicts before execution. After observing those results and interface fields, we freeze one generic alternative for all eight libraries: Boolean values merge by OR, with all other merge rules unchanged. It succeeds on {u['passed']}/{u['total']} libraries; {u['reused_reports']} reports are reused by exact project/source/trajectory identity and {u['new_reports']} are newly executed. The remaining non-Boolean conflict is retained, without further rule tuning. This is posthoc evidence, and the full-capability target favors monotone unions; it is not a general planner for conflicting or opposite-polarity features.

The original no-library code receives only format/load feedback and 8,000 tokens per response, whereas construction receives public behavior feedback and 20,000 tokens. We therefore add a separately frozen, exploratory no-library baseline on both applications with the two construction models (GPT-5 medium and Sonnet 4.5). It receives the same three public development checks, the full target, and at most three 20,000-token responses. The additional target information differs from library construction, so this is not a pure feedback intervention. All four complete before hidden scoring; no library, reference, hidden outcomes or hidden trajectories enter prompts.

'''
    appendix+=latex_table('Exploratory no-library full pages with construction-scale public development feedback. Development counts describe the final generation state, not necessarily the initial response. These rows are separate from the original 8,000-token comparisons.',
        'tab:development-feedback',['App','Model','Version','Calls','Final dev.','Trajectories','Full app'],texrows,'lllrrrr')
    appendix+=f"\nThis baseline costs \\${f['costs']['settled_usd']:.6f}; all {f['costs']['calls']} calls are settled. The day's three stages total \\${cost['settled_usd']:.6f}, with no new unresolved reservation and all ledgers closed. It supplies public test feedback, not a browser-tool agent, and does not establish broad library or model superiority.\n"
    return text,appendix


def task_only_section(t):
    selected = [g for g in t['groups'] if g['level'] == 'overall' and g['label'] == 'final']
    rows = [[COHORT[g['cohort']], METHOD.get(g['method'], g['method']), g['n'],
             g['old_current_passed'] if g['old_current_available'] else '未测',
             g['history_passed'], g['task_history_passed'], g['old_current_fail_task_history_pass']]
            for g in selected]
    text = f'''\n### 25.5 排除独立init文件的任务历史证据（事后，零API）

观察第25节后发现，三项目中calculator的80个最终方案端点均先在init失败。另冻结`test/history_tasks_only/`，单列task-1..k证据：仍沿用{t['comparisons']}个端点，不修改主指标、原页、库或任一task断言。{t['reused_decisive_reports']}份原报告已有全部task通过或某个task失败的决定性证据，直接复用；{t['new_reports']}份因init中止而未知的报告另执行相同页面的task-1..k。

{table(['阶段','做法','n','旧当前过','init＋历史过','仅task历史过','旧当前失败/仅task历史过'], rows)}

去掉独立init文件并不删除task文件内部的布局或基础行为要求。新增通过说明端点放宽后的行为证据，不是改进方法成绩；复用部分也不是在新日期重新执行。旧当前分数与新报告来自不同时间，反向差异照实保留。本诊断在观察原结果后提出，不能替换预先冻结的完整历史主表，也不识别去掉init的因果效应。原始报告、复用理由及完整分层结果见`history-tasks-only.json`；独立复算包含在`test.replay_nov15`。
'''
    erows = [[g['cohort'], g['method'].replace('control/', 'fixed '), g['n'],
              g['old_current_passed'] if g['old_current_available'] else '--',
              g['history_passed'], g['task_history_passed'], g['old_current_fail_task_history_pass']] for g in selected]
    appendix = f'''\n\\subsection{{Exploratory task-file history without the independent initialization file}}
After observing the history results, we find that all 80 final calculator plans in the three-project cohort first fail the independent initialization file. We freeze a separate diagnostic over the same {t['comparisons']} endpoints. It retains decisive task-file evidence from {t['reused_decisive_reports']} old reports and executes the same saved pages for the remaining {t['new_reports']} reports whose task outcomes were censored by initialization failure. The new test sets contain every task file through $k$, with original assertions, runtimes and timeouts; only the independent initialization file is omitted. No library, candidate or original outcome is changed. Task files can still assert layout and baseline behavior.

This is a posthoc, mixed saved/new evidence endpoint, not a rerun of all pages or a causal effect of deleting initialization checks. The init-plus-history endpoint remains primary. All reverse discrepancies against historical current-task observations are retained, and no model receives either set of outcomes.
'''
    appendix += latex_table('Final-page task-file history diagnostic, separately frozen after the init-plus-history result. Reverse counts are historical current-file failures with task-history success; missing historical observations are not classified as failures.',
        'tab:task-history', ['Cohort', 'Method', '$n$', 'Old current', 'Init + history', 'Task history', 'Reverse'], erows, 'llrrrrr')
    return text, appendix


def main_history_table(h):
    final=[g for g in h['groups'] if g['level']=='overall' and g['label']=='final']
    lines=[r'\begin{table}[t]',r'\centering',r'\caption{Saved-page endpoints under separate Web-Bench protocols. Current-file counts are historical observations; complete history is newly evaluated on the same saved sources. Prefixes and repeated control pages are dependent.}',r'\label{tab:history-main}',r'\begin{tabular}{@{}lrr@{}}',r'\toprule',r'Method & Old current & Full history \\',r'\midrule']
    for cohort,title,methods in [('expert','Supplied dom1 (7 models)',['free_lib','dna']),('interface','Model-built: two projects',['free_lib','plan']),('expansion','Model-built: three projects',['free_lib','plan','control/final-plan'])]:
        lines.append(r'\multicolumn{3}{@{}l}{\emph{'+title+r'}} \\')
        for method in methods:
            selected=[g for g in final if g['cohort']==cohort and g['method']==method]
            assert selected and all(g['old_current_available']==g['n'] for g in selected)
            n=sum(g['n'] for g in selected);old=sum(g['old_current_passed'] for g in selected);new=sum(g['history_passed'] for g in selected)
            name={'free_lib':'Code + library','dna':'Plan + check','plan':'Plan','control/final-plan':'Fixed final plan'}[method]
            lines.append(f'{name} & {old}/{n} & {new}/{n}'+r' \\')
    lines.extend([r'\bottomrule',r'\end{tabular}',r'\end{table}'])
    return '\n'.join(lines)+'\n'


def main():
 p=argparse.ArgumentParser();p.add_argument('--write-docs',action='store_true');a=p.parse_args()
 h=read('history-replay.json');d=read('history-replay-diagnostics.json');t=read('interaction-transfer.json');cost=read('review-20261115-costs.json')
 assert h['complete']
 assert all(s['unsettled_calls']==0 and s['stop_usd']==0 for s in cost['stages'].values())
 hs,ha=history_sections(h,d,read('history-replay-witnesses.json'));ts,ta=transfer_sections(t,cost)
 if (ROOT/'test/results/history-tasks-only.json').exists():
  extra_text,extra_tex=task_only_section(read('history-tasks-only.json'))
  hs+=extra_text;ha+=extra_tex
 es,ea=exploratory_sections(read('interaction-union.json'),read('development-feedback.json'),cost)
 (ROOT/'DNA_latex/history_main_table.tex').write_text(main_history_table(h))
 (ROOT/'DNA_latex/nov15_study.tex').write_text(ha+'\n'+ta+'\n'+ea)
 if a.write_docs:
  target=ROOT/'实验结果.md';old=target.read_text();marker='\n## 25. '
  prefix=old.split(marker)[0] if marker in old else old.rstrip()
  suffix=next((old[m.start():] for m in re.finditer(r'\n## (\d+)\. ',old) if int(m.group(1))>26),'')
  target.write_text((prefix+'\n\n'+hs+'\n'+ts+'\n'+es+suffix).rstrip()+'\n')
 print('Rendered sections 25--26 and local paper appendix from saved observations.')

if __name__=='__main__':main()
