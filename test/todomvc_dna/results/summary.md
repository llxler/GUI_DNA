# TodoMVC（官方 Playwright 测试集）：自由代码 vs 冻结原子接线（GUI-DNA）

生成时间 2026-11-02T04:07:29Z。8 个功能族任务 × 2 个样本；隐藏评测 = 官方 Playwright TodoMVC 示例测试集（24 项）中该任务启用功能覆盖的子集；三条臂同种子、同公开反馈（页面错误 + 一次添加的冒烟检查），最多 2 轮修复；隐藏测试从不进入提示词。

| 模型 | 方法 | 任务全过（首次） | 任务全过（最终） | 隐藏测试通过（首次） | 隐藏测试通过（最终） | 调用 | 编译/解析拒绝 | 费用 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-pro-0813 | 自由代码（基线） | 16/16 | **16/16** | 166/166 | **166/166** | 16 | 0 | $0.0547 |
| deepseek/deepseek-v4-pro-0813 | 规则接线（零 API 控制） | 2/16 | **2/16** | 120/166 | **120/166** | 0 | 0 | $0.0000 |
| deepseek/deepseek-v4-pro-0813 | GUI-DNA 计划 + 检查编译 | 16/16 | **16/16** | 166/166 | **166/166** | 16 | 0 | $0.0134 |
| deepseek/deepseek-v4-pro-0813 | 配对（最终，DNA vs 自由） | 仅 DNA 全过 0 | 仅自由全过 0 | 都过 16 | 都败 0 | 测试数差 +0 | | |
| qwen/qwen3-coder-30b-a3b-instruct | 自由代码（基线） | 13/16 | **15/16** | 150/166 | **163/166** | 18 | 0 | $0.0052 |
| qwen/qwen3-coder-30b-a3b-instruct | 规则接线（零 API 控制） | 2/16 | **2/16** | 120/166 | **120/166** | 0 | 0 | $0.0000 |
| qwen/qwen3-coder-30b-a3b-instruct | GUI-DNA 计划 + 检查编译 | 16/16 | **16/16** | 166/166 | **166/166** | 16 | 0 | $0.0064 |
| qwen/qwen3-coder-30b-a3b-instruct | 配对（最终，DNA vs 自由） | 仅 DNA 全过 1 | 仅自由全过 0 | 都过 15 | 都败 0 | 测试数差 +3 | | |
| mistralai/mistral-small-3.2-24b-instruct | 自由代码（基线） | 9/16 | **12/16** | 97/166 | **149/166** | 23 | 0 | $0.0052 |
| mistralai/mistral-small-3.2-24b-instruct | 规则接线（零 API 控制） | 2/16 | **2/16** | 120/166 | **120/166** | 0 | 0 | $0.0000 |
| mistralai/mistral-small-3.2-24b-instruct | GUI-DNA 计划 + 检查编译 | 16/16 | **16/16** | 166/166 | **166/166** | 16 | 0 | $0.0033 |
| mistralai/mistral-small-3.2-24b-instruct | 配对（最终，DNA vs 自由） | 仅 DNA 全过 4 | 仅自由全过 0 | 都过 12 | 都败 0 | 测试数差 +17 | | |
| google/gemma-3-12b-it | 自由代码（基线） | 0/16 | **9/16** | 0/166 | **128/166** | 35 | 0 | $0.0103 |
| google/gemma-3-12b-it | 规则接线（零 API 控制） | 2/16 | **2/16** | 120/166 | **120/166** | 0 | 0 | $0.0000 |
| google/gemma-3-12b-it | GUI-DNA 计划 + 检查编译 | 16/16 | **16/16** | 166/166 | **166/166** | 16 | 0 | $0.0106 |
| google/gemma-3-12b-it | 配对（最终，DNA vs 自由） | 仅 DNA 全过 7 | 仅自由全过 0 | 都过 9 | 都败 0 | 测试数差 +38 | | |

