# 局部开发需求到完整交互序列

这是独立合成诊断，不是官方benchmark成绩。来源与适配见[SOURCES.md](SOURCES.md)，预定方法/控制/预算见[PROTOCOL.md](PROTOCOL.md)。两来源应用、两建库者、两建库提示、两规划者。建库输入只含三个局部开发需求，目标每应用一份完整规格；每个目标评分12条未见交错轨迹，不把轨迹当独立应用。

```bash
uv run python -m test.interaction_transfer.prepare calibrate
uv run python -m test.interaction_transfer.prepare freeze
uv run python -m test.interaction_transfer.run build --workers 2
uv run python -m test.interaction_transfer.run run --workers 2
uv run python -m test.interaction_transfer.evaluate prepare
uv run python -m test.interaction_transfer.evaluate score
uv run python -m test.interaction_transfer.analyze
uv run python -m test.authorized_costs --date 20261115
```

生成/修复最多3响应；`--resume`只补传输缺失，保留已有效响应和反馈，旧未知费用不抹去。整个候选批次完成后才评分。方案与同库自由代码的user输入逐字相同，自由代码能一行调用整个编译器；额外工作功能允许存在。三个不变开发示例、预定全部合并、所有非空子集的固定合并均保留。有限子集任何成功只算可达见证，不算可部署的择优控制。

建库请求预算配置为cap12/stop11.5，但冻结Ledger实现的初始硬上限自动收紧为**实际cap10/stop9**；不放宽。生成实际cap6/stop5.7。只读费用入口报告真实策略；配置/协议保留，不以其较大请求值冒充实际可花额度。今天总授权≤20美元，06:40 UTC后不接受新请求，07:20 UTC前收工。

冻结清单在 `artifacts/interaction-transfer-calibration-20261115/frozen.json`，包括domain/browser/fixtures/reference/prepare/core/run/controls/evaluate、公开开发输入、两个协议文档及复用依赖；不能原地改。analyze.py、README与后续只读报告工具不在该冻结清单中。前两步校准及冻结已经完成后，不得重新写已有产物。
