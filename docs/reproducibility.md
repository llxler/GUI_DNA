# 复算与公开材料说明

研究代码在 `studies/`，工程测试在 `tests/`。旧记录的 `test/...` 路径仍有效；当前分支已移除累计前缀评分入口；原始实验 JSON 和账本不重新解释。

## 公开目录与历史模块

`python -m studies.layout check` 从公开源码核对迁移前的 170 份文件。仅在直接校验旧路径清单或执行冻结运行器时使用 `python -m studies.layout prepare`。按正式目录执行的语法是 `python -m studies.layout run <阶段目录> <模块> [参数]`；它使用当时记录的模块名和文件深度。核对完成后可用 `python -m studies.layout tidy` 收起兼容文件。旧版源码专用快照仍按各阶段的协议使用。[目录与归档](../studies/README.md)

## 新建行为库的跨项目复验

主研究保留每个生成请求、页面文件哈希、当前官方文件报告和建库者固定首例；原模型对照、两个其他基准、留出与交付敏感性均有独立登记。历史清单可用 `uv run python -m studies.public_library_transfer.history --check` 从旧冻结结果离线恢复。其余复验入口及本地原始产物位置见[研究说明](../studies/public_library_transfer/README.md)。

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

正文总表及其[逐格数据](../studies/results/paper-performance-matrix.json)由 `studies.paper_end_to_end --write` 一起生成。用 `uv run python -m studies.webbench.backbone_matrix.audit` 可从公开逐题 JSON 核对模型、共同目标、实测零分、服务缺测和四批独立账本。四批的预算上限只在上一批封存后按实际敞口释放，逐笔授权可查。固定首例用相同自建库配对另报；表中“自建”表示该行的同一模型既建库又选配置。[实验协议及本地复验入口](../studies/webbench/backbone_matrix/README.md)

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

Table 1 B 区的离线绑定列可从公开的逐题 JSON 直接重建：运行 `uv run python -m studies.public_library_transfer.self_refinement.suite_comparisons` 核对两个套件的六个模型、每格目标与从零差集。逐个浏览器/Jest 收据的本机检查见 [TodoMVC](../studies/public_library_transfer/self_refinement/todomvc/source_binding/README.md) 和 [Duo](../studies/public_library_transfer/self_refinement/duo_composition/README.md)。人工库的来源、项目差异与建库模型的已知交付问题单列在[设计依据](library-preparation-design.md)。
