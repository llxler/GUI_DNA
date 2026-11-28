# 复算与公开材料说明

研究代码在 `studies/`，工程测试在 `tests/`。旧记录的 `test/...` 路径仍有效；当前分支已移除累计前缀评分入口；原始实验 JSON 和账本不重新解释。

## 公开目录与历史模块

`python -m studies.layout check` 从公开源码核对迁移前的 170 份文件。仅在直接校验旧路径清单或执行冻结运行器时使用 `python -m studies.layout prepare`。按正式目录执行的语法是 `python -m studies.layout run <阶段目录> <模块> [参数]`；它使用当时记录的模块名和文件深度。核对完成后可用 `python -m studies.layout tidy` 收起兼容文件。旧版源码专用快照仍按各阶段的协议使用。[目录与归档](../studies/README.md)

## 新建行为库的跨项目复验

主研究保留每个生成请求、页面文件哈希、当前官方文件报告和建库者固定首例；原模型对照、两个其他基准、留出与交付敏感性均有独立登记。历史清单可用 `uv run python -m studies.public_library_transfer.history --check` 从旧冻结结果离线恢复。其余复验入口及本地原始产物位置见[研究说明](../studies/public_library_transfer/README.md)。

## WebGen-Bench 网站操作与表格交互修复

主表 C 用 `python -m studies.webgen_bench.site_completion.report` 从 Git 中的判决复算。每个模型的四种方法共用站点和操作编号。查看单格用 `python -m studies.lookup webgen-bench "DeepSeek V4 Flash" Human`，返回完整通过数、分母、已启动的共同目标及判决文件。具备本机原始产物时，给复算命令加 `--ledgers` 核对费用，运行 `uv run --with duckdb python -m studies.webgen_bench.site_completion.sdk_audit` 可独立重放旧游戏页升级前后的数值。运行 `python -m studies.webgen_bench.site_completion.verify_pages` 可从同一份原配置重编三个渲染端；当前主表 Human 另使用 SDK 的原生纵向标签设置。[新网站与逐项数据](../studies/webgen_bench/site_completion/README.md)

离线运行 `uv run python -m studies.webgen_bench.report --portable`，可从版本库中的逐项判决重算六站同题得分，并核对五种建库接口、每阶段原始成本和两个 Qwen 表格库的固定页对照。本机有原账本时，`uv run python -m studies.webgen_bench.report` 进一步核对模型、阶段及未决敞口。恢复六站数据、作者评估器及 amis SDK 使用 `uv run python -m studies.webgen_bench.fetch_sources`。[新基准目录](../studies/webgen_bench/README.md) · [Qwen 原库逐交互修复](../studies/webbench/table/selection_binding/interaction_repairs/PROTOCOL.md)

运行 `uv run python -m studies.public_library_transfer.source_diagnosis.report`，根据逐题记录重算库来源比较、固定方案和独立重复。该命令还检查文件管理器新增条目的身份、SVG 封存后的新数组，以及 TodoMVC 的四种方法。具备本机原始页面与回执时，`uv run python -m studies.public_library_transfer.source_diagnosis.visible_choices.core_profiles.choices` 可复原模型选择和每个配置未通过的公共操作。[来源比较及复核入口](../studies/public_library_transfer/source_diagnosis/README.md)

## 零 API 复算

```bash
uv run python -m studies.end_to_end --check
uv run pytest -q
uv run python -m experiments.audit_scale
```

11 月 23 日的建库改进使用独立清单和产物目录。在保留对应回执的本机，可用下列命令逐条复算。表格的两批归档响应与新的 Qwen 计划分别验收。每个后端都按当前任务和整套页面文件哈希取官方回执。

```bash
uv run python -m studies.layout run webbench/table/starter_binding run check
uv run python -m studies.layout run webbench/table/shared_state_contract evaluate check
uv run python -m studies.layout run webbench/table/compatible_rebuild evaluate check
uv run python -m studies.layout run webbench/table/local_planning evaluate check
uv run python -m studies.layout run webbench/table/controller_build evaluate check
uv run python -m studies.layout run webbench/table/schema_decoding evaluate check
uv run python -m studies.library_refinement_accounting --check
```

SVG 的原始规划、固定示例与部署回退可按[图表冻结实验](../studies/webbench/svg_chart/interface_refinement/README.md)复核；本地模型、解码条件与新图表库分别见[规划协议](../studies/webbench/svg_chart/local_planning/PROTOCOL.md)及[重建协议](../studies/webbench/svg_chart/compatible_rebuild/PROTOCOL.md)。

