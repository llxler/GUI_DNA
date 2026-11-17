# 公开行为反馈小试

这是独立公开/隐藏划分，只在同库两种做法均有效的共同任务上比较修复前后；不能把这里的通过率直接拼入全隐藏主表。

| 项目 | 建库者 | 规划者 | 同库自由代码：修复前→后 | 方案：修复前→后 | 最终方案 vs 同库 胜/负/平 |
|---|---|---|---:|---:|---:|
| dom1 | anthropic/claude-sonnet-4.5 | mistralai/mistral-small-3.2-24b-instruct | 2→3/5 | 2→2/5 | 0/1/4 |
| dom1 | anthropic/claude-sonnet-4.5 | openai/gpt-oss-120b | 2→2/5 | 3→3/5 | 1/0/4 |
| dom1 | openai/gpt-5 | mistralai/mistral-small-3.2-24b-instruct | 0→0/5 | 2→2/5 | 2/0/3 |
| dom1 | openai/gpt-5 | openai/gpt-oss-120b | 2→2/5 | 2→2/5 | 0/0/5 |
| form | anthropic/claude-sonnet-4.5 | mistralai/mistral-small-3.2-24b-instruct | 1→2/5 | 2→2/5 | 0/0/5 |
| form | anthropic/claude-sonnet-4.5 | openai/gpt-oss-120b | 2→2/5 | 2→2/5 | 0/0/5 |
| form | openai/gpt-5 | mistralai/mistral-small-3.2-24b-instruct | 1→1/5 | 2→2/5 | 1/0/4 |
| form | openai/gpt-5 | openai/gpt-oss-120b | 2→2/5 | 2→2/5 | 0/0/5 |

新增行为修复费用：已结算 $0.122873；含预留 $0.290186。
缺失或未评分：0 个候选。

每项目只有五个相关里程碑、两个规划模型和两个库；不据此进行跨项目显著性推断。给出具体断言反馈仍不等于具备浏览器工具的完整代理。
