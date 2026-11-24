# 用需求前缀选择已有 AI 库的行为

图表实验读取截至当前任务已经出现的公开配置字段，按名启用库的布尔功能。表格实验读取公开的 DOM 交互观察，选择能够产生已要求类名的实现。所有逐题选择先封存，之后才与浏览器成绩联结。该阶段复用已有模型源码和无库对照，没有新增 API 调用。[实验协议](PROTOCOL.md) · [逐题配置与成绩](result.json)

三份图表库各测 20 个当前任务文件。Qwen3-Coder 和 DeepSeek Flash 是当时十二个登记模型中成功交付 SVG 库的两款 Self 模型。五款模型建库失败，五款模型请求缺失。第三份 SVG 库由 GPT-5 准备，与原 Mistral 逐题生成对比。表格使用同一 Qwen3.5-9B 的两份独立建库。原库均从公开需求和工程准备，本次没有增加人工组件或修改页面实现。规则是单独的确定性选择器，模型的原方案、固定首例和各取值仍分别报告。

从仓库核对发布数据与原对照：

```bash
uv run python -m studies.public_library_transfer.self_refinement.target_selection.report check
```

如有冻结包、原始浏览器回执与本机运行时，可在仓库根目录依次执行：

```bash
uv run python -m studies.public_library_transfer.self_refinement.target_selection.run freeze
uv run python -m studies.public_library_transfer.self_refinement.target_selection.run score
uv run python -m studies.public_library_transfer.self_refinement.target_selection.run geometry
uv run python -m studies.public_library_transfer.self_refinement.target_selection.report check-local
```

各实验只评当前任务文件。SVG 另报可区分空白页的 19 个文件与两个互斥几何判据，两个几何判断使用同一份输入。表格可执行选项来自公开交互观察，至少两份新浏览器上下文重复后才采用。详情含当前目标与从零各自独有的通过项。

在同一 GPT-5 供库上，规则组装、固定首例、全开在相同的 17/20 个官方任务通过；Mistral 的原方案与从零各为 3/20。只看预先公开的两项相反几何要求，规则先铺满画布、再给轴留位，命中 2/2；各固定页和两个原模型流程各 1/2。两个 Self 图表库用任一规则或原模型规划都仅通过公共数据题。表格的一个 Qwen3.5 库在公开探针引导下比原规划多通过一题，更新后的 1/20 与固定替代取值、从零相同。另一库没有可检验选项，严格组装为 0/20。

SVG 的两份 Self 实现另做[公共启动与接线诊断](chart_binding/PROTOCOL.md)。这一步保留既有图表实现，记录研究者接线和一次由公开运行错误触发的修复，和上述只改配置的试验分开。
