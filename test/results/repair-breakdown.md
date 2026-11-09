# 收益来自首次还是修复？（首次即对 / 修复后才对 / 修复也不对）

零 API，`uv run python -m test.repair_breakdown`。每个候选按隐藏测试全过与否分三类：**首次即对**（第一个版本全过）、**修复后才对**（首个版本失败、最终版本全过）、**修复也不对**（最终版本仍失败）；「首次对、最终错」单列。自建任务只计 47 个完整四方法组（与 analyze.py 相同）。

| 数据集 | 做法 | n | 首次即对 | 修复后才对 | 修复也不对 | 首次对最终错 |
|---|---|---:|---:|---:|---:|---:|
| List-16 | Free | 47 | 17 | 10 | 20 | 0 |
| List-16 | Free+Lib | 47 | 36 | 3 | 8 | 0 |
| List-16 | Plan- | 47 | 35 | 5 | 7 | 0 |
| List-16 | GUI-DNA | 47 | 33 | 14 | 0 | 0 |
| TodoMVC | Free | 128 | 101 | 15 | 12 | 0 |
| TodoMVC | Free+Lib | 128 | 100 | 10 | 18 | 0 |
| TodoMVC | Rule | 128 | 16 | 0 | 112 | 0 |
| TodoMVC | Plan- | 128 | 128 | 0 | 0 | 0 |
| TodoMVC | GUI-DNA | 128 | 128 | 0 | 0 | 0 |
| Web-Bench dom1 | Free | 160 | 53 | 1 | 106 | 0 |
| Web-Bench dom1 | Free+Lib | 160 | 96 | 3 | 61 | 0 |
| Web-Bench dom1 | Rule | 160 | 64 | 0 | 96 | 0 |
| Web-Bench dom1 | Plan- | 160 | 133 | 0 | 27 | 0 |
| Web-Bench dom1 | GUI-DNA | 160 | 132 | 0 | 28 | 0 |

## 逐模型（自由代码与 GUI-DNA）

