# GPT-5 预算断点续作

初始账本 cap $4.5 / stop $4.3 按预留上界触发停止，停止后已结算 $3.127263，含五次未确认中断的敞口 $3.984886。原账本已关闭，**没有放宽**。当时55条记录中48条完整、5条传输不完整、2条预算未发出末次请求；另5条尚未开始。

新阶段 `artifacts/webbench-expand-frontier-2` cap $2 / stop $1.8，复制全部55条记录（包括完整失败与部分有效尝试），未按成绩选择。`test.webbench_expand.frontier_continue` 只补未完成的请求与尚未开始的候选；模型、供应商、提示词、输出上限、最多两次修复都不变。降低并发至2，不增加有效采样次数。前一账本的未知预留继续计入当天预算；此时当天最坏敞口 $16.979706，低于 $20。

正式评分与汇总使用 `webbench-expand-frontier-2`，费用合并两个账本。原 `FRONTIER.md` 和生成文件已冻结，保留当时的账本与协议，不改写历史。

```bash
uv run python -m test.webbench_expand.frontier_continue --workers 2
# 等600个主候选、60个frontier候选都补齐，关闭两份新账本，再评分与汇总：
uv run python -m test.webbench_expand.offline_pipeline --wait
```
