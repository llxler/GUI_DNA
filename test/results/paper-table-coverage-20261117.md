# 论文逐表复验范围

这是来源对应表，不是所有LaTeX单元格均已验证的证明。`recomputed_sources`只表示相关来源在现有独立入口中重算；`partial`保留未覆盖列；`not_recomputed`明确列出缺口。全文及附录表格均登记，未编号表以源文件顺序标识。

| 表格 | 来源复算范围 | 入口 | 尚未覆盖 |
|---|---|---|---|
| tab:main | partial | test.replay_primary_tables, test.review_metrics | 部分来源、配对子列或辅助口径尚未全部覆盖，具体范围见同名JSON及重算输出。 |
| tab:interface-main | recomputed_sources | test.replay_new_tables | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:history-main | recomputed_sources | test.replay_nov15 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:todomvc-tests | specification | 无独立入口 | 规范/来源描述，仍需人工逐项核对，不适用准确率复算。 |
| tab:intervals | recomputed_sources | test.paired_intervals, test.review_metrics | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:relax | recomputed_sources | test.replay_nov15, test.replay_review_tables | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。另需历史CRA/Jest运行环境；当前Chromium复验不能代替它。 |
| tab:models | partial | test.replay_primary_tables, test.review_metrics | 部分来源、配对子列或辅助口径尚未全部覆盖，具体范围见同名JSON及重算输出。 |
| tab:todomvc-full | partial | test.replay_primary_tables, test.review_metrics | 部分来源、配对子列或辅助口径尚未全部覆盖，具体范围见同名JSON及重算输出。 |
| tab:webbench-full | recomputed_sources | test.replay_primary_tables, test.replay_table_details, test.replay_nov15 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:repair | recomputed_sources | test.repair_breakdown, test.replay_primary_tables, test.replay_scale_table | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:samples | partial | test.replay_primary_tables, test.review_metrics | 部分来源、配对子列或辅助口径尚未全部覆盖，具体范围见同名JSON及重算输出。 |
| tab:seeds | partial | test.replay_primary_tables, test.review_metrics | 部分来源、配对子列或辅助口径尚未全部覆盖，具体范围见同名JSON及重算输出。 |
| tab:cost | recomputed_sources | test.replay_nov15, test.replay_table_details | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。原始阶段名单已明确固定，不能换用当前全账本总额。 |
| main:table-13 | partial | test.review_metrics | 部分来源、配对子列或辅助口径尚未全部覆盖，具体范围见同名JSON及重算输出。 |
| main:table-14 | recomputed_sources | test.replay_nov15, test.replay_review_tables | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| main:table-15 | recomputed_sources | test.replay_nov15, test.replay_review_tables | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| main:table-16 | recomputed_sources | test.review_metrics | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| interface_study:table-1 | recomputed_sources | test.interface_blind.analyze | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:interfaces | recomputed_sources | test.interface_blind.analyze | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| interface_study:table-3 | recomputed_sources | test.replay_nov15, test.replay_review_tables | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| interface_study:table-4 | recomputed_sources | test.replay_nov15, test.replay_review_tables | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| interface_study:table-5 | recomputed_sources | test.behavior_feedback_analyze | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:expansion | recomputed_sources | test.replay_new_tables | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:expansion-libraries | recomputed_sources | test.replay_nov15, test.replay_table_details | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:expansion-sensitivity | recomputed_sources | test.replay_nov15, test.replay_table_details | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:expansion-frontier | recomputed_sources | test.replay_new_tables | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:library-repair | recomputed_sources | test.replay_library_repair | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| nov14_study:table-1 | recomputed_sources | test.replay_nov14 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| nov14_study:table-2 | recomputed_sources | test.replay_nov14 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| nov14_study:table-3 | recomputed_sources | test.replay_nov14 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:prefix-factorial | recomputed_sources | test.replay_nov14 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:history-replay | recomputed_sources | test.replay_nov15 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:task-history | recomputed_sources | test.replay_nov15 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:matched-feedback | recomputed_sources | test.replay_nov16 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:matched-feedback-usage | recomputed_sources | test.replay_nov16 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:draw | recomputed_sources | test.replay_nov17, test.paper_nov17 | 对应来源已重算；仍需逐格核对论文转写，不表示所有浏览器重新执行。 |
| tab:suites | specification | 无独立入口 | 规范/来源描述，仍需人工逐项核对，不适用准确率复算。 |

浏览器运行时、来源路径及本地论文输入哈希见同名JSON。源码路径存在不等于运行器或整套浏览器已在独立环境复现；原第三轮保持暂停。
