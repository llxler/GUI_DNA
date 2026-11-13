# 第 0 节审稿问题的复验入口

结论统一见 [`实验结果.md` 第 16–21 节](../实验结果.md)，未解决的问题见 [`experiments/TODO.md`](../experiments/TODO.md)。这里记录复现流程，避免把探索性检查误作新主实验。第16节是2026-11-11的历史阶段；2026-11-12用户另授权当天不超过$20，11月13日本次新增授权最多$10。

## 只读汇总与本地复验

```bash
uv run python -m test.review_checks
uv run python -m test.review_metrics
uv run python -m test.random_plans --report
uv run python -m test.ledger_read artifacts/todomvc-blind-2/budget.sqlite3
uv run python -m test.name_sensitivity --no-generate --out artifacts/name-sensitivity-2 --extra-ledgers artifacts/name-sensitivity/budget.sqlite3
uv run python -m test.blind_library --summary --out artifacts/todomvc-blind-2 --extra-ledgers artifacts/todomvc-blind/budget.sqlite3 --planners qwen/qwen3-coder-30b-a3b-instruct mistralai/mistral-small-3.2-24b-instruct deepseek/deepseek-v4-pro-0813 openai/gpt-oss-120b
uv run python -m test.webbench_dna.continue_clean_prefix --no-generate
```

这些汇总入口使用只读账本。**不要为了看费用用很小的 cap 创建 `Ledger` 实例**：它会永久收紧已有阶段的上限。接手时 `todomvc-blind` 和 `name-sensitivity` 已遇到这一问题，本轮另立 `-2` 阶段，复制原始候选并通过 `--extra-ledgers` 复用已结算响应。旧账本不放宽；新目录的 `continuation.json` 记录复制来源和传输失败的归档。

下面只调用本地浏览器，不调用模型。TodoMVC 可在首个官方断言失败后停止，得到准确的「任务全过/不过」；不能把未执行测试当通过，也不汇报这种记录的测试级平均分。

```bash
uv run python -m test.random_plans --suite webbench --workers 3 --browser-workers 1
uv run python -m test.random_plans --suite todomvc --workers 3 --browser-workers 1
WORKERS=1 uv run python -m test.grade_review --stage artifacts/name-sensitivity-2 --workers 3
WORKERS=1 uv run python -m test.grade_review --stage artifacts/todomvc-blind-2 --workers 3
WORKERS=1 uv run python -m test.plan_counterfactuals --workers 1
uv run python -m test.webbench_dna.review_evaluate --stage artifacts/webbench-dna-clean-2 --workers 3
uv run --with matplotlib python -m test.failure_figure
uv run --with matplotlib python -m test.webbench_dna.taskmap_figure
uv run python -m test.export_review_snapshot
```

`taskmap_figure` 默认排除 Web-Bench 传输缺失的 Gemma；`--include-gemma` 可重画历史八模型图。最后一个命令仅准备本地匿名源码与汇总快照，不上传，不包含完整原始候选/响应/账本。完整历史观测包与独立复验入口见本文末节；匿名上传仍属 TODO R11b。

## 2026-11-11付费阶段的固定范围（历史）

用户本轮明确授权总额不超过 $10。预算汇总保守计入接手前两个阶段的已结算与未确认预留，再加新账本的最大上限，始终不超过 $9.905890；未确认预留不等于已结算费用。新的授权不适用于继续第三轮或任意扩展实验。

| 新阶段 | 内容 | cap / stop（美元） |
|---|---|---:|
| `todomvc-blind-2` | 两个已冻结模型库 × 四个规划模型 × 两种做法 × 16 候选 | 2.80 / 2.60 |
| `name-sensitivity-2` | 补齐两套数据上四模型、四种提示词干预 | 0.35 / 0.30 |
| `webbench-dna-clean` | 六模型 × 20 任务 × 参考前缀代码/增量方案 | 2.40 / 2.30 |
| `webbench-dna-clean-2` | 复制有效记录；重做断连候选，Mistral 新调用改用官方供应商 | 0.85 / 0.80 |
| `webbench-dna-frontier-lib` | GPT-5 自由代码 + 同一函数库，20 任务 | 2.80 / 2.65 |

