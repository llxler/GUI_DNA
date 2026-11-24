# 从参考库设计改进 AI 建库

Web-Bench 的 table 和 svg-chart 都记录过 GPT-5 建库、Mistral 逐任务组装通过 3/20。两个分数对应不同故障，适合分别检验实现质量和接口质量。下表用于研究设计与事后解释。新建库器只接收各实验协议允许的公开材料，本页、参考代码、官方断言及已知通过位置均留在生成流程之外。[table 逐项记录](../studies/results/table-library-sources-20261123.json) · [svg-chart 逐项记录](../studies/results/svg-chart-interfaces-20261123.json)

## 六种参考库提供了什么

| 项目 | 组件来源与组装单位 | 对建库方法的启发 |
|---|---|---|
| TodoMVC | 研究者依据规范与测试编写 24 个函数。事件处理更新共享待办状态，后处理负责持久化，读取函数据状态派生筛选视图。 | 给一个完整事件写清输入、状态更新、外部效果和下一次渲染。独立函数可通过同一状态协作。[函数库](../studies/todomvc_dna/library.py) · [执行顺序](../studies/todomvc_dna/domain.py) |
| Web-Bench dom1 | 从上游参考实现拆出函数并加入语义变体，共 44 个。六个二选一槽位控制不同策略，菜单项和快捷键另用列表绑定。 | 生命周期的稳定部分可留在实现内，确有多种行为的地方才交给方案选择。该库使用了参考实现，不能据此声称盲建库器也知道怎样划分槽位。[库源码](../studies/webbench_dna/library.py) · [来源说明](method.md) |
| form | 参考编译器从导出的题型类读取可用名字，并把参数传给对应构造器。方案另指定插入位置、问卷标题及导出。 | 将对象类型、实参及约束放入同一份可检查的接口。遇到不符合约定的实参时，规划器可以获得公开验证错误。[编译器](../studies/webbench/form/library_sources/compiler.js) · [公开格式修复记录](../studies/results/form-public-repair-20261121.json) |
| table | 上游七个生产模块提供表格状态和交互。研究绑定用六个开关挂接事件控制器，全部 64 种组合可离线执行。 | 先让控制器完成事件处理、状态修改和视图更新，再暴露开关。固定全开页已通过 20/20，因此还应测量逐任务选择相对固定页的增量。[绑定与来源](../studies/webbench/table/library_sources/README.md) · [组合枚举](../studies/results/table-controller-enumeration-20261123.json) |
| svg-chart | 上游渲染类接收公开起始数据。参考绑定按数据的图表类型选择渲染类，类名和允许的键可以逐项列出。 | 区分输入数据与配置，文档只列编译器真正接受的名字。在同一参考实现上，枚举接口比原文字说明多生成 3 张有效且通过的页面（17/20 → 20/20）。[编译器](../studies/webbench/svg_chart/library_sources/compiler.js) · [同实现配对](../studies/results/svg-chart-interfaces-20261123.json) |
| expression-editor | 上游六个模块负责解析、求值、编辑、高亮、诊断与补全。研究绑定暴露四种工具栏命令与六种控制器；固定空方案保留了基础编辑器，已通过 7/20。 | 说明空方案保留哪些功能，并展示一个能直接提交的最短方案。对已取得响应的九个位置，末尾重述接口并附空方案后，有效方案由 0/9 升至 9/9。此诊断同时改变了示例和位置。[绑定](../studies/webbench/expression_editor/library_sources/binding.js) · [空方案对照](../studies/webbench/expression_editor/empty_plan/README.md) · [接口示例诊断](../studies/webbench/expression_editor/interface_examples/README.md) |

## 按生成模型选择建库检查

从历史七个 Web-Bench 模型的实际交付中，可以把下一次修复放在具体的编译、挂载或交互步骤。下表第三列是后续新建库使用的检查；已经实测的离线修复在末列标出。人类实现及历史故障分析只供研究者制订协议，不作为建库模型的输入。[逐模型原始故障](../studies/results/self-failure-diagnosis-20261124.json)

