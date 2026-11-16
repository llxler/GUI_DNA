# BOM负对照异常后的零API续评

原BOM候选评分前发现官方task-20让空白页通过，原入口按预定断言停止。原报告与错误假设保留；[PROTOCOL.md](PROTOCOL.md)在任何BOM候选评分前记录了例外及续评规则。原三个断言将null视为defined并提前返回，不能把该端点的通过独立当作功能见证。

续评只使用原冻结的64配置/102去重作业；另加空白完整历史负对照。原calculator/table评分逐字保留。`run.py`、`__init__.py`、`PROTOCOL.md`及`snapshot.json`依赖已冻结，不得修改或重跑挑选；分析入口合并两个阶段，保留两套原报告。

```bash
uv run python -m test.schema_search.analyze
uv run python -m test.replay_nov16
```

只读入口会重编译158配置、检查原始报告，并重做null/undefined的本地matcher探针，不再运行浏览器或API。整套原官方分数不回填。
