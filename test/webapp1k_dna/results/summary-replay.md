# WebApp1K-Duo：自由代码 vs 冻结原子接线（GUI-DNA）

生成时间 2026-11-01T13:29:24Z。10 个 Duo 任务，官方 CRA/Jest 评分，每任务 4 项断言；三条臂同种子、同反馈协议（公开 Jest 失败回传，最多 2 轮修复）。

| 模型 | 方法 | 首次通过 | 最终通过 | 首次断言 | 最终断言 | 调用次数 | 编译/解析拒绝 | 费用 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-pro-0813 | 自由代码（基线） | 9/10 | **9/10** | 38/40 | 38/40 | 12 | 0 | $0.0000 |
| deepseek/deepseek-v4-pro-0813 | 规则接线（零 API 控制） | 9/10 | **9/10** | 38/40 | 38/40 | 0 | 0 | $0.0000 |
| deepseek/deepseek-v4-pro-0813 | GUI-DNA 计划 + 检查编译 | 9/10 | **9/10** | 38/40 | 38/40 | 12 | 0 | $0.0000 |
| deepseek/deepseek-v4-pro-0813 | 配对（最终） | 仅 DNA 过 0 | 仅自由过 0 | 都过 9 | 都败 1 | | | |
| qwen/qwen3-coder | 自由代码（基线） | 8/10 | **9/10** | 36/40 | 38/40 | 13 | 0 | $0.0000 |
| qwen/qwen3-coder | 规则接线（零 API 控制） | 9/10 | **9/10** | 38/40 | 38/40 | 0 | 0 | $0.0000 |
| qwen/qwen3-coder | GUI-DNA 计划 + 检查编译 | 8/10 | **9/10** | 34/40 | 38/40 | 13 | 1 | $0.0000 |
| qwen/qwen3-coder | 配对（最终） | 仅 DNA 过 0 | 仅自由过 0 | 都过 9 | 都败 1 | | | |

## deepseek/deepseek-v4-pro-0813：逐任务（最终断言 / 4）

| 类别 | 组合任务 | 自由代码（基线） | 规则接线（零 API 控制） | GUI-DNA 计划 + 检查编译 | 原子单测通过的变体 | DNA 计划 |
|---|---|---:|---:|---:|---|---|
| blogging | addAltTextToImage_postPerformanceReport | 2/4 败（首次 2） | 2/4 败 | 2/4 败（首次 2） | addAltTextToImage:v1,v2; postPerformanceReport:无 | addAltTextToImage=v2 postPerformanceReport=v2 |
| blogging | addCanonicalUrl_addComment | 4/4 过 | 4/4 过 | 4/4 过 | addCanonicalUrl:v1,v2; addComment:v1,v2 | addCanonicalUrl=v2 addComment=v1 |
| blogging | addCanonicalUrl_assignPostToCategory | 4/4 过 | 4/4 过 | 4/4 过 | addCanonicalUrl:v1,v2; assignPostToCategory:v1,v2 | addCanonicalUrl=v2 assignPostToCategory=v1 |
| blogging | addCanonicalUrl_editComment | 4/4 过 | 4/4 过 | 4/4 过 | addCanonicalUrl:v1,v2; editComment:v1,v2 | addCanonicalUrl=v1 editComment=v1 |
| blogging | addCanonicalUrl_editTag | 4/4 过 | 4/4 过 | 4/4 过 | addCanonicalUrl:v1,v2; editTag:v1,v2 | addCanonicalUrl=v1 editTag=v1 |
| taskmanagement | addCommentToTask_setTaskDeadline | 4/4 过 | 4/4 过 | 4/4 过 | addCommentToTask:v1,v2; setTaskDeadline:v1,v2 | addCommentToTask=v1 setTaskDeadline=v1 |
| taskmanagement | approveOrRejectTaskReview_compareTime | 4/4 过 | 4/4 过 | 4/4 过 | approveOrRejectTaskReview:v1,v2; compareTime:v1,v2 | approveOrRejectTaskReview=v1 compareTime=v1 |
| taskmanagement | approveOrRejectTaskReview_projectCustomWorkflows | 4/4 过 | 4/4 过 | 4/4 过 | approveOrRejectTaskReview:v1,v2; projectCustomWorkflows:v1,v2 | approveOrRejectTaskReview=v1 projectCustomWorkflows=v1 |
| taskmanagement | approveOrRejectTaskReview_setTaskPriority | 4/4 过 | 4/4 过 | 4/4 过 | approveOrRejectTaskReview:v1,v2; setTaskPriority:v1,v2 | approveOrRejectTaskReview=v1 setTaskPriority=v1 |
| taskmanagement | assignTaskToProject_assignTaskToUser | 4/4 过 | 4/4 过 | 4/4 过 | assignTaskToProject:v1,v2; assignTaskToUser:v1,v2 | assignTaskToProject=v1 assignTaskToUser=v1 |

