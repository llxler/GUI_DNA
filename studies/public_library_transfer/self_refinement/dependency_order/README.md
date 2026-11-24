# 按依赖顺序建库

Qwen3-Coder-30B-A3B-Instruct 在 Web-Bench 表格编辑器独立建立两份库。程序把模型自己的源码按依赖顺序交给后续调用，使用 Node 的 ES module 链接器列出实际导出和未满足的依赖，只把公开输入与公开诊断传给模型。二十道题共用同一次从零生成对照。每个建库重复分别保留自己的逐题配置和固定首例。详细的预算、信息范围、退出条件和对照设计见[预登记协议](PROTOCOL.md)。

开放仓库中可直接核对两份建库结果、原始目标键、共同对照、费用和逐题翻转。当本地另有冻结源码、账本和浏览器报告时，可以继续逐份复核候选、原始响应和源码依赖图。

```bash
uv run python -m studies.public_library_transfer.self_refinement.dependency_order.report --check-public
uv run python -m studies.public_library_transfer.self_refinement.dependency_order.report --check
```

原始的公开逐题记录见[依赖顺序实验结果](../../../results/self-dependency-table-20261124.json)。

初次运行中两份库分别在第 3 和第 6 个模块遇到传输中断。[串行续接协议](RESUME.md)逐字复用已收到的回答，只重传无回答的同一请求。初次运行和[续接阶段的逐题证据](../../../results/self-dependency-resume-20261124.json)分别发布，费用表同时给出两个账本的总敞口。

```bash
uv run python -m studies.public_library_transfer.self_refinement.dependency_order.resume_report --check-public
uv run python -m studies.public_library_transfer.self_refinement.dependency_order.resume_report --check
```
