# 既有 Web-Bench 页面的完整历史复验

协议：[PROTOCOL.md](PROTOCOL.md)，正参考标注修正：[REFERENCE.md](REFERENCE.md)。独立阶段 `artifacts/history-replay-20261115`，零 API。1640个原候选/规则页的首次、最终版本，加730个固定对照端点，共4010比较；相同项目、运行环境、全部源文件及测试集合去重为1650项浏览器工作。旧分数和源码不回写。

```bash
uv run python -m test.history_replay.run prepare
uv run python -m test.history_replay.run calibrate
uv run python -m test.history_replay.reference prepare
uv run python -m test.history_replay.reference calibrate
uv run python -m test.history_replay.reference evaluate
uv run python -m test.history_replay.analyze
uv run python -m test.history_replay.diagnostics
uv run python -m test.history_replay.witnesses
```

前四步已有冻结产物时不能再执行。续接已固定队列只用reference evaluate；存在未完成原始报告会停下，不能覆盖或择优重跑。BOM仅一个队列，其他最多四项并发。原朴素规则控制最初误标正参考的校准完整保留，真正正参考另行校准，无模型候选评分前完成。

冻结文件：run.py、PROTOCOL.md、reference.py、REFERENCE.md、两个快照列出的来源/测试/运行依赖。analyze.py为只读汇总入口。完整历史是同一个C_k上的init与task-1..k联合通过，不是多个不同页面旧成绩相与；first沿用旧实验的首次可执行版本。旧当前任务成绩来自历史观测，日期/调度噪声不能排除。

`witnesses`是事后只读可达下界：对原三项目六库的已有合法计划和固定控制，找到14/120个完整历史通过配对，并从原包逐字重编译正见证。它没有搜索或新增浏览器评分，不能把其余106配对称为不可达；也不替换旧当前文件53/120口径。
