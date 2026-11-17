# 参考输入页的完整历史检查

使用原20张`clean_page`输入页（前缀0–19），每页跑初始布局和此前所有任务文件。原阶段191个页面/文件配对，独立冻结扩展再检查非空前缀的19个init；合计210配对、909断言，全部通过。39份原始报告完整保留，没有按结果排除断言或重写测试。

```bash
uv run python -m test.prefix_history_audit.analyze
```

该入口只读汇总`artifacts/prefix-history-audit-20261114`，输出`test/results/prefix-history-audit.json`。运行采用原Playwright1.63和测试超时，不调用模型。结果说明所列断言通过，不是公开自然语言需求的形式证明。

`run.py`、`PROTOCOL.md`、`init_extension.py`已分别冻结；`analyze.py`也被后续前缀因子实验的评分快照引用。不要修改这些源码或已有评分。新条件使用新目录和清单。
