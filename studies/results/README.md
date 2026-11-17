# Saved Results and Reporting Views

展示统一使用 `by_builder`、`by_project_builder`、`by_generator_builder`，每组与共用无库基线的目标和分母一致；费用同样按建库者分开。旧聚合字段仅供对账。

当前主比较入口是 [`end_to_end.json`](end_to_end.json)：AI 建库＋GUI-DNA 对真实无库生成。它记录源哈希、真实候选路径、两种端点、基线去重、建库费用和报告范围；是事后派生视图，不是新模型实验。

```bash
uv run python -m studies.end_to_end --check
```

原有带日期和研究名称的 JSON 保持原始记录，不删方法、不替换分数、不覆盖失败。`free_lib` 表示真实的历史同库自由代码条件，不能改成 `free`。没有无库条件的阶段不出现在主比较表中。

`paper_end_to_end_audit.json` 和 `paper_format_end_to_end.json` 是当前本地稿件的检查；旧 `paper-*`、`replay-*` 报告只证明其登记的历史版本。源码 checkout 中没有所有被忽略的页面、响应和账本，不能据这些摘要宣称完成全历史浏览器复现。详见 [复现说明](../../docs/reproducibility.md)。
