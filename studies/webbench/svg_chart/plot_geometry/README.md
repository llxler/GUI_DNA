# Web-Bench svg-chart 的绘图区冲突

第 3 步要求折线铺满画布，第 4 步要求默认显示坐标轴时缩小绘图区。我们固定公共数据中同一个折线图 `lineAxes`，从真实浏览器读取三条折线共 15 个顶点和两条坐标轴。视口、数据和操作在两端都相同。协议及预定配置见 [PROTOCOL.md](PROTOCOL.md)，完整输入摘要和结果见 [结果 JSON](../../../results/svg-chart-requirement-conflict-20261123.json)。

| 库与配置 | 折线的 x 范围 | 折线的 y 范围 | 命中的公开要求 |
|---|---|---|---|
| GPT-5 库，`defaults.axes=false` | 0 至 100 | 0 至 70 | 铺满画布 |
| GPT-5 库，`defaults.axes=true` | 10 至 100 | 0 至 60 | 为坐标轴留位 |
| 人工库，`line → LineChart` | 10 至 98 | 2 至 60 | 为坐标轴留位 |

坐标为 SVG 的 viewBox 单位，画布范围为 x=0–100、y=0–70。GPT-5 库仅改一个字段便覆盖两端。人工包的绑定可以为 line 选择七种渲染类或省略。没有一项绑定命中铺满端点；AreaChart 和 LineChart 均命中了留位端点。AreaChart 也含有符合位置判据的折线，说明这项测量只验证了绘图区。每个配置在两个新的 Chromium 上下文中得到相同结果。单个固定页在相同输入下最多覆盖一端。

从仓库根目录可校验记录，或用独立临时目录完整重跑浏览器。初始研究使用 11 月 21 日冻结的两个库，复现需已下载的上游数据与本地实验产物。原始点坐标与校准记录存于 `artifacts/svg-chart-requirement-conflict-20261123/`。

```bash
uv run python -m studies.svg_chart_requirement_conflict.run check
uv run python -m studies.svg_chart_requirement_conflict.run replay
```

论文配图由两次独立加载均一致的折线顶点、轴线端点和画布尺寸重绘。两幅图对应研究者指定的 `defaults.axes` 开关，浅色为折线绘图区外的左、下边距。使用 Matplotlib 可重建单栏矢量 PDF。

```bash
uv run --no-project --with matplotlib==3.11.2 python -m studies.svg_chart_requirement_conflict.plot
```

全量生成冻结后，另回放 11 月 23 日四组 Mistral Small 3.2 的原始目标页。在每行中，第 3 步应铺满、第 4 步应留位。以同组第 20 步页面固定复用作为对照。

| 已生成工作流 | 第 3 步 | 第 4 步 | 命中端点 | 固定第 20 步 |
|---|---|---|---|---|
| 人工库，原接口说明 | 留位 | 留位 | 1/2 | 留位，1/2 |
| 人工库，含允许的字段和值 | 留位 | 留位 | 1/2 | 留位，1/2 |
| GPT-5 库 | 响应无效 | 留位 | 1/2 | 响应无效，0/2 |
| 无库生成 | 铺满 | 两端均未命中 | 1/2 | 没有目标图，0/2 |

研究者干预证实了两个不同的 AI 库配置可实现需求变化；本次受测模型的四组原始输出各只完成了其中一端。保留生成缺陷和固定页的缺失状态，避免将其解释为几何属性。