主视图的默认展示按建库者分列，项目/生成模型另分层，原合并字段只供对账。`studies.builder_costs` 从本地账本和 draw 回执重建逐建库者费用索引；没有原始产物时，主视图可从已登记索引复算。

主视图脚本直接读取两项目/三项目的原当前成绩与 draw 的 current 行，按真实候选去重；保留 BOM 敏感性和建库费用。它不读取累计前缀复验结果，不重新运行浏览器。完整旧研究命令见 [历史索引](../studies/REVIEW.md)。

本地拥有完整 `artifacts/` 时可进一步复验研究快照与原报告。旧快照必须在登记的源码版本复算，见 [退役说明](archive/full-history-retirement.md)。当前分支不再提供已删除实验的复验入口；不要修改旧清单来迁就新源码。代码 checkout 不包含被忽略的响应、页面、账本、浏览器缓存或上游 checkout；仅有源码不能重放全部历史结果。

### 核对 Table 1 的红框复验、弱模型和扩展分母

`uv run python -m studies.webbench.table_interactions.diagnose` 离线复放表格库全部四种开关组合中的右键、Delete 和双击。逐研究费用及五组问卷解码请求都由下述汇总的源记录核对；建库费用、逐题费用和未决预留分别保存。

以下命令只读封存的候选、逐题判定和账本。第二条核对红框 18 格的原题、最终采用的协议、固定配置与费用。不执行 `generate`。

```bash
uv run --offline python -m studies.paper_end_to_end
uv run --offline python -m studies.webbench.compact_planning.report
```

本地重新编译并将新成稿放回 `DNA_latex/main.pdf` 后，以下命令从正文的实际表题定位 Table 1，同时刷新单页 PDF 和 PNG。正文中的表号引用不计作表题。

```bash
uv run --offline --with pymupdf python -m studies.paper_format --report studies/results/paper_format_end_to_end.json --table-preview artifacts/paper-build/performance-matrix
```

原样本上的变化见[编号配置试验](../studies/webbench/compact_planning/PROTOCOL.md)和[类型化组件](../studies/webbench/typed_components/PROTOCOL.md)；额外目标只使用同一套已冻结的库和部署方式，独立保存在[补传与扩展](../studies/webbench/transport_completion/extension.md)。小模型的主结果与第二份独立库见[八个功能子集](../studies/public_library_transfer/compact_todomvc/PROTOCOL.md)。C 区的采样可由[数据版本与分层规则](../studies/webgen_bench/README.md)复算。

### 核对主表 A、B 的 25 格自建库复测

主表使用每格第一份独立建库的逐题方案。统一审计核对两次重复的可部署目标、固定首例、原始同题对照和本轮七份账本。初版接收器产生的费用也在其中。有本地原始产物时运行以下只读命令。[复验阶段与数据](../studies/webbench/self_build_modules/README.md)

```sh
uv run --offline python -m studies.webbench.self_build_modules.audit
```

### 核对 11 月 25 日的 Flash 问卷复测

下列命令分别核对两次全新建库的首次响应，以及原样补交传输中断请求后的同目标结果。带本机原始收据时，把 `check-public` 换成 `check` 可核对模型响应、页面与官方评分。[协议、原批和中间结果](../studies/webbench/form/flash_self_build/README.md)

```bash
uv run python -m studies.webbench.form.flash_self_build.file_repair.report check-public
uv run python -m studies.webbench.form.flash_self_build.transport_completion.report check-public
```

### 核对 11 月 24 日的自建库诊断

以下命令用公开结果核对失败阶段、同一题的对照、独立建库重复和实际分母。带 `check-local` 的入口还读本机原始文件、API 收据和官方浏览器报告。生成新候选需要另开有预算的研究批次。

```bash
uv run python -m studies.public_library_transfer.diagnostics.self_failures check
uv run python -m studies.public_library_transfer.diagnostics.self_capacity.run check
uv run python -m studies.public_library_transfer.self_refinement.native.report check
uv run python -m studies.public_library_transfer.self_refinement.coherent.report check
uv run python -m studies.public_library_transfer.self_replication.confirmation check
uv run python -m studies.public_library_transfer.self_replication.paper
uv run python -m studies.public_library_transfer.self_replication.accounting check
uv run python -m studies.public_library_transfer.strong_builder.check
```