审稿专用生成脚本在发出新调用前写 `review-manifest.json`，校验配置、生成脚本和库的哈希。后续修改生成逻辑须另立阶段。先生成整组再隐藏评分；接手前已经产生的少量隐藏评分保留，但没有用于改库、改提示词或模型修复。GPT-5 对照沿用原运行器的清单与账本控制。源文件头部的简写不改变以下解释边界。

## 必须保留的解释边界

- **随机对照有条件**：只随机变体；菜单、快捷键、钩子等固定为参考方案。规则方案的变体投影不等于完整规则方案。
- **槽位一致不等于行为正确**：比较参考名字只度量参考一致率；同一任务的测试可能接受多个实现。最终方案必须从实际执行的版本回溯，不能误用后来被拒的提案。
- **2026-11-11的TodoMVC建库只对测试文本盲**：建库模型看不到官方测试或参考函数，但获得人工固定槽位、功能标签与外壳协议。这项历史实验不是自动发现接口；2026-11-12的接口实验另见末节。两者都不能排除预训练见过公开任务。
- **参考前缀有混杂**：前缀通过其上一任务的官方测试，未证明所有历史规格同时成立。相较自己上一版代码，参考代码还改变质量和表示，差值不能当作错误继承的因果占比。增量方案仍看到累计功能/槽位列表，所以“只给当前需求”并不等于两组全部信息等价。
- **统计单位有限**：任务相关、模型也可能相关；McNemar/符号检验仅作探索，按模型 bootstrap 仍不能证明跨项目推广。
- **缺失不是模型失败**：传输失败与评测器失败单独列出；只在有效共同候选上配对。旧主表和事后菜单/变体干预的分数均不覆盖。
- **成本口径分开**：报告生成调用、建库调用、未确认预留；人工工时没有记录，本地浏览器计算不折算为零成本生产开销。

本轮复评另外统一重跑了接手前使用旧 TodoMVC 全套评分器的缓存（名称干预 22 个版本、建库对照 20 个版本），而非只重跑失败项。旧评分保存在 `hidden-before-review-*.json`；排除了页面加载超时造成的假失败。评分器临时输出改为候选目录内的独立路径，官方断言与超时不变。Web-Bench 续跑可由 `test/webbench_dna/review_evaluate.py` 用独立临时目录并行评分；用已保存的通过/失败页面核对原评分一致。原续跑入口的串行评分保留作兼容路径。

2026-11-11停止时，Qwen参考前缀task-16的修复传输未完成，共同子集n=119。2026-11-12获新授权后，在 `webbench-dna-clean-3/-4/-5` 原样重放已结算响应并补齐末次修复。三次有效响应均达到12,000 tokens上限、无可执行版本，现在是有效模型失败，共同子集恢复n=120。旧失败、预留及更正说明均保留，结果见第17.1节。

## 2026-11-12：接口、第二项目与公开行为反馈

完整协议与生成入口见 [interface_blind/README.md](interface_blind/README.md)。四套库只从公开需求提出接口和实现；没有人工槽位、参考代码或页面外壳。最终比较在 `interface-blind-final-2`，累计需求、完整页面、相同输出上限；同库自由代码预加载冻结文件，可覆盖任意文件。Mistral在候选隐藏评分前因供应商故障整组改为DeepInfra FP8；原Parasail尝试保留。固定文档示例控制不读取当前需求；另外在看到主结果后固定取最后一个任务的已执行方案，原样重放20个前缀，作为事后诊断（`test.interface_blind_final_plan`）。P6另固定部分官方测试为公开反馈，其余仍隐藏，不能与原全隐藏主表合并。

```bash
uv run python -m test.replay_primary_tables
uv run python -m test.replay_scale_table
uv run python -m test.interface_blind.analyze
uv run python -m test.interface_blind_audit
uv run python -m test.behavior_feedback_analyze
uv run python -m test.review_daily_costs
uv run python -m test.export_replay_bundle
uv run python -m test.validate_replay_bundle
```

