# Web-Bench canvas 匹配对照

[预先固定的协议](PROTOCOL.md)规定任务、重复数、输入、费用上限和当前任务指标。生成时只取公开需求文本及资源名，同一准备产物供该次重复的五个目标使用。校准和候选报告存于本地 artifacts/matched-canvas-20261118。

有原始材料时用 `uv run python -m studies.matched_canvas.analyze --check` 对照协议和源码哈希、20 个目标位置、原始浏览器报告、编译后的文件、实际模型回执及关闭的独立账本。公开的派生结果保留每个任务的状态、报告哈希、各重复费用和两组配对。旧阶段不追加调用。

执行顺序为 browser 校准、run 冻结并生成、evaluate 核对生成快照并评分、analyze 重算。生成命令属于已结算阶段的实现记录。独立的接口诊断使用 canvas_interface_probe 的公开操作，不参与候选生成。
