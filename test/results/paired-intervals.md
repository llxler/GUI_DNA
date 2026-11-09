# 配对差与聚类 bootstrap 区间（GUI-DNA − 基线，单位：百分点）

零 API，`uv run python -m test.paired_intervals`。统计口径与第三轮 `paired_interval()` 相同：按簇（TodoMVC 为功能族 = 任务 id；Web-Bench 为任务 id）有放回重抽 10,000 次，取重抽均值的 2.5% / 97.5% 分位。合计行另给「以模型为簇」的区间。

## TodoMVC (official Playwright tests)（summary 生成于 2026-11-03T07:08:33Z）

| 范围 | 对比 | 版本 | n 对 | 差值 | 95% 区间（任务簇） | 95% 区间（模型簇） | 胜/负/平 |
|---|---|---|---:|---:|---:|---:|---:|
| 合计（8 模型） | vs Free | final | 128 | +9.4 | [4.7, 14.8] | [0.8, 21.1] | 12/0/116 |
| 合计（8 模型） | vs Free | first | 128 | +21.1 | [17.2, 25.0] | [2.3, 46.9] | 27/0/101 |
| 合计（8 模型） | vs Free+Lib | final | 128 | +14.1 | [12.5, 16.4] | [0.8, 32.0] | 18/0/110 |
| 合计（8 模型） | vs Free+Lib | first | 128 | +21.9 | [18.0, 25.8] | [1.6, 50.0] | 28/0/100 |
| 合计（8 模型） | vs Plan- | final | 128 | +0.0 | [0.0, 0.0] | [0.0, 0.0] | 0/0/128 |
| 合计（8 模型） | vs Plan- | first | 128 | +0.0 | [0.0, 0.0] | [0.0, 0.0] | 0/0/128 |
| 合计（8 模型） | vs Rule | final | 128 | +87.5 | [62.5, 100.0] | [87.5, 87.5] | 112/0/16 |
| 合计（8 模型） | vs Rule | first | 128 | +87.5 | [62.5, 100.0] | [87.5, 87.5] | 112/0/16 |
| deepseek/deepseek-v4-pro-0813 | vs Free | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| deepseek/deepseek-v4-pro-0813 | vs Free+Lib | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| deepseek/deepseek-v4-pro-0813 | vs Plan- | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| deepseek/deepseek-v4-pro-0813 | vs Rule | final | 16 | +87.5 | [62.5, 100.0] | — | 14/0/2 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Free | final | 16 | +6.2 | [0.0, 18.8] | — | 1/0/15 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Free | first | 16 | +18.8 | [6.2, 37.5] | — | 3/0/13 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Free+Lib | final | 16 | +6.2 | [0.0, 18.8] | — | 1/0/15 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Free+Lib | first | 16 | +12.5 | [0.0, 31.2] | — | 2/0/14 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Plan- | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| qwen/qwen3-coder-30b-a3b-instruct | vs Rule | final | 16 | +87.5 | [62.5, 100.0] | — | 14/0/2 |
| mistralai/mistral-small-3.2-24b-instruct | vs Free | final | 16 | +25.0 | [6.2, 50.0] | — | 4/0/12 |
| mistralai/mistral-small-3.2-24b-instruct | vs Free | first | 16 | +43.8 | [25.0, 62.5] | — | 7/0/9 |
| mistralai/mistral-small-3.2-24b-instruct | vs Free+Lib | final | 16 | +43.8 | [25.0, 62.5] | — | 7/0/9 |
| mistralai/mistral-small-3.2-24b-instruct | vs Free+Lib | first | 16 | +75.0 | [56.2, 93.8] | — | 12/0/4 |
| mistralai/mistral-small-3.2-24b-instruct | vs Plan- | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| mistralai/mistral-small-3.2-24b-instruct | vs Rule | final | 16 | +87.5 | [62.5, 100.0] | — | 14/0/2 |
| google/gemma-3-12b-it | vs Free | final | 16 | +43.8 | [25.0, 62.5] | — | 7/0/9 |
| google/gemma-3-12b-it | vs Free | first | 16 | +100.0 | [100.0, 100.0] | — | 16/0/0 |
| google/gemma-3-12b-it | vs Free+Lib | final | 16 | +62.5 | [37.5, 81.2] | — | 10/0/6 |
| google/gemma-3-12b-it | vs Free+Lib | first | 16 | +87.5 | [75.0, 100.0] | — | 14/0/2 |
| google/gemma-3-12b-it | vs Plan- | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| google/gemma-3-12b-it | vs Rule | final | 16 | +87.5 | [62.5, 100.0] | — | 14/0/2 |
| openai/gpt-5-mini | vs Free | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| openai/gpt-5-mini | vs Free | first | 16 | +6.2 | [0.0, 18.8] | — | 1/0/15 |
| openai/gpt-5-mini | vs Free+Lib | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| openai/gpt-5-mini | vs Plan- | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| openai/gpt-5-mini | vs Rule | final | 16 | +87.5 | [62.5, 100.0] | — | 14/0/2 |
| openai/gpt-oss-120b | vs Free | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| openai/gpt-oss-120b | vs Free+Lib | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| openai/gpt-oss-120b | vs Plan- | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| openai/gpt-oss-120b | vs Rule | final | 16 | +87.5 | [62.5, 100.0] | — | 14/0/2 |
| google/gemini-2.5-flash | vs Free | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| google/gemini-2.5-flash | vs Free+Lib | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| google/gemini-2.5-flash | vs Plan- | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| google/gemini-2.5-flash | vs Rule | final | 16 | +87.5 | [62.5, 100.0] | — | 14/0/2 |
| anthropic/claude-haiku-4.5 | vs Free | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| anthropic/claude-haiku-4.5 | vs Free+Lib | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| anthropic/claude-haiku-4.5 | vs Plan- | final | 16 | +0.0 | [0.0, 0.0] | — | 0/0/16 |
| anthropic/claude-haiku-4.5 | vs Rule | final | 16 | +87.5 | [62.5, 100.0] | — | 14/0/2 |

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
