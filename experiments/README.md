# Historical Experiment Runners

这里是早期原型与冻结运行器。当前公开基准研究位于 [`studies/`](../studies/README.md)，工程测试位于 [`tests/`](../tests/README.md)。

- `scale_study/`：第三轮冻结机制实验，190/640 候选后人工暂停；仅只读审计，不随当前任务恢复付费调用。
- `round2/`：第二轮分析和辅助脚本。
- `plan_linker.py` / `replay_linked_plans.py`：历史连接器复验，路径与源码被旧 manifest 固定。
- `TODO.md`：指向 [`todo.md`](../todo.md) 的兼容入口；新文档使用正式路径。

```bash
uv run python -m experiments.audit_scale
```

不要将本目录旧的合成任务和人工接口实验写成当前模型建库的公开基准结果。
