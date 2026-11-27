# Web-Bench 分项目研究

11 月 27 日的表格复验分别检验[两次从零建库后的连续操作](table/action_sequences/PROTOCOL.md)和[同一配置下修改选择与编辑函数](table/action_sequences/selection_mode/PROTOCOL.md)。

11 月 26 日的完整项目补测包括[文件管理器](file_explorer/document_library/PROTOCOL.md)和[计算器](calculator/key_groups/PROTOCOL.md)。旧表格的低分核查见[选区绑定的独立建库](table/selection_binding/replication/PROTOCOL.md)与[菜单事件传播](table/menu_propagation/PROTOCOL.md)。[问卷整页操作](form/survey_workflow/PROTOCOL.md)与[SVG 公开数据变化](typed_components/svg_public_geometry/PROTOCOL.md)均在官方评分前冻结候选。

11 月 25 日的主表复验分为[固定原库改配置](compact_planning/PROTOCOL.md)、[原模型实现类型化组件](typed_components/PROTOCOL.md)及[无回执目标补传](transport_completion/PROTOCOL.md)。原题上的方法变化和扩展到其他目标后的分母分别核对。

11 月 25 日的[自建库复验](self_build_modules/README.md)覆盖主表 A 的 17 个原准备失败或零通过格，保留每份库的两种部署与原同题对照。

11 月 25 日的[问卷 Flash 自建库专项](form/flash_self_build/README.md)单列完整源码交付、接口与 ES 模块入口修复，以及在全新库上的重复验证。

11 月 24 日的[多模型比较](backbone_matrix/README.md)包含表格与 SVG 的全项目实验。以下索引收录 11 月 21 日和 23 日的 26 个研究阶段。各项目下按研究问题查阅协议、实现和复算入口。[研究总览](../README.md) · [结果数据](../results/)

| 项目 | 研究阶段 |
|---|---|
| 表格 | [组件来源与同目标对照](table/library_sources/README.md) · [六个控制器的全配置枚举](table/controller_enumeration/README.md) · [将组件绑定到公开起始工程](table/starter_binding/PROTOCOL.md) · [保持既有接口的独立重建](table/compatible_rebuild/PROTOCOL.md) · [重建后端上的本地规划](table/local_planning/README.md) · [共享状态与组件职责](table/shared_state_contract/README.md) · [从公开需求设计可配置控制器](table/controller_build/README.md) · [按模式约束解码](table/schema_decoding/README.md) |
| SVG 图表 | [参考实现与模型建库](svg_chart/library_sources/PROTOCOL.md) · [公开数据与可见图形的交叉对照](svg_chart/fixture_audit/README.md) · [接口说明与起始工程](svg_chart/interface_documentation/PROTOCOL.md) · [调整接口及已有方案的恢复](svg_chart/interface_refinement/README.md) · [本地模型与精简接口](svg_chart/local_planning/README.md) · [保持既有接口的独立重建](svg_chart/compatible_rebuild/README.md) · [折线图绘图区的冲突需求](svg_chart/plot_geometry/README.md) |
| 表达式编辑器 | [三种生成流程的同目标对照](expression_editor/library_sources/README.md) · [固定空方案](expression_editor/empty_plan/README.md) · [参考库输出格式示例](expression_editor/interface_examples/README.md) · [32k 准备窗口](expression_editor/preparation_window/PROTOCOL.md) · [后十项需求留出](expression_editor/held_out_requirements/README.md) · [准备笔记的补充准入](expression_editor/preparation_notes/README.md) |
| 问卷 | [问卷组件来源比较](form/library_sources/PROTOCOL.md) · [仅用公开反馈修复](form/public_repair/PROTOCOL.md) |
| 绘图 | [短距离拖动与最小线长](draw/pointer_transition/PROTOCOL.md) |
| Flex 布局 | [卡片列数的冲突需求](flex/column_count/README.md) |
| React 博客 | [官方参考页、起始页和空白页校准](react_blog/runtime_calibration/PROTOCOL.md) |

冻结清单使用原始的仓库相对路径和文件哈希。复算既有阶段时使用其记录的模块入口。新目录和原路径的对应关系见[目录映射](layout.json)。

文件管理器对两份原库各自重放创建、嵌套、菜单、编辑与 JSON 往返等公开操作；逐个修复断点后再比较同题固定页与二十份模型方案。[操作与准入](file_explorer/interaction_contracts/PROTOCOL.md) · [跟踪刚刚创建的条目](file_explorer/interaction_contracts/entry_identity/PROTOCOL.md)
