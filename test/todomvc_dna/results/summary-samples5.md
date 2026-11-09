# TodoMVC（官方 Playwright 测试集）：自由代码 vs 冻结原子函数组装（GUI-DNA）

生成时间 2026-11-09T12:17:39Z。8 个功能族任务 × 5 个样本；隐藏评测 = 官方 Playwright TodoMVC 示例测试集（24 项）中该任务启用功能覆盖的子集；三种做法同种子、同公开反馈（页面错误 + 一次添加的冒烟检查），最多 2 轮修复；隐藏测试从不进入提示词。

| 模型 | 方法 | 任务全过（首次） | 任务全过（最终） | 隐藏测试通过（首次） | 隐藏测试通过（最终） | 调用 | 编译/解析拒绝 | 费用 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-pro-0813 | 自由代码（基线） | 40/40 | **40/40** | 415/415 | **415/415** | 40 | 0 | $0.1323 |
| deepseek/deepseek-v4-pro-0813 | GUI-DNA 组装方案 + 编译检查 | 40/40 | **40/40** | 415/415 | **415/415** | 40 | 0 | $0.0483 |
| deepseek/deepseek-v4-pro-0813 | 配对（最终，DNA vs 自由） | 仅 DNA 全过 0 | 仅自由全过 0 | 都过 40 | 都败 0 | 测试数差 +0 | | |
| qwen/qwen3-coder-30b-a3b-instruct | 自由代码（基线） | 35/40 | **39/40** | 383/415 | **412/415** | 44 | 0 | $0.0125 |
| qwen/qwen3-coder-30b-a3b-instruct | GUI-DNA 组装方案 + 编译检查 | 40/40 | **40/40** | 415/415 | **415/415** | 40 | 0 | $0.0111 |
| qwen/qwen3-coder-30b-a3b-instruct | 配对（最终，DNA vs 自由） | 仅 DNA 全过 1 | 仅自由全过 0 | 都过 39 | 都败 0 | 测试数差 +3 | | |
| mistralai/mistral-small-3.2-24b-instruct | 自由代码（基线） | 27/40 | **32/40** | 318/415 | **390/415** | 51 | 0 | $0.0114 |
| mistralai/mistral-small-3.2-24b-instruct | GUI-DNA 组装方案 + 编译检查 | 40/40 | **40/40** | 415/415 | **415/415** | 40 | 0 | $0.0083 |
| mistralai/mistral-small-3.2-24b-instruct | 配对（最终，DNA vs 自由） | 仅 DNA 全过 8 | 仅自由全过 0 | 都过 32 | 都败 0 | 测试数差 +25 | | |
| google/gemma-3-12b-it | 自由代码（基线） | 0/35 | **17/35** | 0/359 | **227/359** | 85 | 1 | $0.0288 |
| google/gemma-3-12b-it | GUI-DNA 组装方案 + 编译检查 | 37/37 | **37/37** | 359/359 | **359/359** | 38 | 1 | $0.0149 |
| google/gemma-3-12b-it | 配对（最终，DNA vs 自由） | 仅 DNA 全过 17 | 仅自由全过 0 | 都过 17 | 都败 0 | 测试数差 +108 | | |
| openai/gpt-5-mini | 自由代码（基线） | 39/40 | **40/40** | 414/415 | **415/415** | 41 | 0 | $0.1383 |
| openai/gpt-5-mini | GUI-DNA 组装方案 + 编译检查 | 40/40 | **40/40** | 415/415 | **415/415** | 40 | 0 | $0.0692 |
| openai/gpt-5-mini | 配对（最终，DNA vs 自由） | 仅 DNA 全过 0 | 仅自由全过 0 | 都过 40 | 都败 0 | 测试数差 +0 | | |
| openai/gpt-oss-120b | 自由代码（基线） | 40/40 | **40/40** | 415/415 | **415/415** | 40 | 0 | $0.0139 |
| openai/gpt-oss-120b | GUI-DNA 组装方案 + 编译检查 | 40/40 | **40/40** | 415/415 | **415/415** | 40 | 0 | $0.0102 |
| openai/gpt-oss-120b | 配对（最终，DNA vs 自由） | 仅 DNA 全过 0 | 仅自由全过 0 | 都过 40 | 都败 0 | 测试数差 +0 | | |
| google/gemini-2.5-flash | 自由代码（基线） | 40/40 | **40/40** | 415/415 | **415/415** | 40 | 0 | $0.0927 |
| google/gemini-2.5-flash | GUI-DNA 组装方案 + 编译检查 | 40/40 | **40/40** | 415/415 | **415/415** | 40 | 0 | $0.0306 |
| google/gemini-2.5-flash | 配对（最终，DNA vs 自由） | 仅 DNA 全过 0 | 仅自由全过 0 | 都过 40 | 都败 0 | 测试数差 +0 | | |
| anthropic/claude-haiku-4.5 | 自由代码（基线） | 40/40 | **40/40** | 415/415 | **415/415** | 40 | 0 | $0.2425 |
| anthropic/claude-haiku-4.5 | GUI-DNA 组装方案 + 编译检查 | 40/40 | **40/40** | 415/415 | **415/415** | 63 | 23 | $0.2711 |
| anthropic/claude-haiku-4.5 | 配对（最终，DNA vs 自由） | 仅 DNA 全过 0 | 仅自由全过 0 | 都过 40 | 都败 0 | 测试数差 +0 | | |

