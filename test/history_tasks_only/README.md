# task-1..k历史证据（事后补充）

第25节主指标仍是init＋task-1..k全部通过。这里单独检查去除独立init文件后的证据，动机、复用规则及边界见[PROTOCOL.md](PROTOCOL.md)。不是重写原成绩或针对模型修复，也不排除task文件内部的初始/布局断言。

```bash
# 已完成的阶段不要再次prepare；下面两步只读汇总与复算
uv run python -m test.history_tasks_only.analyze
uv run python -m test.replay_nov15
```

范围沿用4010端点；1650旧报告中1311已有决定性的task正/负证据，339份因init截断而未知，另用同一冻结页面补测。全部来源、复用理由及新报告保留于`artifacts/history-tasks-only-20261115`。只有完整评分后才能解释结果；`evaluation-complete.json`为完成标记。

run.py、__init__.py、PROTOCOL.md及snapshot登记依赖已经冻结；不要原地编辑。analyze.py与本README不在冻结清单内。BOM仍须与其他浏览器阶段串行，不同时开第二个BOM队列。