## qwen/qwen3-coder：逐任务（最终断言 / 4）

| 类别 | 组合任务 | 自由代码（基线） | 规则接线（零 API 控制） | GUI-DNA 计划 + 检查编译 | 原子单测通过的变体 | DNA 计划 |
|---|---|---:|---:|---:|---|---|
| blogging | addAltTextToImage_postPerformanceReport | 2/4 败（首次 2） | 2/4 败 | 2/4 败（首次 2） | addAltTextToImage:v1,v2; postPerformanceReport:无 | addAltTextToImage=v1 postPerformanceReport=v2 |
| blogging | addCanonicalUrl_addComment | 4/4 过 | 4/4 过 | 4/4 过 | addCanonicalUrl:v1,v2; addComment:v1,v2 | addCanonicalUrl=v1 addComment=v1 relabel |
| blogging | addCanonicalUrl_assignPostToCategory | 4/4 过（首次 2） | 4/4 过 | 4/4 过 | addCanonicalUrl:v1,v2; assignPostToCategory:v1,v2 | addCanonicalUrl=v2 assignPostToCategory=v1 |
| blogging | addCanonicalUrl_editComment | 4/4 过 | 4/4 过 | 4/4 过 | addCanonicalUrl:v1,v2; editComment:v1,v2 | addCanonicalUrl=v1 editComment=v1 |
| blogging | addCanonicalUrl_editTag | 4/4 过 | 4/4 过 | 4/4 过 | addCanonicalUrl:v1,v2; editTag:v1,v2 | addCanonicalUrl=v2 editTag=v1 |
| taskmanagement | addCommentToTask_setTaskDeadline | 4/4 过 | 4/4 过 | 4/4 过 | addCommentToTask:v1,v2; setTaskDeadline:v1,v2 | addCommentToTask=v1 setTaskDeadline=v1 |
| taskmanagement | approveOrRejectTaskReview_compareTime | 4/4 过 | 4/4 过 | 4/4 过 | approveOrRejectTaskReview:v1,v2; compareTime:v1,v2 | approveOrRejectTaskReview=v1 compareTime=v1 |
| taskmanagement | approveOrRejectTaskReview_projectCustomWorkflows | 4/4 过 | 4/4 过 | 4/4 过（首次 0） | approveOrRejectTaskReview:v1,v2; projectCustomWorkflows:v1,v2 | approveOrRejectTaskReview=v1 projectCustomWorkflows=v1 |
| taskmanagement | approveOrRejectTaskReview_setTaskPriority | 4/4 过 | 4/4 过 | 4/4 过 | approveOrRejectTaskReview:v1,v2; setTaskPriority:v1,v2 | approveOrRejectTaskReview=v1 setTaskPriority=v1 |
| taskmanagement | assignTaskToProject_assignTaskToUser | 4/4 过 | 4/4 过 | 4/4 过 | assignTaskToProject:v1,v2; assignTaskToUser:v1,v2 | assignTaskToProject=v1 assignTaskToUser=v1 |

账本（独立于第三轮与探针账本）：已结算 $0.000000，敞口 $0.000000，未结算 0。
