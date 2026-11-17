# 匹配累计信息的前缀与输出形式对照

[PROTOCOL.md](PROTOCOL.md)定义160候选：GPT-OSS低推理与Mistral Small，各自在自身/参考前缀下输出同库代码或受检查方案，按20个任务顺序生成。两种方法均获得完整库、累计需求、feature列表、明确JSON模式和完整HTML前缀。参考条件的40组user消息逐字相同；自身前缀来自各自上一可执行输出。最多两次公开修复，不给官方测试反馈。

原`test/prefix_factorial/`遗漏了方案顶层结构说明，在公开编译反馈中发现后、隐藏评分前停止。该阶段全部输出和费用保留，不混入正式v2；修改共享输入后所有条件重新生成，包括代码。协议修正属于探索性开发，不能称未观察输出的确认性预注册。

```bash
# 全部生成结束后才能冻结评分输入；已有快照不要再次prepare。
uv run python -m test.prefix_factorial_v2.score prepare
uv run python -m test.prefix_factorial_v2.score evaluate

# 只读核验、统计。
uv run python -m test.prefix_factorial_v2.analyze
uv run python -m test.prefix_history_audit.analyze
uv run python -m test.replay_nov14
```

首次输出指version-0，编译失败仍计失败；最终取公开修复流程最后保留的可执行版本，不看隐藏分数挑选。当前任务和init+全部历史文件分别评分，首次/最终共640项比较。同页同测试集合只跑一次，首个决定性失败后停止，只解释任务全过与否。

阶段为`artifacts/prefix-factorial-v2-20261114`；中止阶段为`prefix-factorial-20261114`。结果在`test/results/prefix-factorial.json`及`实验结果.md`第24节。两个版本的`run.py`和`PROTOCOL.md`、正式`score.py`及冻结依赖不可修改；原前缀校准另见`test/prefix_history_audit/`。所有账本按日期计划只读汇总，新条件另立阶段，不放宽关闭账本。

本实验仍用参考来源/人工槽位库，仅两模型、一项目、一种子；参考前缀同时改变质量和来源，输出形式包含编译合同差异，不能归因成纯错误继承效应，也不能替代自建库或跨项目证据。