## 人工库与 AI 库的同目标比较

在保留 11 月 21 日原始产物的工作区，运行 `uv run python -m studies.layout run webbench/form/library_sources report` 可只读核对两阶段的输入哈希、目标、页面、官方报告、建库与生成费用以及续跑边界。论文三组配对行来自 [逐目标记录](../studies/results/library-sources-20261121.json)；附录另列每组全体可观察结果和缺失。表单公开修复的独立复核命令为 `uv run python -m studies.layout run webbench/form/public_repair report`，逐项确认所有反馈只含原解析或编译错误。两个项目不共用分母。[问卷协议](../studies/webbench/form/library_sources/PROTOCOL.md) · [图表协议](../studies/webbench/svg_chart/library_sources/PROTOCOL.md)

11 月 23 日的表格编辑器、SVG 图表与表达式编辑器各有独立协议、账本与目标目录。下列命令读取冻结响应和官方报告，核对各研究本身的分母与来源。图表协议保留了空白页通过第 1 项时，在正式生成前登记的校准修订。

```bash
uv run python -m studies.layout run webbench/table/library_sources report --check
uv run python -m studies.layout run webbench/svg_chart/interface_documentation report
uv run python -m studies.layout run webbench/svg_chart/fixture_audit audit
uv run python -m studies.layout run webbench/flex/column_count run check
uv run python -m studies.layout run webbench/svg_chart/plot_geometry run check
uv run python -m studies.layout run webbench/expression_editor/library_sources report --check
uv run python -m studies.layout run webbench/expression_editor/held_out_requirements report
uv run python -m studies.layout run webbench/expression_editor/preparation_notes report
uv run python -m studies.layout run webbench/expression_editor/preparation_window report
uv run python -m studies.layout run webbench/expression_editor/empty_plan run check-public
uv run python -m studies.layout run webbench/expression_editor/interface_examples run check-public
uv run python -m studies.layout run webbench/expression_editor/interface_examples audit
uv run python -m studies.layout run webbench/table/controller_enumeration report --check
uv run python -m studies.layout run webbench/table/controller_enumeration selection
uv run python -m studies.layout run webbench/draw/pointer_transition run check
uv run python -m studies.layout run webbench/draw/pointer_transition length_sensitivity
uv run python -m studies.layout run webbench/react_blog/runtime_calibration run check
uv run python -m studies.webbench_coverage
uv run python -m studies.reuse_costs_20261123
```

32k 编辑器阶段第 7 个无库输出包含超长文件名。独立恢复入口复用原请求回执，将操作系统的路径长度错误计为不可交付的输出，再走已登记的一次公开修复。上面的只读核对可直接验证恢复后的原始记录。[恢复入口](../studies/webbench/expression_editor/preparation_window/resume.py)

在含有固定上游快照、Chromium 与 Node 的环境，可依次运行 `uv run python -m studies.layout run webbench/react_blog/runtime_calibration run setup`、同入口的 `evaluate` 和 `report` 三个阶段，以原 Rush 锁重建 React 运行时并生成 60 份当前文件观察。校准报告中不含模型候选。[React 校准协议](../studies/webbench/react_blog/runtime_calibration/PROTOCOL.md)

核对本日费用可直接运行 `uv run python -m studies.ledger_read artifacts/*20261123/budget.sqlite3`。各账本的 `settled_usd` 只含已结算请求，`exposure_usd` 另含尚未定价的预留；历史建库账本不在这七项中。

## 匹配工作流与交互诊断

`canvas_pilots` 中三个批次分别保留 GPT-5 的两个输出上限与 Claude 的 32k 复验，`matched_flex` 为另一项目。每重复有 5 个预定目标。重算核对任务配对和每次请求的微美元取整，`observed_reuse_costs` 将准备费记一次，再按目标顺序累计回执。

有本地原始材料时，以下命令仅对已完成阶段重新分析，模型生成另有独立入口：

```bash
uv run python -m studies.matched_canvas.analyze --check
uv run python -m studies.canvas_capacity.run analyze
uv run python -m studies.matched_flex.run analyze
uv run python -m studies.canvas_model_replication.run analyze
```