| 模型 | 已见故障 | 下一轮建库检查 | 本轮已验证的范围 |
|---|---|---|---|
| Qwen3-Coder-30B | 能写出事件控制器，TodoMVC 交付完整 JS 却被 JSON 接口拒绝；生成的配置声明没有读取者。 | 直接接收源码，验证配置改变一次真实交互；多模块逐个链接真实导出。 | TodoMVC 恢复为 8/8，固定页、从零也都是 8/8。 |
| Qwen3.5-9B | 长设计可能耗尽推理额度；问卷库可加载但全部合法设置仍无一题可过。 | 按组件短调用，先拿到实现和可交互实例，再声明控制项；空回复计入失败。 | Duo 的原组件按两个公开功能名组装为 3/10，从零 2/10。 |
| GPT-OSS-120B | 表格库穷举仍无可用设置；Duo 有完整 React 组件埋在不合协议的返回里。 | 让每个组件独立以源码交付；在准备阶段逐项过公开功能，然后配对。 | Duo 取回组件后 6/10，从零 5/10。 |
| Gemma 3 12B | 部分项目用错配置字段、锚点和相对路径；TodoMVC 的主要实现先于损坏的附加元数据。 | 分开交付可执行源码和配置，解析声明及首例，并检查控制项是否确实被读取。 | TodoMVC 完整控制器 6/8，从零 4/8；Duo 未取回足够组件。 |
| Mistral Small 3.2 | 图表构造器缺失，Duo 从零代码的 React 默认导出也存在语法错误。 | 两组都检查导出和宿主加载。若已加载，转查事件状态及组件功能。 | 修复 Direct 的导出后 Duo 两组同为 4/10；TodoMVC 恢复的库仍低于从零。 |
| DeepSeek V4 Flash | 部分 Web-Bench 回复没有可解析包；在单个控制器和成组组件间交付差异较大。 | 单页保留可运行控制器，跨模块每个调用只写一个单功能；先验证模块交付齐全。 | TodoMVC 已有固定控制器 8/8，从零 2/8；Duo 重用旧模块 0/10，从零 6/10。 |
| DeepSeek V4 Pro | 多次长 JSON 字符串截断；一次表格修复后仍引用不存在的导出。 | 先生成独立源码文件，检查完整函数及导出，再生成依赖方。 | 该模型未参加六模型 TodoMVC / Duo 复测，保留未测。 |

Duo 的组合名明确给出两项功能。表中的离线组按这些公开标识装配，从零的声明修复不改业务代码。TodoMVC 也对两组对称提取源码；对能恢复的三个控制器，开关取值无法改变实现。后续用新会话分别检验交付和行为，保留所有独立库。[两套件同题结果](../studies/results/library-domain-replay-20261124.json)

计算器使用公开起始工程，研究者提供的按键注册表与标准数学运算连接同样属于准备工作。在引入这种领域脚手架时，要同时跑去掉模型代码的绑定器、仅由模型选择运算的库和可接收完整或截断 HTML 的从零组。Duo 的公开输入是单功能材料与命名组合；该协议没有已登记的人工组件实现。BOM、绘图、canvas、flex 的人工组件来源和已测里程碑仍按各自记录保留。[项目覆盖](roadmap.md) · [计算器实验](../studies/public_library_transfer/self_refinement/local_domain/PROTOCOL.md)

## 对两个 3/20 的检验

| 项目 | 冻结的旧 AI 包 | 新方法最需要检验的假设 |
|---|---|---|
| table | 首轮生成 18/20 张有效页，通过 3/20。一次公开格式修复后 20/20 有效，仍只通过原来的三项。预先指定的固定示例也恰好通过这三项。 | 为编译器生成可执行的交互模块，并用公开需求自拟事件序列检查动作后的状态与外部表现。比较新版固定示例和逐任务方案，分别观察库自身能做什么以及规划器找到了什么。[原始配对](../studies/results/table-library-sources-20261123.json) · [公开行为探针及其采样范围](../studies/results/table-behavior-probe-20261118.json) |
| svg-chart | 收到 20 个逐任务响应，只有 4 个能生成页面，其中 3 个通过。公开起始工程本身通过第一个目标，无库直接生成在其余 19 项通过 2 项，AI 库组通过 3 项。 | 根据建库器自己实现的接口生成短指南，给出精确字段、合法值和最小可编译示例。先统计可生成页面数，再逐项检查新增页面是否也通过公开基准评分。[完整分母与 19 项单列结果](../studies/results/svg-chart-interfaces-20261123.json) |

建库提示可要求先从公开需求提取“输入动作 → 状态变化 → 可观察结果”，将跨需求共享的处理逻辑实现为模块，然后用同一份配置定义驱动编译和文档。自检示例应覆盖默认行为和一次改变行为的配置；同一初始输入下先执行动作，再判断观察结果。示例、探针和修复只能依据建库时获准使用的材料生成。在冻结候选之前保留自检输入、结果及修改记录。

## 怎样确认提升

1. 封存新协议、项目、建库与规划模型、公开材料、预算、输出上限、修复机会、独立建库次数和通过条件。旧 table 的 GPT-5 建库上下文没有逐任务阶段可用的完整起始工程；若新版增加材料或改用分阶段生成，应披露整个流程的改变。只有在相同条件下控制单一因素，才能把改善归因到提示词。[旧 table 协议与来源](../studies/webbench/table/library_sources/PROTOCOL.md) · [旧 svg-chart 协议](../studies/webbench/svg_chart/interface_documentation/PROTOCOL.md)
2. 沿用同一批 20 个需求和同一规划器，保留每个计划的初次响应。分别报告建库交付、首轮有效页、首轮官方当前任务通过、修复后的同一指标。逐项给出旧新均过、仅新过、仅旧过和均未过。独立重建另成一列，保留失败包和未观测请求。复评同一个冻结页面只验证评分复现；验证建库改善还需要独立生成的库。
3. 公共起始工程、预先选定的固定示例、从零生成结果可直接在本地复核。用跑完测试才选出的最佳固定配置会高估复用效果。table 与 svg-chart 的 20 个位置来自各自同一项目，不宜把分别建库的多个结果合并来表示一次实验的成功率。在获得约定的独立确认后，再将全面复测列入路线图。

