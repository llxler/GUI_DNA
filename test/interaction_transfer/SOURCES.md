# 外部规格与适配边界

2026-11-15通过GitHub连接器核对：

- TodoMVC `app-spec.md`，blob `d040877fd8895c4f18fa5190e4b8ee474ffa8ac4`：[公开规格](https://github.com/tastejs/todomvc/blob/master/app-spec.md)。本诊断使用添加、编辑提交/取消、完成状态、全选、删除、计数、清除、持久化和路由语义。固定存储名 `todos-transfer`、DOM选择器为评测适配；不检查CSS外观、README、npm目录结构或框架特性。
- js-framework-benchmark `README.md`，blob `5472130a7d9ca1ffe9cc9f5d31542ed78e6bfcf5`：[公开规格](https://github.com/krausest/js-framework-benchmark/blob/master/README.md)。使用创建、替换、追加、每十行更新、选择、交换、删除、清空及keyed DOM身份语义。保留1000/10000行规模，但不测性能。为可复算明确固定标签为 `Row N`、追加后ID递增、交换第2/999行、更新后缀 ` !!!`；这些细节是本诊断的适配约定，不冒充原始官方评分。

这是新合成的功能组合/交互序列诊断，**不是官方TodoMVC或js-framework-benchmark成绩，也不是官方Web-Bench任务**。只有两个来源应用；熟悉应用的训练先验、人工选择原语与DOM约定仍是局限。开发检查逐项或短序列，留测交错操作检查共享身份、全局计数、筛选/编辑/持久化一致性。未提供的组合轨迹不进入建库或候选提示；动作语义本身来自公开规格/明确适配，不能称全新语义发现。
