# 配对差与聚类 bootstrap 区间（GUI-DNA − 基线，单位：百分点）

零 API，`uv run python -m test.paired_intervals`。统计口径与第三轮 `paired_interval()` 相同：按簇（TodoMVC 为功能族 = 任务 id；Web-Bench 为任务 id）有放回重抽 10,000 次，取重抽均值的 2.5% / 97.5% 分位。合计行另给「以模型为簇」的区间。

## TodoMVC (official Playwright tests)（summary 生成于 2026-11-09T12:17:39Z）

| 范围 | 对比 | 版本 | n 对 | 差值 | 95% 区间（任务簇） | 95% 区间（模型簇） | 胜/负/平 |
|---|---|---|---:|---:|---:|---:|---:|
| 合计（8 模型） | vs Free | final | 314 | +8.3 | [5.0, 11.9] | [0.3, 19.9] | 26/0/288 |
| 合计（8 模型） | vs Free | first | 314 | +16.9 | [15.5, 18.4] | [1.6, 40.1] | 53/0/261 |
| deepseek/deepseek-v4-pro-0813 | vs Free | final | 40 | +0.0 | [0.0, 0.0] | — | 0/0/40 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Free | final | 40 | +2.5 | [0.0, 7.5] | — | 1/0/39 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Free | first | 40 | +12.5 | [2.5, 25.0] | — | 5/0/35 |
| mistralai/mistral-small-3.2-24b-instruct | vs Free | final | 40 | +20.0 | [2.5, 42.5] | — | 8/0/32 |
| mistralai/mistral-small-3.2-24b-instruct | vs Free | first | 40 | +32.5 | [20.0, 50.0] | — | 13/0/27 |
| google/gemma-3-12b-it | vs Free | final | 34 | +50.0 | [31.6, 70.4] | — | 17/0/17 |
| google/gemma-3-12b-it | vs Free | first | 34 | +100.0 | [100.0, 100.0] | — | 34/0/0 |
| openai/gpt-5-mini | vs Free | final | 40 | +0.0 | [0.0, 0.0] | — | 0/0/40 |
| openai/gpt-5-mini | vs Free | first | 40 | +2.5 | [0.0, 7.5] | — | 1/0/39 |
| openai/gpt-oss-120b | vs Free | final | 40 | +0.0 | [0.0, 0.0] | — | 0/0/40 |
| google/gemini-2.5-flash | vs Free | final | 40 | +0.0 | [0.0, 0.0] | — | 0/0/40 |
| anthropic/claude-haiku-4.5 | vs Free | final | 40 | +0.0 | [0.0, 0.0] | — | 0/0/40 |

## Web-Bench dom1 (official tests)（summary 生成于 2026-11-09T08:42:59Z）