各阶段保留公开提示、最终响应、准备失败、冻结源码、逐个浏览器报告与只读账本。固定页面控制复用完全相同源码与任务的报告；接口测量另存真实浏览器观察，在查看主模型成绩后设计的干预已在协议中标明。完整实验均按当前任务文件评分。

## 本地论文与展示

正文总表及其[逐格数据](../studies/results/paper-performance-matrix.json)由 `studies.paper_end_to_end --write` 一起生成。矩阵中 `current` 保存原始口径，`paper_current` 记录因建库失败需从论文成绩中排除的目标与重算分母。Flash 的 `panel_a_self.form` 记录 A 区主格采用的第一份库（file-a）及其逐题来源，`current.form` 保留原批次，用于核对同题对照及建库历史。用 `uv run python -m studies.webbench.backbone_matrix.audit` 可从公开逐题 JSON 核对模型、共同目标、实测零分、服务缺测和四批独立账本。四批的预算上限只在上一批封存后按实际敞口释放，逐笔授权可查。固定首例用相同自建库配对另报；表中“自建”表示该行的同一模型既建库又选配置。[实验协议及本地复验入口](../studies/webbench/backbone_matrix/README.md)

```bash
uv run python -m studies.paper_end_to_end --write
bash artifacts/paper-build/build.sh
# 编译成功且日志无错误后，将 build/main.pdf 同步到 DNA_latex/main.pdf。
uv run --with pymupdf python -m studies.paper_format --report studies/results/paper_format_end_to_end.json
artifacts/presentation-build/venv/bin/python artifacts/presentation-build/build_presentation.py
artifacts/presentation-build/venv/bin/python artifacts/presentation-build/render_and_check.py
```

这些目录/工具为本地编辑资产，尚未作为公开论文材料发布。旧论文模板与累计前缀表格生成器已移出当前工作树；不得从旧版本重新接回当前稿件。新稿全部活跃表格由 `paper_end_to_end` 登记和核对。

## 路径兼容与匿名包

- `test -> studies` 保持旧 Python 导入和哈希路径；`实验结果.md`、`代码逻辑.md`、`experiments/TODO.md` 指向正式 `docs/` 文件。克隆时须保留符号链接；无符号链接环境可使用匿名导出器的实文件副本。
- 匿名导出需同时保留正式路径和旧 `test/...` 可执行副本，不能把路径变更当作改写冻结证据的理由。新清单登记原始与匿名化字节的区别。含已退役实验的旧导出选项已停用；新论文材料需另立范围明确的包。
- 旧大包为 `anonymous-replay-20261116-final-2.zip`，12 个入口通过；该包的检验只对应当时登记的材料。旧包不覆盖、不自行上传。
- 仓库保留上游许可证和来源说明。数据与匿名下载地址仍待作者审核，见 [roadmap](roadmap.md)。

2026-11-18 的当前报告包为 `current-report-20261118.zip`，使用 [导出与解包说明](../studies/current_bundle/README.md)。在本机另行解包后，正式、兼容两个入口重算一致，核对 80 个预定位置、147 条精简浏览器报告（127 份不同原件），两个项目共七次真实浏览器抽查与原判定一致。哈希与逐页结果见 [验收记录](../studies/results/current-report-validation-20261118.json)。

TodoMVC 和 Duo 的离线绑定结果可从逐题 JSON 重建。运行 `uv run python -m studies.public_library_transfer.self_refinement.suite_comparisons` 核对两个套件的六个模型、每格目标与从零差集。逐个浏览器/Jest 收据的本机检查见 [TodoMVC](../studies/public_library_transfer/self_refinement/todomvc/source_binding/README.md) 和 [Duo](../studies/public_library_transfer/self_refinement/duo_composition/README.md)。人工库的来源、项目差异与建库模型的已知交付问题单列在[设计依据](library-preparation-design.md)。

Duo 初批两模型与 Qwen 精简契约的另外两份库，分别用 `uv run python -m studies.public_library_transfer.self_refinement.duo_components.report check` 和 `uv run python -m studies.public_library_transfer.self_refinement.duo_components.compact.report check`。Gemma 的两份控制器用 `uv run python -m studies.public_library_transfer.self_refinement.todomvc.verified_controller.run check`，分支语法修复用同目录 `switch_scope.run check`。这些核对从发布记录取数，不调用模型。