## deepseek/deepseek-v4-pro-0813：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | GUI-DNA 组装方案 + 编译检查 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---|
| todo-01 s0 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s2 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s3 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s4 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s2 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s3 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s4 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s2 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s3 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s4 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s2 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s3 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s4 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s2 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s3 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s4 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s2 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s3 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s4 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s2 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s3 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s4 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s2 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s3 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s4 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |

## qwen/qwen3-coder-30b-a3b-instruct：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | GUI-DNA 组装方案 + 编译检查 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---|
| todo-01 s0 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s2 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s3 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s4 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 0 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s2 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s3 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s4 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s2 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s3 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s4 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 5 → **5** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s2 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s3 | toggle, toggleAll | 0 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s4 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 0 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s2 | toggle, clearCompleted | 0 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s3 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s4 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s2 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s3 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s4 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s2 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s3 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s4 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s2 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s3 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s4 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |

## mistralai/mistral-small-3.2-24b-instruct：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | GUI-DNA 组装方案 + 编译检查 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---|
| todo-01 s0 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s2 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s3 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s4 | counter | 0 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 0 → **0** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s2 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s3 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s4 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 0 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s2 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s3 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s4 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 0 → **5** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s2 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s3 | toggle, toggleAll | 5 → **5** / 8 | 8 → **8** / 8 |  |
| todo-04 s4 | toggle, toggleAll | 5 → **5** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 0 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s2 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s3 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s4 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 0 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s2 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s3 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s4 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s2 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s3 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s4 | toggle, edit, counter, clearCompleted | 0 → **16** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 0 → **21** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 18 → **18** / 24 | 24 → **24** / 24 |  |
| todo-08 s2 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s3 | toggle, toggleAll, edit, counter, clearCompleted, routing | 23 → **23** / 24 | 24 → **24** / 24 |  |
| todo-08 s4 | toggle, toggleAll, edit, counter, clearCompleted, routing | 23 → **23** / 24 | 24 → **24** / 24 |  |

