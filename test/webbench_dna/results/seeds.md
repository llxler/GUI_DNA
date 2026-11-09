# Web-Bench dom1 多种子（任务通过 / 20，最终版本）

零 API，`uv run python -m test.webbench_dna.seeds`。种子 [20261102, 20261109, 20261110]（GPT-5-mini 不接受种子参数，每个阶段是一次独立采样）。第一个种子来自 `test/webbench_dna/results/summary.json`，其余来自 `artifacts/webbench-dna-seed*/summary.json`；空格 = 该种子没跑这一做法。

| 模型 | 做法 | 种子 20261102 | 种子 20261109 | 种子 20261110 | 均值 |
|---|---|---:|---:|---:|---:|
| Qwen3-Coder-30B | Free | 5 | 6 | 7 | 6.0 |
| Qwen3-Coder-30B | Free+Lib | 11 |  |  | 11.0 |
| Qwen3-Coder-30B | GUI-DNA | 17 | 17 | 17 | 17.0 |
| Mistral-Small-3.2 | Free | 5 | 6 | 5 | 5.3 |
| Mistral-Small-3.2 | Free+Lib | 5 |  |  | 5.0 |
| Mistral-Small-3.2 | GUI-DNA | 18 | 16 | 18 | 17.3 |
| Gemma-3-12B | Free | 2 |  |  | 2.0 |
| Gemma-3-12B | Free+Lib | 0 |  |  | 0.0 |
| Gemma-3-12B | GUI-DNA | 6 |  |  | 6.0 |
| DeepSeek-V4-Flash | Free | 12 | 6 | 9 | 9.0 |
| DeepSeek-V4-Flash | Free+Lib | 15 |  |  | 15.0 |
| DeepSeek-V4-Flash | GUI-DNA | 18 | 17 | 18 | 17.7 |
| GPT-OSS-120B | Free | 7 |  |  | 7.0 |
| GPT-OSS-120B | Free+Lib | 18 | 14 | 15 | 15.7 |
| GPT-OSS-120B | GUI-DNA | 17 | 17 | 17 | 17.0 |
| Gemini-2.5-Flash | Free | 11 |  |  | 11.0 |
| Gemini-2.5-Flash | Free+Lib | 18 | 17 | 20 | 18.3 |
| Gemini-2.5-Flash | GUI-DNA | 20 | 20 | 20 | 20.0 |
| GPT-5-mini | Free | 6 |  |  | 6.0 |
| GPT-5-mini | Free+Lib | 15 | 9 | 17 | 13.7 |
| GPT-5-mini | GUI-DNA | 18 | 18 | 18 | 18.0 |
| Claude-Haiku-4.5 | Free | 6 |  |  | 6.0 |
| Claude-Haiku-4.5 | Free+Lib | 17 | 8 | 16 | 13.7 |
| Claude-Haiku-4.5 | GUI-DNA | 18 | 18 | 18 | 18.0 |

## 配对差（GUI-DNA − 基线，百分点；按任务聚类 bootstrap）

| 对比 | 模型数 | n 对 | 差值 | 95% 区间 | 胜/负/平 | 逐种子差值 |
|---|---:|---:|---:|---:|---:|---|
| vs Free | 8 | 280 | +50.7 | [36.8, 64.3] | 143/1/136 | 20261102: +48.8 (79/1/80); 20261109: +53.3 (32/0/28); 20261110: +53.3 (32/0/28) |
| vs Free+Lib | 8 | 320 | +19.7 | [13.8, 26.6] | 67/4/249 | 20261102: +20.6 (35/2/123); 20261109: +31.2 (25/0/55); 20261110: +6.2 (7/2/71) |