最新 20 项问卷及图表的官方结果和源文件接收灵敏度分别见 [问卷核验命令](../studies/public_library_transfer/self_refinement/form_components/README.md) 和 [图表核验命令](../studies/public_library_transfer/self_refinement/svg_renderers/README.md)。主表 双库复验记录逐行保留目标标识及输入哈希。[原 18 行的逐行来源](../studies/results/prospective-domain-builds-20261124.json) · [前瞻确认行与复用对照](../studies/results/prospective-domain-confirmation-20261124.json) · [七账本计费收据](../studies/results/domain-construction-accounting-20261124.json)

图表两份全新确认库和共用的旧 Direct 可用 `uv run python -m studies.public_library_transfer.self_refinement.svg_renderers.confirmation.report check` 逐题核验。最终八个账本用 `uv run python -m studies.public_library_transfer.self_refinement.prospective_accounting check-final`。[前瞻确认](../studies/public_library_transfer/self_refinement/svg_renderers/confirmation/result.json) · [合计费用与未决预留](../studies/results/domain-construction-accounting-final-20261124.json)

### 核对 11 月 26 日的组件库复验

`uv run python -m studies.library_capabilities` 只读核对各阶段的原始账本、主库、独立重复和固定页。`uv run python -m studies.paper_end_to_end --write` 依据同题交集生成论文表。文件管理器 Direct 每题从公开起始页生成，旧逐步编辑结果保存在原协议中。Duo 使用 OneKQ 固定数据集提交的 `gpt-5.code`；在本地下载的 Parquet 上运行 `uv run --with duckdb python -m studies.public_library_transfer.duo_donor_library.run prepare` 可核对他组来源与公开单功能验收。原始库、传输请求、测试报告和账本保存在本机 artifacts。

同线程中页面服务与浏览器共用一个并发名额，可用 `uv run python -m studies.browser_worker studies.webbench.calculator.key_groups.run score` 在封存后重放。独立种子表格若运行模型 JavaScript 造成公开页面卡死，先在两个受时限保护的独立浏览器中重放；已超时的交互保留状态与收据。[重复实验的执行器](../studies/webbench/table/selection_binding/replication/bounded.py)

11 月 26 日的总账保留分槽决策的三批回执。先在旧的已结算响应中逐字比较请求体、校验响应哈希，再补真正缺失的选择；重传不会释放原未知预留。逐格索引同时记录原截图的目标 ID、当时的通过数、最新协议在这些原目标上的通过数、以及扩充后的实际分母。主表生成时会逐格核对。[汇总程序](../studies/library_capabilities.py) · [最后两个限流位置](../studies/public_library_transfer/compact_todomvc/slot_choices/last_delivery.md)

### 核对 11 月 27 日的跨站与组件验证

在仓库根目录运行 `uv run python -m studies.webgen_bench.component_contracts.report`，可从发布的逐项记录复算六站、三站、TodoMVC 两次建库及表格序列诊断。有原始账本的本地环境可加 `--ledgers` 复核各模型建库、选配置、写整页与评判支出。查询归档试验用 `uv run python -m studies.lookup webgen-bench/heldout "Gemma 3 12B" Self`；把数据集换成 `webgen-bench/development` 即查原六站开发结果。两次查询给出各自的站点、分母和逐项回执。[阶段索引](../studies/webgen_bench/component_contracts/README.md)

本机保留原始生成及浏览器时运行 `uv run python -m studies.webgen_bench.heldout_transfer.incomplete_html.inspect`，可离线核对两站首答和重试的可见按钮、文本和内联 JavaScript 语法。表格新处理函数的回放记录同时给出与旧配置相同的逐题对照以及两段独立顺序的每步状态。[HTML 浏览器诊断](../studies/webgen_bench/heldout_transfer/incomplete_html/inspect.py) · [表格功能验证](../studies/webbench/table/action_sequences/selection_mode/validation.json)

表格菜单可用 `python -m studies.webbench.table.menu_propagation.author_repair.report` 从 Git 中的两次建库和五个模型的逐题记录核对首份修复、固定页及每次得失。配对提示的两个种子与官方结果由 `python -m studies.webbench.table.menu_propagation.event_trace.verify` 核对。[修复范围与准入](../studies/webbench/table/menu_propagation/author_repair/PROTOCOL.md)

### 核对 11 月 28 日的新增模型与配置实验