## google/gemma-3-12b-it：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | GUI-DNA 组装方案 + 编译检查 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---|
| todo-01 s0 | counter | 0 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 0 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s2 | counter | 0 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s3 | counter | 0 → **0** / 4 | 4 → **4** / 4 |  |
| todo-01 s4 | counter | 0 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 0 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 0 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s2 | toggle | 0 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s3 | toggle | 0 → **0** / 5 | 5 → **5** / 5 |  |
| todo-02 s4 | toggle | 0 → **5** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 0 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 0 → **6** / 8 | 8 → **8** / 8 |  |
| todo-03 s2 | edit | 0 → **0** / 8 | 8 → **8** / 8 |  |
| todo-03 s3 | edit | 0 → **0** / 8 | 8 → **8** / 8 |  |
| todo-03 s4 | edit | 0 → **0** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 0 → **2** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 0 → **5** / 8 | 8 → **8** / 8 |  |
| todo-04 s2 | toggle, toggleAll | — | 8 → **8** / 8 |  |
| todo-04 s3 | toggle, toggleAll | — | 8 → **8** / 8 |  |
| todo-04 s4 | toggle, toggleAll | — | — |  |
| todo-05 s0 | toggle, clearCompleted | 0 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 0 → **2** / 8 | 8 → **8** / 8 |  |
| todo-05 s2 | toggle, clearCompleted | — | 8 → **8** / 8 |  |
| todo-05 s3 | toggle, clearCompleted | 0 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s4 | toggle, clearCompleted | 0 → **8** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 0 → **8** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 0 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s2 | toggle, routing | 0 → **9** / 10 | 10 → **10** / 10 |  |
| todo-06 s3 | toggle, routing | 0 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s4 | toggle, routing | 0 → **10** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 0 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 0 → **0** / 16 | 16 → **16** / 16 |  |
| todo-07 s2 | toggle, edit, counter, clearCompleted | 0 → **0** / 16 | 16 → **16** / 16 |  |
| todo-07 s3 | toggle, edit, counter, clearCompleted | 0 → **0** / 16 | 16 → **16** / 16 |  |
| todo-07 s4 | toggle, edit, counter, clearCompleted | 0 → **15** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 0 → **21** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 0 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s2 | toggle, toggleAll, edit, counter, clearCompleted, routing | 0 → **0** / 24 | — |  |
| todo-08 s3 | toggle, toggleAll, edit, counter, clearCompleted, routing | 0 → **21** / 24 | 24 → **24** / 24 |  |
| todo-08 s4 | toggle, toggleAll, edit, counter, clearCompleted, routing | — | — |  |

## openai/gpt-5-mini：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | GUI-DNA 组装方案 + 编译检查 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---|
| todo-01 s0 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s2 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s3 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s4 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s2 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s3 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s4 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s2 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s3 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s4 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s2 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s3 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s4 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s2 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s3 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s4 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s2 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s3 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s4 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s2 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s3 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s4 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 23 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s2 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s3 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s4 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |

## openai/gpt-oss-120b：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | GUI-DNA 组装方案 + 编译检查 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---|
| todo-01 s0 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s2 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s3 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s4 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s2 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s3 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s4 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s2 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s3 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s4 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s2 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s3 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s4 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s2 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s3 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s4 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s2 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s3 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s4 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s2 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s3 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s4 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s2 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s3 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s4 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |

## google/gemini-2.5-flash：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | GUI-DNA 组装方案 + 编译检查 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---|
| todo-01 s0 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s2 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s3 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s4 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s2 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s3 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s4 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s2 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s3 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s4 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s2 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s3 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s4 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s2 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s3 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s4 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s2 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s3 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s4 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s2 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s3 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s4 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s2 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s3 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s4 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |

## anthropic/claude-haiku-4.5：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | GUI-DNA 组装方案 + 编译检查 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---|
| todo-01 s0 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s2 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s3 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s4 | counter | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s2 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s3 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-02 s4 | toggle | 5 → **5** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s2 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s3 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-03 s4 | edit | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s2 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s3 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-04 s4 | toggle, toggleAll | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s2 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s3 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-05 s4 | toggle, clearCompleted | 8 → **8** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s2 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s3 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-06 s4 | toggle, routing | 10 → **10** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s2 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s3 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-07 s4 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s2 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s3 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |
| todo-08 s4 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 24 → **24** / 24 |  |

账本（独立）：已结算 $0.674097，敞口 $0.942150，未结算 122。
