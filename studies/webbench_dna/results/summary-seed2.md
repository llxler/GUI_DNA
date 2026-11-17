# Web-Bench dom1（官方 Playwright 测试）：自由增量代码 vs 冻结原子函数组装（GUI-DNA）

生成时间 2026-11-09T09:23:03Z。20 个顺序任务，隐藏评测 = 官方 `task-k.spec.js`（共 85 项断言测试）；自由代码按基准协议从官方初始页面逐任务增量修改，GUI-DNA 每个任务独立写组装方案；两者同种子、同公开反馈（页面/控制台错误、工具按钮可点击），最多 2 轮修复。「顺序分」= 基准口径：按任务顺序累计通过数，连续两次失败即停止。

| 模型 | 方法 | 任务通过（首次） | 任务通过（最终） | 顺序分（最终） | 测试通过（最终） | 调用 | 编译/解析拒绝 | 费用 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| qwen/qwen3-coder-30b-a3b-instruct | 自由增量代码（基准协议） | 7/20 | **7/20** | 3/20 | 32/81 | 24 | 0 | $0.0451 |
| qwen/qwen3-coder-30b-a3b-instruct | 自由增量代码 + 同一函数库（对照） | 0/0 | **0/0** | 0/0 | 0/0 | 0 | 0 | $0.0000 |
| qwen/qwen3-coder-30b-a3b-instruct | GUI-DNA 组装方案 + 编译检查 | 17/20 | **17/20** | 7/20 | 78/81 | 20 | 0 | $0.0053 |
| qwen/qwen3-coder-30b-a3b-instruct | 配对（最终，DNA vs 自由） | 仅 DNA 过 10 | 仅自由过 0 | 都过 7 | 都败 3 | | | |
| mistralai/mistral-small-3.2-24b-instruct | 自由增量代码（基准协议） | 5/20 | **5/20** | 3/20 | 26/81 | 30 | 0 | $0.0477 |
| mistralai/mistral-small-3.2-24b-instruct | 自由增量代码 + 同一函数库（对照） | 0/0 | **0/0** | 0/0 | 0/0 | 0 | 0 | $0.0000 |
| mistralai/mistral-small-3.2-24b-instruct | GUI-DNA 组装方案 + 编译检查 | 18/20 | **18/20** | 7/20 | 78/81 | 32 | 12 | $0.0086 |
| mistralai/mistral-small-3.2-24b-instruct | 配对（最终，DNA vs 自由） | 仅 DNA 过 13 | 仅自由过 0 | 都过 5 | 都败 2 | | | |
| deepseek/deepseek-v4-flash | 自由增量代码（基准协议） | 9/20 | **9/20** | 3/20 | 54/81 | 24 | 0 | $0.0383 |
| deepseek/deepseek-v4-flash | 自由增量代码 + 同一函数库（对照） | 0/0 | **0/0** | 0/0 | 0/0 | 0 | 0 | $0.0000 |
| deepseek/deepseek-v4-flash | GUI-DNA 组装方案 + 编译检查 | 18/20 | **18/20** | 18/20 | 79/81 | 24 | 4 | $0.0063 |
| deepseek/deepseek-v4-flash | 配对（最终，DNA vs 自由） | 仅 DNA 过 9 | 仅自由过 0 | 都过 9 | 都败 2 | | | |
| google/gemini-2.5-flash | 自由增量代码（基准协议） | 0/0 | **0/0** | 0/0 | 0/0 | 0 | 0 | $0.0000 |
| google/gemini-2.5-flash | 自由增量代码 + 同一函数库（对照） | 20/20 | **20/20** | 20/20 | 81/81 | 26 | 6 | $0.3419 |
| google/gemini-2.5-flash | GUI-DNA 组装方案 + 编译检查 | 20/20 | **20/20** | 20/20 | 81/81 | 23 | 3 | $0.0188 |
| google/gemini-2.5-flash | 配对（最终，DNA vs 自由） | 仅 DNA 过 0 | 仅自由过 0 | 都过 0 | 都败 0 | | | |
| anthropic/claude-haiku-4.5 | 自由增量代码（基准协议） | 0/0 | **0/0** | 0/0 | 0/0 | 0 | 0 | $0.0000 |
| anthropic/claude-haiku-4.5 | 自由增量代码 + 同一函数库（对照） | 15/20 | **16/20** | 7/20 | 73/81 | 22 | 1 | $0.8995 |
| anthropic/claude-haiku-4.5 | GUI-DNA 组装方案 + 编译检查 | 18/20 | **18/20** | 18/20 | 79/81 | 23 | 3 | $0.0970 |
| anthropic/claude-haiku-4.5 | 配对（最终，DNA vs 自由） | 仅 DNA 过 0 | 仅自由过 0 | 都过 0 | 都败 0 | | | |
| openai/gpt-5-mini | 自由增量代码（基准协议） | 0/0 | **0/0** | 0/0 | 0/0 | 0 | 0 | $0.0000 |
| openai/gpt-5-mini | 自由增量代码 + 同一函数库（对照） | 16/20 | **17/20** | 17/20 | 74/81 | 22 | 0 | $0.4141 |
| openai/gpt-5-mini | GUI-DNA 组装方案 + 编译检查 | 18/20 | **18/20** | 7/20 | 79/81 | 20 | 0 | $0.0399 |
| openai/gpt-5-mini | 配对（最终，DNA vs 自由） | 仅 DNA 过 0 | 仅自由过 0 | 都过 0 | 都败 0 | | | |
| openai/gpt-oss-120b | 自由增量代码（基准协议） | 0/0 | **0/0** | 0/0 | 0/0 | 0 | 0 | $0.0000 |
| openai/gpt-oss-120b | 自由增量代码 + 同一函数库（对照） | 15/20 | **15/20** | 7/20 | 67/81 | 20 | 0 | $0.0167 |
| openai/gpt-oss-120b | GUI-DNA 组装方案 + 编译检查 | 17/20 | **17/20** | 7/20 | 78/81 | 21 | 1 | $0.0024 |
| openai/gpt-oss-120b | 配对（最终，DNA vs 自由） | 仅 DNA 过 0 | 仅自由过 0 | 都过 0 | 都败 0 | | | |

