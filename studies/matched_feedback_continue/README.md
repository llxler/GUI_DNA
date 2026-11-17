> 版本边界：当前分支已抽出公共工具；原阶段哈希复验使用移除前的 Git 版本。见 [退役记录](../../docs/archive/full-history-retirement.md)。原始成绩与账本未改。

# GPT-5预算断点续补

初始匹配反馈队列在并发请求的最坏费用预留阈值处阻止了部分新调用。此入口使用新目录和新账本，只补尚未发出的请求；原目录、账本、已完整响应和公开报告保留。协议见[PROTOCOL.md](PROTOCOL.md)，模型、输入、反馈、输出上限与最多两次修复均不变。续补改为串行，实际缓存和费用另列。

`run.py/__init__.py/PROTOCOL.md`和新`snapshot.json`列出的源码、原阶段记录、复制的既有输出与公开报告在续补前冻结。新候选完成后另有`candidate-snapshot.json`。关闭账本不能重开，不要再次执行生成或覆盖既有记录；后续任何断点必须另行归档和登记。

最终副本目录为`artifacts/matched-feedback-frontier-continue-20261116/`。公开缓存复用前核对原报告哈希；已有调用必须已结算，且请求消息、模型逐字一致才可重放，未知预留拒绝自动重复。原/新账本在汇总时合并，拷贝请求不重复计费。

```bash
uv run python -m test.matched_feedback_frontier.analyze
uv run python -m test.authorized_costs --date 20261116
uv run python -m test.replay_nov16
```

以上只读重算。最终状态以新目录`generation-complete.json/evaluation-complete.json`为准；未完成时不能声称15候选全部有效或启动本组隐藏评分。初始阶段没有隐藏评分。新组评分前仍需全部生成完成，并与基础GPT-OSS及BOM配置搜索顺序隔离。
