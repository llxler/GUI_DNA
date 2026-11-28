# 机器可读结果

当前论文 Table 1 的各格存于 [paper-performance-matrix.json](paper-performance-matrix.json)。按项目和模型浏览成绩及其来源，请用[首页的 A、B、C 分区](../../README.md#按数据集模型和方法查-table-1)。

历次端到端比较使用 `by_builder`、`by_project_builder`、`by_generator_builder`，每组与共用无库基线的目标和分母一致；费用同样按建库者分开。旧聚合字段仅供对账。

早期端到端工作流的入口是 [`end_to_end.json`](end_to_end.json)：AI 建库＋GUI-DNA 对真实无库生成。它记录源哈希、真实候选路径、当前任务指标、基线去重、建库费用和报告范围；其中 `cohorts` 由历史记录重算，`canvas_pilots` 与 `matched_flex` 为新运行的独立对照。每个重复的 `settled_attempts` 提供响应哈希、结束原因、token 数与实际费用，`rows` 保留任务、生成状态和官方评分报告哈希。

```bash
uv run python -m studies.end_to_end --check
```

原有带日期和研究名称的 JSON 保持原始记录，不删方法、不替换分数、不覆盖失败。`free_lib` 表示真实的历史同库自由代码条件，不能改成 `free`。没有无库条件的阶段不出现在主比较表中。

`paper_end_to_end_audit.json` 和 `paper_format_end_to_end.json` 是当前本地稿件的检查；旧 `paper-*`、`replay-*` 报告只证明其登记的历史版本。源码 checkout 中没有所有被忽略的页面、响应和账本，不能据这些摘要宣称完成全历史浏览器复现。详见 [复现说明](../../docs/reproducibility.md)。