## qwen/qwen3-coder-30b-a3b-instruct：逐任务（测试通过 首次 → 最终 / 总数）

| 任务 | 难度 | 自由增量代码（基准协议） | 自由增量代码 + 同一函数库（对照） | GUI-DNA 组装方案 + 编译检查 | DNA 最终仍失败的测试 |
|---|---|---:|---:|---:|---|
| task-1 | easy | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-2 | easy | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-3 | easy | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-4 | easy | 2 → **2** / 7 | — | 7 → **7** / 7 |  |
| task-5 | moderate | 3 → **3** / 5 | — | 5 → **5** / 5 |  |
| task-6 | moderate | 0 → **0** / 5 | — | 5 → **5** / 5 |  |
| task-7 | moderate | 0 → **0** / 6 | — | 6 → **6** / 6 |  |
| task-8 | moderate | 1 → **1** / 3 | — | 2 → **2** / 3 | menu item no entries/delete |
| task-9 | moderate | 0 → **0** / 4 | — | 3 → **3** / 4 | menu item entries/paste |
| task-10 | challenging | 1 → **1** / 4 | — | 3 → **3** / 4 | menu item no entries/rename |
| task-11 | challenging | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-12 | challenging | 2 → **2** / 4 | — | 4 → **4** / 4 |  |
| task-13 | challenging | 0 → **0** / 2 | — | 2 → **2** / 2 |  |
| task-14 | challenging | 0 → **0** / 5 | — | 5 → **5** / 5 |  |
| task-15 | challenging | 0 → **0** / 4 | — | 4 → **4** / 4 |  |
| task-16 | challenging | 2 → **2** / 2 | — | 2 → **2** / 2 |  |
| task-17 | challenging | 3 → **3** / 3 | — | 3 → **3** / 3 |  |
| task-18 | challenging | 2 → **2** / 2 | — | 2 → **2** / 2 |  |
| task-19 | challenging | 0 → **0** / 5 | — | 5 → **5** / 5 |  |
| task-20 | moderate | 0 → **0** / 4 | — | 4 → **4** / 4 |  |

## mistralai/mistral-small-3.2-24b-instruct：逐任务（测试通过 首次 → 最终 / 总数）

