# 复算与公开材料说明

研究代码在 `studies/`，工程测试在 `tests/`。旧记录的 `test/...` 路径仍有效；当前分支已移除累计前缀评分入口；原始实验 JSON 和账本不重新解释。

## 零 API 复算

```bash
uv run python -m studies.end_to_end --check
uv run pytest -q
uv run python -m experiments.audit_scale
```

主视图的默认展示按建库者分列，项目/生成模型另分层，原合并字段只供对账。`studies.builder_costs` 从本地账本和 draw 回执重建逐建库者费用索引；没有原始产物时，主视图可从已登记索引复算。

主视图脚本直接读取两项目/三项目的原当前成绩与 draw 的 current 行，按真实候选去重；保留 BOM 敏感性和建库费用。它不读取累计前缀复验结果，不重新运行浏览器。完整旧研究命令见 [历史索引](../studies/REVIEW.md)。

本地拥有完整 `artifacts/` 时可进一步复验研究快照与原报告。旧快照必须在登记的源码版本复算，见 [退役说明](archive/full-history-retirement.md)。当前分支不再提供已删除实验的复验入口；不要修改旧清单来迁就新源码。代码 checkout 不包含被忽略的响应、页面、账本、浏览器缓存或上游 checkout；仅有源码不能重放全部历史结果。

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
