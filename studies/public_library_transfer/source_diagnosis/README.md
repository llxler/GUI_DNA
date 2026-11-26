# 库来源与配置失败诊断

本研究追踪同一目标模型下 GPT-5 库得分低于 Self 的主表格子。最初的比较只涵盖 PDF 实际显示的模型与任务。后续干预保留原始分数，并同时检查配置是否成功编译、固定配置能否运行以及真正通过了哪些目标。[初始逐格数据](initial-comparisons.json) · [实验协议](PROTOCOL.md)

`sequences.cjs` 使用公开状态与事件合同在新建状态中执行连续操作，`todo.py` 管理同模型修复及目标配置，`run.py` 封存并评分。人工及 GPT-5 TodoMVC 库的函数没有改动。本文的固定槽位对照会按题目启用规定槽位，然后对每个可用槽位取第一个选项。Web-Bench 的固定示例则在每道题上使用同一页面。二者分别统计。问卷额外使用同一语义方案在不同库上编译。[问卷分组复验](../../webbench/form/survey_workflow/qwen_comparison/PROTOCOL.md)

运行 `uv run python -m studies.public_library_transfer.source_diagnosis.report` 可离线重算各组分子、分母和初始逆序的诊断证据。运行生成流程需要单独预算。带上 `--ledgers` 会对包括视觉评判在内的整轮账本逐项核对。原始回执和浏览器报告保存在本地 artifacts 目录，结果文件提供逐题状态及哈希。[逐格汇总](../../results/library-source-diagnosis-20261126.json)

Ministral 的原路由函数在迭代数组时向同一数组不断追加，触发了 Node 进程退出。公开样例的隔离恢复保留原动作与断言，每条操作独立运行，错误后的状态摘要限制长度，已结算响应按原请求复用。六份库的操作改进和两个文件管理器模型的条目身份对照均由汇总逐题列出。[恢复入口](public_worker.py) · [文件管理器协议](../../webbench/file_explorer/interaction_contracts/entry_identity/PROTOCOL.md)

对联合选择耗尽可见输出窗口的 Qwen 与 Flash，四种部署均在关闭额外推理的同一设置复验。部署使用原模型、原首库与原输入。SVG 的实现改动另行在原图表计划和封存后的新数组上检验。[可见输出](visible_choices/PROTOCOL.md) · [SVG 属性合同](../../webbench/typed_components/svg_public_geometry/attribute_contracts/PROTOCOL.md)

对仍有低分的 Self，枚举原库允许的全部配置。每项执行共同的新增、清理输入、存储与恢复操作，获得合格配置后重新让模型选择。原逐题页、固定原首例和距原配置最近的合格页一起报告。[配置检查与冻结顺序](visible_choices/core_profiles/PROTOCOL.md) · [实际选择](visible_choices/core_profiles/configurations.json)
