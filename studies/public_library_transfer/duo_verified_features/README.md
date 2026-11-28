# WebApp1K-Duo 双功能组合

每题给出两个公开功能名。四条路线在同一模型行使用相同的官方组合文件，每个文件的四项断言全过计一题。Gemma 3 12B 和 Qwen3.5-9B 延续原比较中的五个博客组合，其他四款模型延续五个博客和五个任务管理组合。独立抽取的十个新组合另列。数值见[实验结果第 60 节](../../../docs/results.md#duo-verified-features)。

| 要核对的内容 | 入口 |
|---|---|
| 四种方法的原始记录、分母和固定对照 | 在仓库根目录运行 `python -m studies.lookup webapp1k-duo "DeepSeek V4 Flash" Self`。输出的 `targets`、`method_record` 和 `record_filter` 指定要读取的行。[组表代码](report.py) |
| 为什么此前没有 Human | [固定提交、四个发布版本和字段清单](source-audit.json)。作者发布生成代码，未查到可归属的人工业务实现。 |
| Human 测了什么 | 第三方人工维护的 Final Form 与 React Final Form 管理状态和提交，研究宿主负责传输和显示，模型独立填写业务绑定。[SDK 协议](form_sdk/PROTOCOL.md) · [正式收据](form_sdk/declared_config/result.json) |
| GPT-5 和 Self 如何建库 | [单功能来源顺序](PROTOCOL.md) · [组件与宿主接口](component_contract/PROTOCOL.md) · [资源路由](resource_routes/PROTOCOL.md) · [原作者补写](author_completion/PROTOCOL.md) · [字段与资源绑定](field_bindings/PROTOCOL.md) |
| 组件还是计划带来的差异 | 用相同模型配置复算[补写前的组件](author_completion/same-choices.json)，与[正式得分和固定功能对](field_bindings/result.json)按题名相连。 |
| 新组合能否复现 | [抽样与修复次数](unseen_pairs/PROTOCOL.md) · [抽样与候选](unseen_pairs/result.json) · [真实路由适配](unseen_pairs/router/result.json) · [按实际入口执行四例的两批正式成绩](unseen_pairs/entry_points/result.json) |
| 成本与版本 | [本轮按建库者和调用阶段记账](accounting.json)，包含未结预留和旧研究账本范围。[实际模型、输入与用例执行核验](verification.json) |

公开单功能用例与双功能评分有重合，逐题选择也能直接读取两个功能名。十个新组合检验新功能在相同两个域中的组装。开发复测保留首次结果。原运行环境、原始回复和 Jest 日志在本地 `artifacts/`，Git 中的 JSON 保存逐题结果、来源和指纹。[本地复验入口](../../../docs/reproducibility.md#duo-feature-check)
