# TodoMVC（官方 Playwright 测试集）：自由代码 vs 冻结原子接线（GUI-DNA）

生成时间 2026-11-02T02:04:05Z。8 个功能族任务 × 2 个样本；隐藏评测 = 官方 Playwright TodoMVC 示例测试集（24 项）中该任务启用功能覆盖的子集；三条臂同种子、同公开反馈（页面错误 + 一次添加的冒烟检查），最多 2 轮修复；隐藏测试从不进入提示词。

| 模型 | 方法 | 任务全过（首次） | 任务全过（最终） | 隐藏测试通过（首次） | 隐藏测试通过（最终） | 调用 | 编译/解析拒绝 | 费用 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-pro-0813 | 自由代码（基线） | 16/16 | **16/16** | 166/166 | **166/166** | 16 | 0 | $0.0547 |
| deepseek/deepseek-v4-pro-0813 | 规则接线（零 API 控制） | 2/16 | **2/16** | 120/166 | **120/166** | 0 | 0 | $0.0000 |
| deepseek/deepseek-v4-pro-0813 | GUI-DNA 计划 + 检查编译 | 16/16 | **16/16** | 166/166 | **166/166** | 22 | 6 | $0.0134 |
| deepseek/deepseek-v4-pro-0813 | 配对（最终，DNA vs 自由） | 仅 DNA 全过 0 | 仅自由全过 0 | 都过 16 | 都败 0 | 测试数差 +0 | | |
| qwen/qwen3-coder-30b-a3b-instruct | 自由代码（基线） | 13/16 | **15/16** | 150/166 | **163/166** | 18 | 0 | $0.0052 |
| qwen/qwen3-coder-30b-a3b-instruct | 规则接线（零 API 控制） | 2/16 | **2/16** | 120/166 | **120/166** | 0 | 0 | $0.0000 |
| qwen/qwen3-coder-30b-a3b-instruct | GUI-DNA 计划 + 检查编译 | 16/16 | **16/16** | 166/166 | **166/166** | 32 | 16 | $0.0064 |
| qwen/qwen3-coder-30b-a3b-instruct | 配对（最终，DNA vs 自由） | 仅 DNA 全过 1 | 仅自由全过 0 | 都过 15 | 都败 0 | 测试数差 +3 | | |

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

账本（独立）：已结算 $0.079695，敞口 $0.079695，未结算 0。