首个入口进行2692次候选记录与隐藏评分核对（跨表有复用，另报不同记录路径数），覆盖两套外部主表、TodoMVC五采样、Web-Bench两个新种子和两份GPT-5对照；第二个入口从190个已评分候选复算暂停的List-16准确率和配对区间，不打开账本、不恢复生成。Web-Bench主口径统一排除Gemma，不调用旧运行器的账本构造。后三个入口分别只读记账、制作本地匿名原始观测包、在独立临时目录复算指定表格。导出包含候选、响应、SSE、评分和去标识SQLite账本；原始哈希与导出哈希分开记录。导出脚本本身不上传，验证报告只证明实际复算的表，不能当成所有历史浏览器评分都已重新运行。论文仍不入Git。

`interface_blind_audit`仅在原工作区运行：检查历史冻结哈希、160对同库user输入、有效响应终止原因和公开反馈消息边界。匿名包路径/ID经过重写，应改验其独立 `REPLAY-MANIFEST.json`，不能要求原冻结哈希也通过。

## 2026-11-12续作：Web-Bench三个新项目

`calculator/table/bom` 的项目清单在上一阶段按公开需求固定。新阶段入口在 [webbench_expand/PRELOAD.md](webbench_expand/PRELOAD.md)，评分以 [EVALUATION.md](webbench_expand/EVALUATION.md) 为准；目录内最初的README保留为建库时的冻结记录。不要运行旧 `run generate` 代替正式的 `generate`。建库只看全部公开需求，模型提出封闭方案模式与整页实现；这仍不是建库时未见组合迁移。

同库代码可覆盖预加载文件，也可提交任意 `build(files, compile)` JavaScript，直接调用冻结编译器后修改结果。方案则先经过通用模式验证再调用同一个编译器。这一更强代码对照在首次规划调用前固定；不能把与第17节的分数变化归因于严格模式验证。

主阶段为 `webbench-expand-build` 和 `webbench-expand-run`，600个候选。GPT-5 medium独立里程碑小试60个，最终记录位于 `webbench-expand-frontier-2`；成本同时读取初始 `webbench-expand-frontier` 及续作账本。原账本关闭后复制全部记录，仅补缺失请求与未开始候选，不重抽完整模型失败。当天全部账本已关闭新请求，以下命令不调用模型：

```bash
# 在原工作区核对冻结输入和评分前的候选文件快照。
uv run python -m test.webbench_expand.snapshot
uv run python -m test.webbench_expand.audit
uv run python -m test.webbench_expand.calibration_summary

# 已保存评分的只读汇总；frontier_analyze若缺固定最终页评分，会运行本地浏览器。
uv run python -m test.webbench_expand.analyze
uv run python -m test.webbench_expand.frontier_analyze
uv run python -m test.webbench_expand.diagnostics
uv run python -m test.webbench_expand.verify_scores
uv run python -m test.review_daily_costs
uv run python -m test.webbench_expand.paper_tables
uv run python -m test.webbench_expand.report

# 仅补缺失的浏览器评分，不覆盖已存成绩、不调用模型。
uv run python -m test.webbench_expand.evaluate_pinned --workers 6
uv run python -m test.webbench_expand.controls --workers 6
uv run python -m test.webbench_expand.evaluate_pinned --stage artifacts/webbench-expand-frontier-2 --workers 6
```

运行环境由 `test.webbench_expand.setup_runtime` 及同目录的npm锁文件重建；上游测试、`test-util`、候选和协议各自有哈希。正式评分用Playwright1.57.0及Chromium1200，每任务只跑对应官方文件，BOM串行，不能随意增大并发。BOM task-7/14/19的敏感性集合在候选评分前根据参考页校准固定；主表仍保留全部20项。重复评分的同页不一致完整保留，不择优重跑。

两个文档示例和每个规划者task-20最后可执行页都原样评分；新阶段的固定最终页控制在规划调用前指定，与第17节的事后控制不同。三个项目最终参考页均可固定通过全部20个任务文件，必须结合固定控制解释逐任务规划价值。统计单位仍是三个便利选择的项目，不能把前缀、建库者、规划者当作独立应用。

原始阶段和论文仍只在本地。此前 `anonymous-replay.zip` 是第17节时间点快照；本次使用独立扩展文件名，见下节。