## deepseek/deepseek-v4-pro-0813：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | 规则接线（零 API 控制） | GUI-DNA 计划 + 检查编译 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---:|---|
| todo-01 s0 | counter | 4 → **4** / 4 | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 4 → **4** / 4 | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 5 → **5** / 5 | 4 → **4** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 5 → **5** / 5 | 4 → **4** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 10 → **10** / 10 | 6 → **6** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 10 → **10** / 10 | 6 → **6** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 12 → **12** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 12 → **12** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 16 → **16** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 16 → **16** / 24 | 24 → **24** / 24 |  |

## qwen/qwen3-coder-30b-a3b-instruct：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | 规则接线（零 API 控制） | GUI-DNA 计划 + 检查编译 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---:|---|
| todo-01 s0 | counter | 4 → **4** / 4 | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 4 → **4** / 4 | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 0 → **5** / 5 | 4 → **4** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 5 → **5** / 5 | 4 → **4** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 5 → **5** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 0 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 10 → **10** / 10 | 6 → **6** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 10 → **10** / 10 | 6 → **6** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 12 → **12** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 12 → **12** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 16 → **16** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 24 → **24** / 24 | 16 → **16** / 24 | 24 → **24** / 24 |  |

## mistralai/mistral-small-3.2-24b-instruct：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | 规则接线（零 API 控制） | GUI-DNA 计划 + 检查编译 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---:|---|
| todo-01 s0 | counter | 4 → **4** / 4 | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 4 → **4** / 4 | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 0 → **0** / 5 | 4 → **4** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 5 → **5** / 5 | 4 → **4** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 0 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 0 → **5** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 0 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 8 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 0 → **10** / 10 | 6 → **6** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 10 → **10** / 10 | 6 → **6** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 12 → **12** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 16 → **16** / 16 | 12 → **12** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 0 → **21** / 24 | 16 → **16** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 18 → **18** / 24 | 16 → **16** / 24 | 24 → **24** / 24 |  |

## google/gemma-3-12b-it：逐任务（隐藏测试通过 首次 → 最终 / 总数）

| 任务 | 启用功能 | 自由代码（基线） | 规则接线（零 API 控制） | GUI-DNA 计划 + 检查编译 | 最终仍失败的测试（DNA） |
|---|---|---:|---:|---:|---|
| todo-01 s0 | counter | 0 → **4** / 4 | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-01 s1 | counter | 0 → **4** / 4 | 4 → **4** / 4 | 4 → **4** / 4 |  |
| todo-02 s0 | toggle | 0 → **5** / 5 | 4 → **4** / 5 | 5 → **5** / 5 |  |
| todo-02 s1 | toggle | 0 → **5** / 5 | 4 → **4** / 5 | 5 → **5** / 5 |  |
| todo-03 s0 | edit | 0 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-03 s1 | edit | 0 → **6** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-04 s0 | toggle, toggleAll | 0 → **2** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-04 s1 | toggle, toggleAll | 0 → **5** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-05 s0 | toggle, clearCompleted | 0 → **8** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-05 s1 | toggle, clearCompleted | 0 → **2** / 8 | 6 → **6** / 8 | 8 → **8** / 8 |  |
| todo-06 s0 | toggle, routing | 0 → **8** / 10 | 6 → **6** / 10 | 10 → **10** / 10 |  |
| todo-06 s1 | toggle, routing | 0 → **10** / 10 | 6 → **6** / 10 | 10 → **10** / 10 |  |
| todo-07 s0 | toggle, edit, counter, clearCompleted | 0 → **16** / 16 | 12 → **12** / 16 | 16 → **16** / 16 |  |
| todo-07 s1 | toggle, edit, counter, clearCompleted | 0 → **0** / 16 | 12 → **12** / 16 | 16 → **16** / 16 |  |
| todo-08 s0 | toggle, toggleAll, edit, counter, clearCompleted, routing | 0 → **21** / 24 | 16 → **16** / 24 | 24 → **24** / 24 |  |
| todo-08 s1 | toggle, toggleAll, edit, counter, clearCompleted, routing | 0 → **24** / 24 | 16 → **16** / 24 | 24 → **24** / 24 |  |

账本（独立）：已结算 $0.109084，敞口 $0.118009，未结算 4。
