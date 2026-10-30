# WebApp1K / WebApp1K-Duo 探针结果

生成时间 2026-10-30T11:02:23Z。自由代码基线（无计划编译器），官方 CRA/Jest 评分，每个测试文件单独一次 Jest 进程。

| 模型 | 单功能通过 | 双功能组合通过 | 组合断言通过 | 两个原子单独都过的组合数 | 其中组合仍失败（组合缺口） | 生成失败 |
|---|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-pro-0813 | 14/15 | 9/10 | 38/40 | 9 | 0 | 0 |
| qwen/qwen3-coder | 14/15 | 7/10 | 33/40 | 9 | 2 | 0 |

「组合缺口」= 两个原子功能各自单独实现都通过，但把二者接进同一个模块时失败的任务数。这正是本项目方法针对的现象。

## deepseek/deepseek-v4-pro-0813：逐任务

| 类别 | 组合任务 | 原子 A（单独 / 组合内） | 原子 B（单独 / 组合内） | 组合 4 项断言 | 组合缺口 |
|---|---|---|---|---:|---|
| blogging | addAltTextToImage_postPerformanceReport | addAltTextToImage：过 / 2/2 | postPerformanceReport：败 / 0/2 | 2/4 |  |
| blogging | addCanonicalUrl_addComment | addCanonicalUrl：过 / 2/2 | addComment：过 / 2/2 | 4/4 |  |
| blogging | addCanonicalUrl_assignPostToCategory | addCanonicalUrl：过 / 2/2 | assignPostToCategory：过 / 2/2 | 4/4 |  |
| blogging | addCanonicalUrl_editComment | addCanonicalUrl：过 / 2/2 | editComment：过 / 2/2 | 4/4 |  |
| blogging | addCanonicalUrl_editTag | addCanonicalUrl：过 / 2/2 | editTag：过 / 2/2 | 4/4 |  |
| taskmanagement | addCommentToTask_setTaskDeadline | addCommentToTask：过 / 2/2 | setTaskDeadline：过 / 2/2 | 4/4 |  |
| taskmanagement | approveOrRejectTaskReview_compareTime | approveOrRejectTaskReview：过 / 2/2 | compareTime：过 / 2/2 | 4/4 |  |
| taskmanagement | approveOrRejectTaskReview_projectCustomWorkflows | approveOrRejectTaskReview：过 / 2/2 | projectCustomWorkflows：过 / 2/2 | 4/4 |  |
| taskmanagement | approveOrRejectTaskReview_setTaskPriority | approveOrRejectTaskReview：过 / 2/2 | setTaskPriority：过 / 2/2 | 4/4 |  |
| taskmanagement | assignTaskToProject_assignTaskToUser | assignTaskToProject：过 / 2/2 | assignTaskToUser：过 / 2/2 | 4/4 |  |

## qwen/qwen3-coder：逐任务

| 类别 | 组合任务 | 原子 A（单独 / 组合内） | 原子 B（单独 / 组合内） | 组合 4 项断言 | 组合缺口 |
|---|---|---|---|---:|---|
| blogging | addAltTextToImage_postPerformanceReport | addAltTextToImage：过 / 2/2 | postPerformanceReport：败 / 0/2 | 2/4 |  |
| blogging | addCanonicalUrl_addComment | addCanonicalUrl：过 / 2/2 | addComment：过 / 2/2 | 4/4 |  |
| blogging | addCanonicalUrl_assignPostToCategory | addCanonicalUrl：过 / 2/2 | assignPostToCategory：过 / 2/2 | 4/4 |  |
| blogging | addCanonicalUrl_editComment | addCanonicalUrl：过 / 2/2 | editComment：过 / 0/2 | 2/4 | 是 |
| blogging | addCanonicalUrl_editTag | addCanonicalUrl：过 / 2/2 | editTag：过 / 2/2 | 4/4 |  |
| taskmanagement | addCommentToTask_setTaskDeadline | addCommentToTask：过 / 0/2 | setTaskDeadline：过 / 1/2 | 1/4 | 是 |
| taskmanagement | approveOrRejectTaskReview_compareTime | approveOrRejectTaskReview：过 / 2/2 | compareTime：过 / 2/2 | 4/4 |  |
| taskmanagement | approveOrRejectTaskReview_projectCustomWorkflows | approveOrRejectTaskReview：过 / 2/2 | projectCustomWorkflows：过 / 2/2 | 4/4 |  |
| taskmanagement | approveOrRejectTaskReview_setTaskPriority | approveOrRejectTaskReview：过 / 2/2 | setTaskPriority：过 / 2/2 | 4/4 |  |
| taskmanagement | assignTaskToProject_assignTaskToUser | assignTaskToProject：过 / 2/2 | assignTaskToUser：过 / 2/2 | 4/4 |  |

探针账本（独立于第三轮账本）：已结算 $0.040576，含未结算预留的敞口 $0.072442，未结算请求 2。