| 任务 | 难度 | 自由增量代码（基准协议） | 自由增量代码 + 同一函数库（对照） | GUI-DNA 组装方案 + 编译检查 | DNA 最终仍失败的测试 |
|---|---|---:|---:|---:|---|
| task-1 | easy | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-2 | easy | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-3 | easy | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-4 | easy | 0 → **0** / 7 | — | 7 → **7** / 7 |  |
| task-5 | moderate | 1 → **1** / 5 | — | 5 → **5** / 5 |  |
| task-6 | moderate | 0 → **0** / 5 | — | 5 → **5** / 5 |  |
| task-7 | moderate | 0 → **0** / 6 | — | 6 → **6** / 6 |  |
| task-8 | moderate | 1 → **1** / 3 | — | 2 → **2** / 3 | menu item no entries/delete |
| task-9 | moderate | 0 → **0** / 4 | — | 2 → **2** / 4 | menu item entries/paste; menu item pasted dir open/close |
| task-10 | challenging | 2 → **2** / 4 | — | 4 → **4** / 4 |  |
| task-11 | challenging | 2 → **2** / 4 | — | 4 → **4** / 4 |  |
| task-12 | challenging | 2 → **2** / 4 | — | 4 → **4** / 4 |  |
| task-13 | challenging | 0 → **0** / 2 | — | 2 → **2** / 2 |  |
| task-14 | challenging | 0 → **0** / 5 | — | 5 → **5** / 5 |  |
| task-15 | challenging | 0 → **0** / 4 | — | 4 → **4** / 4 |  |
| task-16 | challenging | 2 → **2** / 2 | — | 2 → **2** / 2 |  |
| task-17 | challenging | 2 → **2** / 3 | — | 3 → **3** / 3 |  |
| task-18 | challenging | 2 → **2** / 2 | — | 2 → **2** / 2 |  |
| task-19 | challenging | 0 → **0** / 5 | — | 5 → **5** / 5 |  |
| task-20 | moderate | 0 → **0** / 4 | — | 4 → **4** / 4 |  |

## deepseek/deepseek-v4-flash：逐任务（测试通过 首次 → 最终 / 总数）

| 任务 | 难度 | 自由增量代码（基准协议） | 自由增量代码 + 同一函数库（对照） | GUI-DNA 组装方案 + 编译检查 | DNA 最终仍失败的测试 |
|---|---|---:|---:|---:|---|
| task-1 | easy | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-2 | easy | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-3 | easy | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-4 | easy | 5 → **5** / 7 | — | 7 → **7** / 7 |  |
| task-5 | moderate | 4 → **4** / 5 | — | 5 → **5** / 5 |  |
| task-6 | moderate | 0 → **0** / 5 | — | 5 → **5** / 5 |  |
| task-7 | moderate | 6 → **6** / 6 | — | 6 → **6** / 6 |  |
| task-8 | moderate | 1 → **1** / 3 | — | 3 → **3** / 3 |  |
| task-9 | moderate | 1 → **1** / 4 | — | 3 → **3** / 4 | menu item entries/paste |
| task-10 | challenging | 3 → **3** / 4 | — | 4 → **4** / 4 |  |
| task-11 | challenging | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-12 | challenging | 2 → **2** / 4 | — | 4 → **4** / 4 |  |
| task-13 | challenging | 2 → **2** / 2 | — | 2 → **2** / 2 |  |
| task-14 | challenging | 5 → **5** / 5 | — | 5 → **5** / 5 |  |
| task-15 | challenging | 4 → **4** / 4 | — | 4 → **4** / 4 |  |
| task-16 | challenging | 1 → **1** / 2 | — | 2 → **2** / 2 |  |
| task-17 | challenging | 2 → **2** / 3 | — | 3 → **3** / 3 |  |
| task-18 | challenging | 2 → **2** / 2 | — | 2 → **2** / 2 |  |
| task-19 | challenging | 0 → **0** / 5 | — | 5 → **5** / 5 |  |
| task-20 | moderate | 0 → **0** / 4 | — | 3 → **3** / 4 | menu item entries/paste |

## google/gemini-2.5-flash：逐任务（测试通过 首次 → 最终 / 总数）

| 任务 | 难度 | 自由增量代码（基准协议） | 自由增量代码 + 同一函数库（对照） | GUI-DNA 组装方案 + 编译检查 | DNA 最终仍失败的测试 |
|---|---|---:|---:|---:|---|
| task-1 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-2 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-3 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-4 | easy | — | 7 → **7** / 7 | 7 → **7** / 7 |  |
| task-5 | moderate | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-6 | moderate | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-7 | moderate | — | 6 → **6** / 6 | 6 → **6** / 6 |  |
| task-8 | moderate | — | 3 → **3** / 3 | 3 → **3** / 3 |  |
| task-9 | moderate | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-10 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-11 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-12 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-13 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-14 | challenging | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-15 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-16 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-17 | challenging | — | 3 → **3** / 3 | 3 → **3** / 3 |  |
| task-18 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-19 | challenging | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-20 | moderate | — | 4 → **4** / 4 | 4 → **4** / 4 |  |

