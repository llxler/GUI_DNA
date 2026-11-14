# 六库修复的缺失响应续作

本目录补齐11月13日原六库实验缺失的六份响应，协议见[PROTOCOL.md](PROTOCOL.md)。六份完整旧响应逐字复制，包括格式失败；仅新增table/Sonnet和两套BOM库的review/feedback。旧消息、模型、供应商约束、seed与推理/输出预算保持不变。不能重抽完整失败，也不能放宽已关闭账本。

生成阶段为`artifacts/library-repair-resume-20261114`；完整重放另在`artifacts/library-repair-full-20261114`。续作前已观察三库子集结果，必须披露时间顺序；新修复输入没有加入旧隐藏成绩。180个不同旧候选，加固定最终方案和开发检查，在两种解析口径下形成1200项比较。严格JSON是主口径；唯一JSON代码块规则仅作独立诊断。

```bash
# 只读核验和汇总；不调用模型。
uv run python -m test.library_repair_resume.replay analyze
uv run python -m test.library_repair_resume.entrypoint analyze
uv run python -m test.authorized_costs --date 20261114
uv run python -m test.replay_nov14
```

最后一个入口须等同日其他诊断也完成。结果统一写入`实验结果.md`第22节和`test/results/library-repair-full.json`。原第21节保留为当时的三库快照，不能回填成当时已补齐。

`run.py`、`PROTOCOL.md`、`replay.py`、`entrypoint.py`、`ENTRYPOINT.md`及清单列出的原库/修复源码与观察文件均已冻结，不要修改、格式化或覆盖。`replay analyze`验证原工作区哈希；匿名导出重写路径后用`test.replay_nov14`和导出清单验证。实现变化不能保证接口语义保持，重放也不等于新规划、非模板迁移或独立复现。

完整重放后另做单例包装缺陷干预，见[ENTRYPOINT.md](ENTRYPOINT.md)：Sonnet的两份table修订省略index.js占位键，编译器因而未生成入口。在固定原GPT-OSS/task-4方案上，原页删入口由通过变失败；两修订只恢复占位键后都由失败变通过。共六页、三份精确旧报告和三份新增评分，仅解释这一配置/测试，不回写模型成绩。
