# 模型自行设计接口的两项目对照

所有做法独立从累计需求生成完整页面；同库自由代码和方案的 user 消息相同。缺失不是模型失败。
普通自由代码在两个建库者之间复用，不重复计为独立样本；下表逐建库者报告。

| 项目 | 建库者 | 规划者 | 自由代码 | 同库自由代码 | 方案 | 方案 vs 同库 胜/负/平 |
|---|---|---|---:|---:|---:|---:|
| dom1 | openai/gpt-5 | openai/gpt-oss-120b | 6/20 | 10/20 | 10/20 | 0/0/20 |
| dom1 | openai/gpt-5 | mistralai/mistral-small-3.2-24b-instruct | 4/20 | 0/20 | 10/20 | 10/0/10 |
| dom1 | anthropic/claude-sonnet-4.5 | openai/gpt-oss-120b | 6/20 | 12/20 | 11/20 | 1/2/17 |
| dom1 | anthropic/claude-sonnet-4.5 | mistralai/mistral-small-3.2-24b-instruct | 4/20 | 9/20 | 11/20 | 2/0/18 |
| form | openai/gpt-5 | openai/gpt-oss-120b | 9/20 | 12/20 | 14/20 | 2/0/18 |
| form | openai/gpt-5 | mistralai/mistral-small-3.2-24b-instruct | 6/20 | 4/20 | 9/20 | 6/1/13 |
| form | anthropic/claude-sonnet-4.5 | openai/gpt-oss-120b | 9/20 | 12/20 | 8/20 | 2/6/12 |
| form | anthropic/claude-sonnet-4.5 | mistralai/mistral-small-3.2-24b-instruct | 6/20 | 8/20 | 13/20 | 5/0/15 |

| 阶段 | 已结算美元 | 含预留敞口 | 未结算调用 |
|---|---:|---:|---:|
| build | 0.240875 | 0.240875 | 0 |
| generation | 0.347864 | 0.355965 | 1 |
| build_previous_0 | 0.533831 | 0.808423 | 1 |
| generation_previous_0 | 0.051227 | 0.201338 | 17 |
| generation_previous_1 | 0.375538 | 1.097821 | 73 |
| generation_previous_2 | 0.018628 | 0.056404 | 4 |
| generation_previous_3 | 0.096572 | 0.153876 | 7 |

解释边界：

- Two projects, two planners, one sample; correlated tasks; no project-level significance claim.
- Builders see the entire public requirement sequence; not held-out requirement transfer.
- The public form requirements themselves specify classes and inheritance.
- Libraries are not behaviorally verified; first public-valid output frozen without hidden selection.
- Free baselines are reused across builders and must not be counted twice.
