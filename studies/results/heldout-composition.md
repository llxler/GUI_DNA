# 自建库与未见行为组合（合成诊断）

Synthetic Web-Bench-inspired policy composition; human-authored behavior axes and DOM contract, model-proposed interface. Not official benchmark scores, broad project transfer, or evidence that LLM planning is necessary.

## main

| 应用 | 建库者 | 规划者 | 同库代码 | 方案 | 无模型差分 | 固定最终页 | 方案对代码W/L |
|---|---|---|---:|---:|---:|---:|---|
| calculator | openai/gpt-5 | openai/gpt-oss-120b | 11/11 | 11/11 | 11/11 | 1/11 | 0/0 |
| calculator | openai/gpt-5 | mistralai/mistral-small-3.2-24b-instruct | 11/11 | 11/11 | 11/11 | 1/11 | 0/0 |
| calculator | anthropic/claude-sonnet-4.5 | openai/gpt-oss-120b | 11/11 | 11/11 | 11/11 | 1/11 | 0/0 |
| calculator | anthropic/claude-sonnet-4.5 | mistralai/mistral-small-3.2-24b-instruct | 11/11 | 11/11 | 11/11 | 1/11 | 0/0 |
| table | openai/gpt-5 | openai/gpt-oss-120b | 11/11 | 11/11 | 11/11 | 1/11 | 0/0 |
| table | openai/gpt-5 | mistralai/mistral-small-3.2-24b-instruct | 11/11 | 11/11 | 11/11 | 1/11 | 0/0 |
| table | anthropic/claude-sonnet-4.5 | openai/gpt-oss-120b | 11/11 | 11/11 | 11/11 | 1/11 | 0/0 |
| table | anthropic/claude-sonnet-4.5 | mistralai/mistral-small-3.2-24b-instruct | 11/11 | 11/11 | 11/11 | 1/11 | 0/0 |

{"free": {"n": 44, "first": 32, "final": 32}, "free_lib": {"n": 88, "first": 88, "final": 88}, "plan": {"n": 88, "first": 88, "final": 88}}

## strong

| 应用 | 建库者 | 规划者 | 同库代码 | 方案 | 无模型差分 | 固定最终页 | 方案对代码W/L |
|---|---|---|---:|---:|---:|---:|---|
| calculator | openai/gpt-5 | openai/gpt-5 | 3/3 | 3/3 | 3/3 | 1/3 | 0/0 |
| calculator | anthropic/claude-sonnet-4.5 | openai/gpt-5 | 3/3 | 3/3 | 3/3 | 1/3 | 0/0 |
| table | openai/gpt-5 | openai/gpt-5 | 3/3 | 3/3 | 3/3 | 1/3 | 0/0 |
| table | anthropic/claude-sonnet-4.5 | openai/gpt-5 | 3/3 | 3/3 | 3/3 | 1/3 | 0/0 |

{"free_lib": {"n": 12, "first": 12, "final": 12}, "plan": {"n": 12, "first": 12, "final": 12}}