| 范围 | 对比 | 版本 | n 对 | 差值 | 95% 区间（任务簇） | 95% 区间（模型簇） | 胜/负/平 |
|---|---|---|---:|---:|---:|---:|---:|
| 合计（8 模型） | vs Free | final | 160 | +48.8 | [36.2, 61.2] | [37.5, 58.1] | 79/1/80 |
| 合计（8 模型） | vs Free | first | 160 | +49.4 | [36.9, 61.2] | [38.1, 58.8] | 80/1/79 |
| 合计（8 模型） | vs Free+Lib | final | 160 | +20.6 | [14.4, 27.5] | [8.1, 36.2] | 35/2/123 |
| 合计（8 模型） | vs Free+Lib | first | 160 | +22.5 | [15.6, 29.4] | [9.4, 40.0] | 38/2/120 |
| 合计（8 模型） | vs Plan- | final | 160 | -0.6 | [-3.1, 1.9] | [-3.8, 1.9] | 2/3/155 |
| 合计（8 模型） | vs Plan- | first | 160 | -0.6 | [-3.1, 1.9] | [-3.8, 1.9] | 2/3/155 |
| 合计（8 模型） | vs Rule | final | 160 | +42.5 | [23.1, 61.9] | [26.2, 52.5] | 72/4/84 |
| 合计（8 模型） | vs Rule | first | 160 | +42.5 | [23.1, 61.9] | [26.2, 52.5] | 72/4/84 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Free | final | 20 | +60.0 | [40.0, 80.0] | — | 12/0/8 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Free+Lib | final | 20 | +30.0 | [10.0, 50.0] | — | 6/0/14 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Plan- | final | 20 | +0.0 | [0.0, 0.0] | — | 0/0/20 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Rule | final | 20 | +45.0 | [25.0, 65.0] | — | 9/0/11 |
| mistralai/mistral-small-3.2-24b-instruct | vs Free | final | 20 | +65.0 | [45.0, 85.0] | — | 13/0/7 |
| mistralai/mistral-small-3.2-24b-instruct | vs Free+Lib | final | 20 | +65.0 | [45.0, 85.0] | — | 13/0/7 |
| mistralai/mistral-small-3.2-24b-instruct | vs Free+Lib | first | 20 | +75.0 | [55.0, 95.0] | — | 15/0/5 |
| mistralai/mistral-small-3.2-24b-instruct | vs Plan- | final | 20 | +5.0 | [0.0, 15.0] | — | 1/0/19 |
| mistralai/mistral-small-3.2-24b-instruct | vs Rule | final | 20 | +50.0 | [30.0, 70.0] | — | 10/0/10 |
| google/gemma-3-12b-it | vs Free | final | 20 | +20.0 | [0.0, 40.0] | — | 5/1/14 |
| google/gemma-3-12b-it | vs Free+Lib | final | 20 | +30.0 | [10.0, 50.0] | — | 6/0/14 |
| google/gemma-3-12b-it | vs Plan- | final | 20 | -10.0 | [-25.0, 0.0] | — | 0/2/18 |
| google/gemma-3-12b-it | vs Rule | final | 20 | -10.0 | [-35.0, 15.0] | — | 2/4/14 |
| deepseek/deepseek-v4-flash | vs Free | final | 20 | +30.0 | [10.0, 50.0] | — | 6/0/14 |
| deepseek/deepseek-v4-flash | vs Free+Lib | final | 20 | +15.0 | [0.0, 30.0] | — | 3/0/17 |
| deepseek/deepseek-v4-flash | vs Plan- | final | 20 | +0.0 | [-15.0, 15.0] | — | 1/1/18 |
| deepseek/deepseek-v4-flash | vs Rule | final | 20 | +50.0 | [30.0, 70.0] | — | 10/0/10 |
| openai/gpt-oss-120b | vs Free | final | 20 | +50.0 | [30.0, 70.0] | — | 10/0/10 |
| openai/gpt-oss-120b | vs Free+Lib | final | 20 | -5.0 | [-15.0, 0.0] | — | 0/1/19 |
| openai/gpt-oss-120b | vs Plan- | final | 20 | +0.0 | [0.0, 0.0] | — | 0/0/20 |
| openai/gpt-oss-120b | vs Rule | final | 20 | +45.0 | [25.0, 65.0] | — | 9/0/11 |
| google/gemini-2.5-flash | vs Free | final | 20 | +45.0 | [25.0, 65.0] | — | 9/0/11 |
| google/gemini-2.5-flash | vs Free | first | 20 | +50.0 | [30.0, 70.0] | — | 10/0/10 |
| google/gemini-2.5-flash | vs Free+Lib | final | 20 | +10.0 | [0.0, 25.0] | — | 2/0/18 |
| google/gemini-2.5-flash | vs Plan- | final | 20 | +0.0 | [0.0, 0.0] | — | 0/0/20 |
| google/gemini-2.5-flash | vs Rule | final | 20 | +60.0 | [40.0, 80.0] | — | 12/0/8 |
| openai/gpt-5-mini | vs Free | final | 20 | +60.0 | [40.0, 80.0] | — | 12/0/8 |
| openai/gpt-5-mini | vs Free+Lib | final | 20 | +15.0 | [0.0, 30.0] | — | 3/0/17 |
| openai/gpt-5-mini | vs Plan- | final | 20 | +0.0 | [0.0, 0.0] | — | 0/0/20 |
| openai/gpt-5-mini | vs Rule | final | 20 | +50.0 | [30.0, 70.0] | — | 10/0/10 |
| anthropic/claude-haiku-4.5 | vs Free | final | 20 | +60.0 | [40.0, 80.0] | — | 12/0/8 |
| anthropic/claude-haiku-4.5 | vs Free+Lib | final | 20 | +5.0 | [-10.0, 25.0] | — | 2/1/17 |
| anthropic/claude-haiku-4.5 | vs Free+Lib | first | 20 | +10.0 | [-10.0, 30.0] | — | 3/1/16 |
| anthropic/claude-haiku-4.5 | vs Plan- | final | 20 | +0.0 | [0.0, 0.0] | — | 0/0/20 |
| anthropic/claude-haiku-4.5 | vs Rule | final | 20 | +50.0 | [30.0, 70.0] | — | 10/0/10 |