## anthropic/claude-haiku-4.5：逐任务（测试通过 首次 → 最终 / 总数）

| 任务 | 难度 | 自由增量代码（基准协议） | 自由增量代码 + 同一函数库（对照） | GUI-DNA 组装方案 + 编译检查 | DNA 最终仍失败的测试 |
|---|---|---:|---:|---:|---|
| task-1 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-2 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-3 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-4 | easy | — | 7 → **7** / 7 | 6 → **6** / 7 | add entry when SelectedEntry is dir and closed |
| task-5 | moderate | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-6 | moderate | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-7 | moderate | — | 6 → **6** / 6 | 6 → **6** / 6 |  |
| task-8 | moderate | — | 1 → **1** / 3 | 3 → **3** / 3 |  |
| task-9 | moderate | — | 1 → **1** / 4 | 3 → **3** / 4 | menu item pasted dir open/close |
| task-10 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-11 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-12 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-13 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-14 | challenging | — | 4 → **4** / 5 | 5 → **5** / 5 |  |
| task-15 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-16 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-17 | challenging | — | 3 → **3** / 3 | 3 → **3** / 3 |  |
| task-18 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-19 | challenging | — | 0 → **5** / 5 | 5 → **5** / 5 |  |
| task-20 | moderate | — | 2 → **2** / 4 | 4 → **4** / 4 |  |

## openai/gpt-5-mini：逐任务（测试通过 首次 → 最终 / 总数）

| 任务 | 难度 | 自由增量代码（基准协议） | 自由增量代码 + 同一函数库（对照） | GUI-DNA 组装方案 + 编译检查 | DNA 最终仍失败的测试 |
|---|---|---:|---:|---:|---|
| task-1 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-2 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-3 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-4 | easy | — | 6 → **6** / 7 | 7 → **7** / 7 |  |
| task-5 | moderate | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-6 | moderate | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-7 | moderate | — | 6 → **6** / 6 | 6 → **6** / 6 |  |
| task-8 | moderate | — | 3 → **3** / 3 | 2 → **2** / 3 | menu item no entries/delete |
| task-9 | moderate | — | 2 → **2** / 4 | 3 → **3** / 4 | menu item entries/paste |
| task-10 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-11 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-12 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-13 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-14 | challenging | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-15 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-16 | challenging | — | 0 → **2** / 2 | 2 → **2** / 2 |  |
| task-17 | challenging | — | 3 → **3** / 3 | 3 → **3** / 3 |  |
| task-18 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-19 | challenging | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-20 | moderate | — | 0 → **0** / 4 | 4 → **4** / 4 |  |

## openai/gpt-oss-120b：逐任务（测试通过 首次 → 最终 / 总数）

| 任务 | 难度 | 自由增量代码（基准协议） | 自由增量代码 + 同一函数库（对照） | GUI-DNA 组装方案 + 编译检查 | DNA 最终仍失败的测试 |
|---|---|---:|---:|---:|---|
| task-1 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-2 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-3 | easy | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-4 | easy | — | 7 → **7** / 7 | 7 → **7** / 7 |  |
| task-5 | moderate | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-6 | moderate | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-7 | moderate | — | 6 → **6** / 6 | 6 → **6** / 6 |  |
| task-8 | moderate | — | 2 → **2** / 3 | 2 → **2** / 3 | menu item no entries/delete |
| task-9 | moderate | — | 1 → **1** / 4 | 3 → **3** / 4 | menu item entries/paste |
| task-10 | challenging | — | 2 → **2** / 4 | 4 → **4** / 4 |  |
| task-11 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-12 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-13 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-14 | challenging | — | 1 → **1** / 5 | 5 → **5** / 5 |  |
| task-15 | challenging | — | 4 → **4** / 4 | 4 → **4** / 4 |  |
| task-16 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-17 | challenging | — | 3 → **3** / 3 | 3 → **3** / 3 |  |
| task-18 | challenging | — | 2 → **2** / 2 | 2 → **2** / 2 |  |
| task-19 | challenging | — | 5 → **5** / 5 | 5 → **5** / 5 |  |
| task-20 | moderate | — | 0 → **0** / 4 | 3 → **3** / 4 | menu item entries/paste |

账本（独立）：已结算 $1.984236，敞口 $2.155841，未结算 18。
