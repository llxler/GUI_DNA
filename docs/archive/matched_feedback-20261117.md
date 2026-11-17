# 匹配公开反馈的完整目标对照（2026-11-16）

在原calculator/table/bom六套模型库上，对完整20任务目标比较无库代码、同库代码和组装方案。公开文件固定为init、task-4/8/12/16，所有做法获得相同源码与反馈；其余16个文件不进本次消息。GPT-OSS-120B low每条件两个实际发送的seed，共30候选。同库两种做法的user消息逐字一致。无库候选跨建库者共享，只计6个。

每次20,000输出token，最多三次响应；公开五文件全过可提前停止。首次取原始响应0，最终取最后响应，格式失败保留，不回退到更早可执行版本。代码可调用并修改冻结编译器。协议在[PROTOCOL.md](PROTOCOL.md)，原始记录在`artifacts/matched-feedback-20261116/`。

`__init__.py/core.py/browser.py/prepare.py/run.py/evaluate.py/PROTOCOL.md`以及`snapshot.json`列出的依赖均已冻结，不原地修改。`analyze.py`与本README可维护。不要重开关闭的账本或重新运行生成入口覆盖记录；新条件另立阶段。原第三轮仍暂停。

只读重算（不调用模型、不重新评分）：

```bash
uv run python -m test.matched_feedback.analyze
uv run python -m test.authorized_costs --date 20261116
uv run python -m test.replay_nov16
```

当前文件、留测16文件和完整21文件分别评分；首次/最终与12个固定示例共216端点比较，按相同项目、完整源码和测试集合去重。两个模型队列全部生成后，依次完成本队列、GPT-5队列、BOM配置搜索的评分，BOM串行。保存首败截断报告，不把未运行断言当通过，也不汇报这种记录的逐断言均分。

这是看到旧历史结果后的探索性跟进，不是研究者从未见过留测的确认性设计；不与原全隐藏主表合并，不代表浏览器工具代理。相同上限不等于实际计算量相等，汇总另报推理、缓存、响应长度和费用。
