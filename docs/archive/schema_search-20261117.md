# 五库非布尔与字段省略搜索（零API）

在原六库中排除已完整枚举的calculator/GPT-5，固定其余五库及原锚点。每库两个文档示例加原GPT-OSS/task-20最终方案，生成单处枚举、整数边界/中点、数组结构、可选字段省略/插入候选；保留锚点后按方案哈希排序，最多32个。实际158配置，共316端点比较、288个不同项目/源码/测试集合。选择不读取本次评分，既有布尔叶子不直接翻转，但省略和补入可改变默认行为。

完整协议见[PROTOCOL.md](PROTOCOL.md)，原始记录在`artifacts/schema-search-20261116/`。`run.py/population.py/__init__.py/PROTOCOL.md`及`snapshot.json`列出的依赖/方案/源码已冻结，不能修改。`analyze.py`和README可维护。

```bash
uv run python -m test.schema_search.analyze
uv run python -m test.replay_nov16
```

这些入口只重构保存的报告。评分端点是当前task-20和同页init+task-1..20，三个最终参考均校准；BOM空白页意外通过task-20，原入口因此停止且未评分BOM候选。例外和额外空白完整历史负对照见`test/schema_search_continue/`，后者续评原配置，不能改原冻结入口或伪造完成标记。BOM当前通过不单独证明目标功能正确。BOM在两队列匹配反馈评分结束后串行执行。相同项目/源码/测试集合仅评分一次，原报告和原53/120、14/120见证时间点保留。

通过给出合法配置的执行见证；失败只说明这次有界搜索没找到，不是整个模式不可达证明，也不是整个模式均匀随机采样或全部120个库/任务配对重审。
