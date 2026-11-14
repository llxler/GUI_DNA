# 原六库的条件布尔配置对照

协议在[PROTOCOL.md](PROTOCOL.md)。这是零API的事后诊断，使用原六套模型库，不使用11月14日修复后的库。

固定每库原GPT-OSS task-20最后可执行方案中的非布尔值、键集合和数组长度，只切换已出现的布尔叶子。布尔数≤5时穷举，否则按冻结种子均匀无放回抽32项；共129配置、645项task-4/8/12/16/20比较。这不覆盖省略的可选字段，也不是整个schema的均匀随机抽样。通过配置给出可达见证；没有见证不是不可达证明。

```bash
# 已保存报告的只读审计和汇总。
uv run python -m test.library_toggle_control.analyze

# 仅补缺失的本地浏览器评分；BOM不得与其他BOM评分同时运行。
uv run python -m test.library_toggle_control.run evaluate --project calculator
uv run python -m test.library_toggle_control.run evaluate --project table
uv run python -m test.library_toggle_control.run evaluate --project bom
```

阶段为`artifacts/library-toggle-control-20261114`，结果为`test/results/library-toggle-control.json`及`实验结果.md`第23节。旧53/120见证统计不改，新见证另算并集。`run.py`、`PROTOCOL.md`及其冻结清单中的依赖/输入不能修改；分析脚本不回传成绩，不修改原规划输出，不按得分选择重跑。
