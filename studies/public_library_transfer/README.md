# 十个 Web-Bench 项目的 AI 建库迁移实验

11 月 24 日的独立复测在八个 TodoMVC 子集和十个 WebApp1K-Duo 组合上比较六个目标模型。每个模型自行建立、部署自己的库，并和同一模型对同一题的从零代码与固定首例分别配对。[实验协议](backbone_suites/PROTOCOL.md) · [逐题数据](../results/backbone-suites-20261124.json)

本研究使用同一公开输入合同在十个项目上建库，各项目分别保留 20 个当前任务。每个建库重复配有逐题组装和固定首例，另按部署模型保留一个共用无库组。重复之间分别报告。运行器要求本地留存上游快照、浏览器依赖、原始包和生成清单。

[生成协议](PROTOCOL.md) · [主批次结果](../results/public-library-transfer-20261123.json) · [官方参考页及空白页校准](../results/public-library-transfer-calibration-20261123.json) · [表格固定配置覆盖率](diagnostics/table_configurations/README.md)

官方参考页在十个项目分别通过 20/20。保留公开资产的空白页通过了 BOM 的任务 13–16、20 以及 SVG 图表的任务 1；其余 194 个任务均拒绝空白页。

## 研究目录

| 范围 | 研究入口 |
|---|---|
| Web-Bench 的部署与建库模型 | [历史部署模型](deployments/historical/README.md) · [开放权重建库](deployments/open_weights/PROTOCOL.md) |
| TodoMVC 与 WebApp1K-Duo | [基准、原模型复测与公开单功能检查](other_benchmarks/README.md) |
| 固定方案与提示 | [表格完整配置空间](diagnostics/table_configurations/README.md) · [同模型提示对照](diagnostics/prompt_guidance/PROTOCOL.md) |
| 准备与交付 | [编辑器留出目标](diagnostics/editor_holdout/PROTOCOL.md) · [无库文件交付](diagnostics/delivery/PROTOCOL.md) · [布尔域规范化](diagnostics/boolean_domains/PROTOCOL.md) |

## 离线评分与核查

只核对仓库内公开汇总时，运行 `uv run python -m studies.public_library_transfer --check`。以下命令使用本地原始产物，可核对到每份浏览器报告。

```bash
uv run python -m studies.public_library_transfer.browser verify
uv run python -m studies.public_library_transfer.browser calibrate --tasks 20
uv run python -m studies.public_library_transfer.browser calibrate
uv run python -m studies.public_library_transfer.browser calibration-report
uv run python -m studies.public_library_transfer.browser score
uv run python -m studies.public_library_transfer.browser audit
```

默认输入为 `artifacts/public-library-transfer-20261123/generation-sealed.json`。`score --project table` 读取整项目封存；`monitor` 会等待全部已登记的封存，并在结束时汇总。`--root` 可指定独立远程批次。原八项目远程批次的 draw，以及另立的 canvas/flex 远程里程碑批次，均按各自登记的五个目标汇总。

每次运行一个官方任务文件，保留 Playwright 报告哈希。完整页面树、项目、目标和浏览器合同相同才可复用收据。格式或建库失败计入已观察的流程失败；未收到响应单列为缺测。机器可读 `groups` 记录各组真实目标、可执行页面及结果，`pairs` 只统计双方均有结果的同一目标。BOM 的历史六项敏感性排除另附来源；校准同时记录官方参考页失败或空白页通过的任务。
