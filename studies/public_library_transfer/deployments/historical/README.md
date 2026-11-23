# Web-Bench 原部署模型迁移实验

Mistral Small 3.2 24B 与 GPT-OSS-120B 在预登记项目上分别从当前需求前缀生成页面，或为某一已冻结的 AI 库选择配置。每个模型和目标只有一份无库代码。GPT-5 与 Claude 的项目准备、两次独立 GPT-6.2-astra 订阅建库、两种部署模型及各自成本分开计数。任务列表和生成设置见[原协议](PROTOCOL.md)和[订阅建库补充协议](CODEX-SUPPLEMENT.md)。

## 复核

历史协议及对应目标可从冻结源离线重算。当前实验的浏览器评分校验页面哈希并运行对应任务的原始断言；重复调用使用已核验的测评收据。与同模型无库生成比较时使用每组共同观测的任务。对未获得模型回复的准备，保留历史目标且记录缺失。

```bash
uv run python -m studies.public_library_transfer.history --check
uv run python -m studies.public_library_transfer.retest_crosswalk --check
uv run python -m studies.public_library_transfer_remote.verify --require-seals
uv run python -m studies.public_library_transfer.browser score \
  --root artifacts/public-library-transfer-remote-20261123 --workers 2
```

生成沿用本轮固定的 UTC 时限及两个独立的 3.50 美元账本。顺序为 `run register`、`run direct`、`supplement register`、`supplement generate`、`supplement seal`。订阅补充自原阶段的 `runs/` 引用直接生成的记录；统一封存入口是 `supplement seal`。协议修订与原始建库的服务商拒绝均保留。建库和规划只读公开需求、起始工程及准入包。评分过程在相应项目封存之后运行。共享设备上的浏览器并发由运行器管理。

结果文件名由独立实验根目录确定。生成结束后，费用明细可在 [public-library-transfer-remote-billing-20261123.json](../../../results/public-library-transfer-remote-billing-20261123.json) 逐模型核对，未知预留计入敞口。最终任务分数在 [public-library-transfer-remote-20261123.json](../../../results/public-library-transfer-remote-20261123.json)。历史登记 [public-library-transfer-history-20261123.json](../../../results/public-library-transfer-history-20261123.json) 中的原建库者、原响应及组别均保留。

Canvas、Flex 两个项目另有五里程碑补测。两种部署模型分别完成五题，各用两份订阅建库，沿用原两账本。协议见[里程碑登记](MILESTONES.md)。独立的 `studies.public_library_transfer_remote.milestones` 入口依次支持 `register`、`generate`、`seal`，评分根目录为 `artifacts/public-library-transfer-remote-milestones-20261123`。共用账本在八项目封存时先截取一次快照，再计算两项目的新增费用。
