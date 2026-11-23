# Web-Bench SVG Chart 的本地规划器实验

同一份原 GPT-5 图表库、相同的二十个公开需求前缀，用本机 Qwen2.5-0.5B-Instruct 生成独立计划。精简包条件使用库作者的计划模式和两个示例。完整包另含原设计、实现和编译器。两条件使用同一原生文本解码、同一结构验证器与同一套官方当前任务文件。

精简接口的 20 份响应都以 EOS 结束且带有 Markdown 围栏。按原始严格约定逐任务部署，通过 0/20；无效响应回退到首例，通过 17/20。固定首例本身也通过 17/20。额外只剥离单一围栏后，10 份满足强类型要求并生成字节完全相同的页面，另外 10 份多嵌套一层 `plan`。单纯剥壳通过 8/20，再加默认恢复通过 16/20。与始终使用默认页相比，唯一变化是第 8 个任务从通过变为失败。[严格结果](../results/svg-chart-compact-local-20261123.json)

同一模型、每格相同的 20 个目标，完整收齐两组各 20 份原始响应。完整包 20 份均达到 768 个输出 token 上限。

| 部署 | 完整包 | 精简包 |
| --- | ---: | ---: |
| 严格 JSON 与模式验证 | 0/20 | 0/20 |
| 严格验证，失败时回退首例 | 17/20 | 17/20 |
| 允许单个 Markdown JSON 围栏 | 0/20 | 8/20 |
| 允许围栏，仍无效时回退首例 | 17/20 | 16/20 |

固定首例对照在同一组 20 个任务上通过 17 项。[同模型逐目标配对](../results/svg-chart-local-prompt-comparison-20261123.json) · [围栏敏感性结果](../results/svg-chart-local-fences-20261123.json)

- [精简包协议](PROTOCOL.md) 规定严格 JSON 的字段、类型和回退规则。
- [完整包协议](FULL.md) 登记 20 个同模型配对和硬截止。
- [围栏敏感性](FENCES.md) 单列精简包首份回应显示 Markdown 围栏后登记的通用输出适配。

首先发布全部候选，才按目标运行官方评分。固定控制将原库作者的第一份示例编译成同一张页面，用于每一个目标。触发恢复的任务仅使用这份固定页。几种部署的通过数应分别解读，不能据此判断新建库能力或整应用正确性。历史 3/20 使用 Mistral、供应商 JSON 模式和 8,192 个输出 token 上限；本地两个 Qwen 条件均使用原生文本解码和 768 个输出 token 上限。两种本地发布方式可在同一模型和同一解码条件下直接比较。

在留存本研究本地制品的机器上，可用以下命令从封存的响应和逐目标回执复算，再与公开 JSON 核对。

```bash
uv run python -m studies.svg_chart_compact_local.run check
uv run python -m studies.svg_chart_compact_local.full check
uv run python -m studies.svg_chart_compact_local.fences check
```

推理命令使用 `python -m studies.svg_chart_compact_local.local_planner <已登记研究目录>`，需要缓存的指定权重、CUDA、PyTorch 2.11.0 与 Transformers 5.5.1。脚本强制离线并拒绝覆盖已封存的生成，响应时间窗口截至 2026-11-23 06:06 UTC。原始回执存文本、输入的 token 摘要、输出 token ID、解码参数和停止原因，研究清单存逐文件权重、分词器、运行时与提示 SHA-256。精简包与完整包的官方评估分别存于 `artifacts/library-refinement-chart-20261123/replays/` 下的独立目录。

完整包与后续两次独立表格研究使用同一台 GPU。为控制内存，[共享调度器](shared_worker.py) 装载一份相同权重，调用原冻结推理代码，每个目标独立应用聊天模板，串行执行单样本解码。就绪的表格任务先执行，组间按等待顺序调度，剩余完整包任务在同一硬截止以里继续。各目录的 `scheduler-admission.json` 留存调度器和原推理代码的 SHA-256。新分配改变了执行顺序，可能影响截止前可观察的位置数。