## 本轮通过复验的配置与边界

1. **建库输入。**给建库模型公开需求和真实起始工程。编译器保留起始 DOM 与样式，让模型自己决定语义开关、默认值和模块实现。在表格两次独立建库中，开关名称和划分都由模型生成。仅在旧库上换回起始工程，两批均仍为 3/20。[建库程序和提示](../studies/webbench/table/controller_build/build.py) · [起始工程对照](../studies/results/library-refinement-table-20261123.json)
2. **提交格式。**给规划器当前需求前缀、所属库的闭合模式和首例。确定性解码器填入键和标点，逐个值只允许模式定义的布尔值或枚举，模型在合法 token 中选择。表格结果为同协议旧库 3/20、新库一和新库二各 18/20；每个新库的全部 20 次规划都选择了首例。区分源自新实现的收益与因避免无效配置而恢复的部署。[解码器](../studies/webbench/table/schema_decoding/generate.py) · [与自由输出、固定页的逐题配对](../studies/results/schema-constrained-table-20261123.json)
3. **跨项目复验。**固定首例是必要对照。图表首例在两次新实现上由 17/20 到 18/20；允许单个围栏后，三库的十个合法响应均只通过 8/20。直接迁移表格的有限枚举尚不能覆盖图表的数值、颜色或数组。按原基准的正式输入和断言单列协议，以新项目实测判断能否推广。[图表重建](../studies/results/compatible-chart-rebuild-20261123.json) · [历史复测清单](roadmap.md)

### 按公开失败改建库接口后的复测

| 模型与项目 | 可以定位的失败 | 在同一组官方目标上的复验 |
|---|---|---|
| GPT-OSS、Qwen3.5 · Duo | 模型选对了两个公开功能名，但组件没有触发需要的交互 | 每次单写一个组件，并给组件和从零都做公开行为检查。GPT-OSS 两库 9/10、6/10，从零 9/10。Qwen 再简化界面契约仍未过整题。 |
| Gemma 3 12B · TodoMVC | 旧代码声明开关却不读取，另有从零代码因重复声明无法解析 | 每个键两端重复观察动作与状态，两份库确有 1、2 个有效键。新库 0/8、5/8，固定页逐题相同；对称修复分支作用域后的从零 6/8。 |
| Qwen3-Coder · SVG | 子类引用未导入的父类；浏览器类名 API 拒绝有空格的单个 token | 解析真实导出、实测整个绘图入口，已有六类图形都可画出。两库 7/20、5/20，强从零 5/20，固定全开得分相同。 |
| GPT-OSS · 问卷 | 独立控件全部能用，完整页面选择了错误的行为，如题目要求导出却关闭开关 | 逐题 5/20、6/20，从零 12/20。下一步检验填表、导出、重载的整条交互。 |

相同的公开反馈应给从零一方。比较两套独立库时，既看每套相对共同从零增加了什么，也检查一个固定配置是否已经做到。[整批结果](results.md#47-按公开运行反馈独立建库再用同模型组装)

## 全面复测时需要区分的旧实验

- Web-Bench 已有逐任务 AI 库数据的项目有 dom1、form、calculator、table、bom、draw、canvas、flex、svg-chart。前六项按历史建库者分别复测，canvas 还要区分输出上限与独立建库次数，flex 保留原来的五个里程碑协议。svg-chart 另列独立的 20 项实验。各组复用真实共用的从零生成记录，分母逐列核对。[两流程记录](../studies/results/end_to_end.json) · [三种库来源记录](../studies/results/library-sources-20261121.json) · [svg-chart 结果](../studies/results/svg-chart-interfaces-20261123.json)
- expression-editor 的原始全需求协议在建库阶段两次达到输出上限，未交付可解析的库。另有准备窗口与留出需求协议。复测应保留各自的信息范围，并先报告能否交付可用包。[完整需求研究](../studies/webbench/expression_editor/library_sources/README.md) · [准备窗口](../studies/webbench/expression_editor/preparation_window/PROTOCOL.md) · [未见需求](../studies/webbench/expression_editor/held_out_requirements/README.md)
- 旧 TodoMVC 另有盲建库研究；论文中的 128/128 来自人工库。WebApp1K-Duo 模型生成组件按原项目单列复测。旧合成的留出组合与冻结库修复保留归档，列在溯源索引中；公开基准复测以各自正式的任务与断言为准。React 博客目前仅有基准校准，可另列为新项目。[TodoMVC 盲建库](../studies/blind_library.py) · [WebApp1K-Duo](../studies/webapp1k_dna/README.md) · [留出组合](../studies/heldout_composition/README.md) · [冻结库修复](../studies/library_repair/README.md) · [React 校准](../studies/results/react-blog-calibration-20261123.json)