| 数据集 | 做法 | 模型 | n | 首次即对 | 修复后才对 | 修复也不对 |
|---|---|---|---:|---:|---:|---:|
| List-16 | Free | qwen/qwen3-coder-plus | 20 | 10 | 4 | 6 |
| List-16 | Free | deepseek/deepseek-v4-pro-0813 | 27 | 7 | 6 | 14 |
| List-16 | Free+Lib | qwen/qwen3-coder-plus | 20 | 12 | 1 | 7 |
| List-16 | Free+Lib | deepseek/deepseek-v4-pro-0813 | 27 | 24 | 2 | 1 |
| List-16 | GUI-DNA | qwen/qwen3-coder-plus | 20 | 18 | 2 | 0 |
| List-16 | GUI-DNA | deepseek/deepseek-v4-pro-0813 | 27 | 15 | 12 | 0 |
| TodoMVC | Free | deepseek/deepseek-v4-pro-0813 | 16 | 16 | 0 | 0 |
| TodoMVC | Free | qwen/qwen3-coder-30b-a3b-instruct | 16 | 13 | 2 | 1 |
| TodoMVC | Free | mistralai/mistral-small-3.2-24b-instruct | 16 | 9 | 3 | 4 |
| TodoMVC | Free | google/gemma-3-12b-it | 16 | 0 | 9 | 7 |
| TodoMVC | Free | openai/gpt-5-mini | 16 | 15 | 1 | 0 |
| TodoMVC | Free | openai/gpt-oss-120b | 16 | 16 | 0 | 0 |
| TodoMVC | Free | google/gemini-2.5-flash | 16 | 16 | 0 | 0 |
| TodoMVC | Free | anthropic/claude-haiku-4.5 | 16 | 16 | 0 | 0 |
| TodoMVC | Free+Lib | deepseek/deepseek-v4-pro-0813 | 16 | 16 | 0 | 0 |
| TodoMVC | Free+Lib | qwen/qwen3-coder-30b-a3b-instruct | 16 | 14 | 1 | 1 |
| TodoMVC | Free+Lib | mistralai/mistral-small-3.2-24b-instruct | 16 | 4 | 5 | 7 |
| TodoMVC | Free+Lib | google/gemma-3-12b-it | 16 | 2 | 4 | 10 |
| TodoMVC | Free+Lib | openai/gpt-5-mini | 16 | 16 | 0 | 0 |
| TodoMVC | Free+Lib | openai/gpt-oss-120b | 16 | 16 | 0 | 0 |
| TodoMVC | Free+Lib | google/gemini-2.5-flash | 16 | 16 | 0 | 0 |
| TodoMVC | Free+Lib | anthropic/claude-haiku-4.5 | 16 | 16 | 0 | 0 |
| TodoMVC | GUI-DNA | deepseek/deepseek-v4-pro-0813 | 16 | 16 | 0 | 0 |
| TodoMVC | GUI-DNA | qwen/qwen3-coder-30b-a3b-instruct | 16 | 16 | 0 | 0 |
| TodoMVC | GUI-DNA | mistralai/mistral-small-3.2-24b-instruct | 16 | 16 | 0 | 0 |
| TodoMVC | GUI-DNA | google/gemma-3-12b-it | 16 | 16 | 0 | 0 |
| TodoMVC | GUI-DNA | openai/gpt-5-mini | 16 | 16 | 0 | 0 |
| TodoMVC | GUI-DNA | openai/gpt-oss-120b | 16 | 16 | 0 | 0 |
| TodoMVC | GUI-DNA | google/gemini-2.5-flash | 16 | 16 | 0 | 0 |
| TodoMVC | GUI-DNA | anthropic/claude-haiku-4.5 | 16 | 16 | 0 | 0 |
| Web-Bench dom1 | Free | qwen/qwen3-coder-30b-a3b-instruct | 20 | 5 | 0 | 15 |
| Web-Bench dom1 | Free | mistralai/mistral-small-3.2-24b-instruct | 20 | 5 | 0 | 15 |
| Web-Bench dom1 | Free | google/gemma-3-12b-it | 20 | 2 | 0 | 18 |
| Web-Bench dom1 | Free | deepseek/deepseek-v4-flash | 20 | 12 | 0 | 8 |
| Web-Bench dom1 | Free | openai/gpt-oss-120b | 20 | 7 | 0 | 13 |
| Web-Bench dom1 | Free | google/gemini-2.5-flash | 20 | 10 | 1 | 9 |
| Web-Bench dom1 | Free | openai/gpt-5-mini | 20 | 6 | 0 | 14 |
| Web-Bench dom1 | Free | anthropic/claude-haiku-4.5 | 20 | 6 | 0 | 14 |
| Web-Bench dom1 | Free+Lib | qwen/qwen3-coder-30b-a3b-instruct | 20 | 11 | 0 | 9 |
| Web-Bench dom1 | Free+Lib | mistralai/mistral-small-3.2-24b-instruct | 20 | 3 | 2 | 15 |
| Web-Bench dom1 | Free+Lib | google/gemma-3-12b-it | 20 | 0 | 0 | 20 |
| Web-Bench dom1 | Free+Lib | deepseek/deepseek-v4-flash | 20 | 15 | 0 | 5 |
| Web-Bench dom1 | Free+Lib | openai/gpt-oss-120b | 20 | 18 | 0 | 2 |
| Web-Bench dom1 | Free+Lib | google/gemini-2.5-flash | 20 | 18 | 0 | 2 |
| Web-Bench dom1 | Free+Lib | openai/gpt-5-mini | 20 | 15 | 0 | 5 |
| Web-Bench dom1 | Free+Lib | anthropic/claude-haiku-4.5 | 20 | 16 | 1 | 3 |
| Web-Bench dom1 | GUI-DNA | qwen/qwen3-coder-30b-a3b-instruct | 20 | 17 | 0 | 3 |
| Web-Bench dom1 | GUI-DNA | mistralai/mistral-small-3.2-24b-instruct | 20 | 18 | 0 | 2 |
| Web-Bench dom1 | GUI-DNA | google/gemma-3-12b-it | 20 | 6 | 0 | 14 |
| Web-Bench dom1 | GUI-DNA | deepseek/deepseek-v4-flash | 20 | 18 | 0 | 2 |
| Web-Bench dom1 | GUI-DNA | openai/gpt-oss-120b | 20 | 17 | 0 | 3 |
| Web-Bench dom1 | GUI-DNA | google/gemini-2.5-flash | 20 | 20 | 0 | 0 |
| Web-Bench dom1 | GUI-DNA | openai/gpt-5-mini | 20 | 18 | 0 | 2 |
| Web-Bench dom1 | GUI-DNA | anthropic/claude-haiku-4.5 | 20 | 18 | 0 | 2 |