## 2026-11-12续作：开发集建库与未见组合

[heldout_composition/README.md](heldout_composition/README.md)和冻结[PROTOCOL.md](heldout_composition/PROTOCOL.md)定义新合成诊断。其行为维度和测试由本研究设计，不是官方Web-Bench任务；不要混入五项目主表。四库只看每应用5个开发需求及公开行为例，其余11种已知原语组合留测。所有配置隐藏动作相同，16种期望轨迹可区分；先参考校准32/32，再冻结输入、生成244候选、运行隐藏及364项控制。

方案与同库代码主组均88/88，无库32/44；GPT-5 medium两种同库做法均12/12。无模型开发示例差分44/44，说明本次选择不需要LLM。五个固定开发示例各0/44，主组固定最终页8/88。结果、首个响应格式失败、供应商和费用见第19节。

```bash
uv run python -m test.heldout_composition.analyze
uv run python -m test.heldout_composition.diagnostics
uv run python -m test.heldout_composition.report
uv run python -m test.heldout_composition.paper_tables
uv run python -m test.replay_new_tables

# 本地扩展包：包含第18–19节，不覆盖第17节历史快照。
uv run python -m test.export_replay_bundle --expanded --out artifacts/anonymous-replay-20261112-expanded.zip --report test/results/replay-bundle-expanded.json
uv run python -m test.validate_replay_bundle --expanded --archive artifacts/anonymous-replay-20261112-expanded.zip --report test/results/replay-validation-expanded.json
```

`replay_new_tables`从原始记录/评分独立重算第18–19节904个不同候选、874个固定控制和七个账本；不重新运行浏览器，也不把匿名重写字节当原冻结字节。扩展包保留生成源码（含编译器.mjs和特殊后缀文件）、请求/响应、评分、去标识账本与运行环境锁文件；不含密钥、作者Git历史或论文。独立解压目录移除API密钥后运行八个汇总入口，覆盖范围以`test/results/replay-validation-expanded.json`为准。匿名托管尚需完成，包的生成和验证不代表已公开。

原工作区`analyze`会核对所有冻结文件，不要修改`heldout_composition`的生成/评分源文件或公开开发资料。其三个阶段账本已关闭，后续新条件必须另立阶段。当天总已结算$9.624046、含未确认预留$13.203664，原第三轮仍暂停；不以账户余额代替实验账本。


第20节的`test.webbench_expand.saved_witnesses`从第18节已有合法方案和固定控制给出可达下界：53/120库与任务配对有通过见证。它不搜索、不调用API、不重跑浏览器；无见证不能说不可达。原工作区会复编译逐字核对，匿名包改用导出清单，不要求原哈希通过。

## 2026-11-13：库实现修复的完整配对可用子集

协议和具体命令见 [library_repair/README.md](library_repair/README.md)。原六库12份修复只有6份完整响应，原付费阶段没有进入候选评分。代理中断和直连地区拒绝保留，账本已经关闭：已结算$1.261570、保守敞口$8.525842，低于本次$10授权。

三套库（calculator/GPT-5、calculator/Sonnet、table/GPT-5）在两个条件下均完整，另立零API阶段重放90个旧候选。600项候选/固定最终方案/开发比较去重为204份浏览器报告；另有四页事件传播干预和固定样式的128种开关×两实现穷举（254份新报告）。严格JSON回退与唯一代码块提取诊断分开报告。文件编号分开不意味着语义未见，不能将此子集称为原六库完成、模型重新规划或泛化成绩。

`test.library_repair.available analyze`核验原工作区快照；`test.replay_library_repair`从原基线与新原始Playwright报告独立复算，可在匿名包内运行。新匿名包需加`--expanded --library-repair`并使用独立20261113-final文件名；此前20261113包只覆盖条件穷举之前的结果，11月12日与更旧的包不含本批。九个入口验证保存观测重算；另可加`--browser-smoke --browser-artifacts <新目录>`，重新解包、离线重装npm依赖后实际重跑四张机制页面和官方参考页。浏览器及系统库仍来自本机缓存，不等于跨机器或全部历史浏览器测试重跑；包也未上传。
