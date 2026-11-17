# 事后布尔并集诊断

协议：[PROTOCOL.md](PROTOCOL.md)。结果独立于原预定严格合并控制，不改变原库/候选。

```bash
uv run python -m test.interaction_union.analyze
```

run.py、PROTOCOL.md、__init__.py及初始analyze.py已由snapshot冻结；prepare/score已经执行，不重复写旧输入。8库中7个布尔并集计划可执行并全过，报告均按完整源码/项目/轨迹哈希精确复用，未新增浏览器报告。另1库仍有非布尔标量冲突，保留失败，不调整规则直到全过。完整页目标要求启用已知能力，这不是互斥或非单调需求的通用选择算法。