运行 `python -m studies.lookup web-bench/calculator` 可列出主表实际展示的计算器模型。GPT-5 来源分支在[逐题记录](../studies/webbench/calculator/compiler_fallback/result.json)中分别保留原生配置、最终页面和两个固定示例。四种方法比较同一行的共同任务。运行 `python -m studies.lookup todomvc "Ministral 3B" Self` 可找到逐题响应和评分记录。各阶段在生成前登记输入与第一库规则。保留原账本的本机可用 `uv run python -m studies.paper_target_extensions` 按研究、模型和建库或部署重新核对费用。

文件管理器的从零结果可按 `python -m studies.lookup web-bench/dom1 "Gemma 3 12B" Direct` 查询。每个模型均保留原始响应摘要、解包前后文件摘要、交付格式和官方判决。对照原接收器与现接收器的结果请见[离线重放协议](../studies/webbench/file_explorer/target_models/direct_reception/PROTOCOL.md)。


用 `python -m studies.lookup web-bench/table "DeepSeek V4 Flash" GPT-5` 可定位表格四组源码的同配置对照。计算器的 `python -m studies.lookup web-bench/calculator "DeepSeek V4 Flash" Self` 同时给出主表分母、任务号和可复算的逐页判决；在 Flash 的同一 JSON 中比较 `self`、`old-code-new-choice` 与 `new-code-old-choice` 即可区分改代码和改配置的作用。Gemma 和 Qwen3.5 还可用 `old-code-same-choice` 与逐键补交后的 `self` 核对同配置的实现变化。费用文件按阶段、模型和用途记录结算与未结敞口。本机保有账本时用 `uv run python -m studies.paper_module_rebuilds` 逐项核对。[计算器逐题记录](../studies/webbench/calculator/key_programs/result.json) · [表格逐题记录](../studies/webbench/table/author_modules/result.json) · [费用收据](../studies/results/library-rebuild-costs-20261128.json)

计算器逐键补交和表格轨迹修复会各生成一份与父阶段的关联收据。原始评分文件保持冻结。本机保有封存候选时，用 `uv run python -m studies.rebuild_lineage calculator` 或 `table` 核对，同一选择的源码哈希或每次修复的输入哈希必须一致。两个初版运行器先封存逐题判决，随后尝试在同一个文件追加父库来源，冻结写入器会拒绝这次追加。下列完整入口把该指纹另存到 `lineage.json`，保留已封存评分。从头运行这两个阶段的完整入口是 `uv run python -m studies.browser_worker studies.rebuild_lineage calculator --execute`（表格将项目名改为 `table`）。

运行 `uv run python -m studies.webbench.calculator.memory_recall.diagnose` 可按报告哈希核对已经封存的完整页在记忆任务上的失败断言。该命令只读取既有浏览器报告。[逐项核对](../studies/webbench/calculator/memory_recall/browser-errors.json)

<a id="duo-feature-check"></a>
### WebApp1K-Duo 的公开检查、收据与新组合

`python -m studies.lookup webapp1k-duo "Qwen3.5-9B" Self` 返回 4/5 和五个题号。按 `method_record`、模型、`record_filter.arm` 及这五个题号过滤记录。三种库的 `fixed_configuration_score` 使用相同分母，字段 `configuration_record` 指向共用的真实模型配置。查任意方法都只需 Python 标准库。逐阶段的冻结边界见[实验目录](../studies/public_library_transfer/duo_verified_features/README.md)。

本机保留原始候选与固定版本的 Jest 环境后，运行 `uv run --offline python -m studies.public_library_transfer.duo_verified_features.report` 可只读核对四本调用账本、费用和源指纹。新组合的抽样和候选在 `unseen_pairs/result.json`。最终判分在 `unseen_pairs/entry_points/result.json`，其 `phases.initial` 是首次生成的代码，`phases.router` 是同题的路由适配复测。按 `entries` 核对三份名称不同的官方导入口，按 `official_cases` 复算每题的四项判决。用 `uv run --offline python -m studies.public_library_transfer.duo_verified_features.unseen_pairs.entry_points.run` 可从两批封存页面复核，两组都使用相同导入规则，无新增模型调用。

运行 `uv run --offline python -m studies.public_library_transfer.duo_verified_features.verify` 可独立核对十个阶段注册时的输入指纹、375 份收到的响应与实际请求模型、主表三种库的逐题执行和新十题两批各 50 份目标判分。[本轮核验](../studies/public_library_transfer/duo_verified_features/verification.json)
