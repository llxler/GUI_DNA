# GUI-DNA：数据、生成流程与评测口径

主表 A、B 按生成模型和相同目标报告 Direct（从零写代码）、Human（人工组件）、GPT-5（冻结 GPT-5 实现）、Self（同模型建库并部署）。针对原低分格，先固定实现改变配置提示，再让原模型按公开签名写问卷类、表格交互或 SVG 渲染器。研究者提供编译器、入口接线或事件路由；模型写可执行组件。开发集上的重测按事先登记的顺序采用可部署的首库。固定配置、相同题目的旧成绩和新增题目的观测分别保存。TodoMVC 的 GPT-5 库使用人工定义的函数槽位，33 个函数由 GPT-5 实现，历史建库费为 0.2054 美元。C 区使用一次登记的九个新网站，各方法按同一模型、站点和操作配对。只有视觉判官给出完整通过才计一次。[红框配置](../studies/webbench/compact_planning/PROTOCOL.md) · [组件复验](../studies/webbench/typed_components/PROTOCOL.md) · [TodoMVC 库来源](../studies/results/blind-library.json) · [新基准登记](../studies/webgen_bench/protocol.json)

表格的编辑与矩形选区两个开关形成四种配置。GPT-5 表格原作者修订只看原实现和公开菜单操作，以两次独立请求修复入口事件。四种配置均须能打开、插行并在表外关闭菜单。计分复用五款模型已封存的逐题配置。[原作者修复协议](../studies/webbench/table/menu_propagation/author_repair/PROTOCOL.md)

主表表格库合并了 GPT-5 按公开需求自查后写出的四个文件，以及它根据右键事件传播记录写出的入口修复。文件没有交叉，按登记顺序取首份通过公开检查的入口实现。七款模型各为 20 个目标重新选配置，同一选择分别在原库、只自查、只修入口和合并库上运行。表格 Self 的新模型自行划分模块并声明接口。接收器对对象或数组形式的接口声明保留完整内容，再请求模型写实现。若连续三份实现未通过菜单和选格准入，原作者可以根据真实点击轨迹，对自己的文件提交可唯一定位的局部替换。顶层编辑数组单列离线重放，每份答复只作用于它实际收到的源文件。仍未准入时，研究者的公共绑定把浏览器事件交给四个短函数。模型负责菜单 DOM、命令执行、菜单关闭和选区效果。旧代码也按相同选择重放。若处理函数调用仅存在于设计说明中的 API，原作者使用真实 DOM 节点独立修订同一函数。四项交互均成功却仍抛出异常的库，再按预先固定的顺序选择同作者四个新增处理函数的子集，和全装四函数、未额外接线的原库共用目标选择。[监听器选择与固定页](../studies/webbench/table/event_hooks/handler_selection/PROTOCOL.md)[真实参数的修订](../studies/webbench/table/event_hooks/dom_contract/PROTOCOL.md) · [事件接口](../studies/webbench/table/event_hooks/PROTOCOL.md)[四份 GPT-5 源码对照](../studies/webbench/table/author_modules/PROTOCOL.md) · [Self 建库与接收范围](../studies/webbench/table/model_modules/structured_design/PROTOCOL.md)

计算器保留公开起始工程可用的数字与四则运算。每个 Self 模型自己实现科学键、记忆、外观及历史。通用绑定器负责接收按键、传递显示值和记忆值，具体运算由模型编写。修订只看公开操作，必须保留原先通过的检查并至少多过一项，按登记顺序最多重建三次。部署模型根据实际页面的按钮和操作结果选配置。正式评分分别交叉新旧源码和新旧选择，也重放固定页、无效按键和空宿主。Gemma 与 Qwen3.5 的按键清单混入了起始页按钮或重复列出运算。先从本模型的原始交付读取功能键，再逐键补交缺失运算，复用已封存的 20 份选择。另用已有数字的显示框检验召回。缺整组记忆键时由同模型分别写每键的显示表达式和记忆表达式，沿用其早晚按键顺序。[非空显示与独立数据](../studies/webbench/calculator/memory_recall/PROTOCOL.md)

GPT-5 在此接口的请求未交付，旧原生接口的成绩单列。[建库与固定页](../studies/webbench/calculator/behavior_modules/PROTOCOL.md) · [按键与配置的交叉实验](../studies/webbench/calculator/key_programs/PROTOCOL.md)

公开回放在同一个右键事件的表格阶段与文档阶段分别读取菜单可见性，另测单击后 Delete 的结果。Self 表格组件另行固定安装接口，按公开需求指定的文件拆分实现，并实际验证右键操作能增加一行。Flash 问卷将从零、人工库、GPT-5 库及两份原 Self 库的全部逐题请求分别复用，仅在五组同时关闭额外推理；保留原输出上限和评分文件。[四种配置的事件记录](../studies/webbench/table_interactions/public-actions.json) · [按职责生成组件](../studies/webbench/table/event_modules/focused.md) · [Flash 同解码协议](../studies/webbench/form/flash_self_build/visible_targets/PROTOCOL.md)

文件管理器的模型库从其实际交付的完整 HTML 启动，只有能在浏览器中新增可观察行为的可选模块才开放给配置。计算器的官方起始页已有四则运算。人工库取上游计算器实现并划出五组可选键；Self 须实际完成 2+3=5、一次可选运算及关闭该组选项后的复查。文件管理器的从零回复按外层格式接收：先解 JSON 文件包，独立 HTML 整页另行接收。文件包字段按原文件规则验证。[原回复的离线复验](../studies/webbench/file_explorer/target_models/direct_reception/PROTOCOL.md)

两项目的从零组均从当前需求和起始工程独立生成；首库、第二份独立库、固定页及起始页分别登记。[文件管理器协议](../studies/webbench/file_explorer/document_library/PROTOCOL.md) · [计算器协议](../studies/webbench/calculator/key_groups/PROTOCOL.md)

论文把交互行为抽象为可组装的库。人工库在 TodoMVC 上通过 128/128（无库 116/128），在参考实现拆库的 dom1 协议下通过 126/140（无库 52/140）。AI 建库实验另按协议比较，用来检验只提供公开需求时能否得到可用的抽象。

研究以给定人工库的组装为主；AI 根据公开需求建库是第二种来源。无库生成作为各协议内的对照。目录入口和安装见根 [README](../README.md)；本文解释各自知道什么、输出什么，以及结果代表什么。

## 问卷自建库的交付与验证

问卷实验区分三类失败：模型没有交付源码，有源码但未能从公共入口编译加载，以及已有可执行页面但没有满足目标行为。DeepSeek V4 Flash 的独立复测只在建库阶段显式关闭额外推理，逐题部署继续使用原参数。接收端记录枚举值变更和入口模块的源码哈希，在原始 form 中加载默认配置和首例。定点修复条件允许同一模型根据公开 Node 行号或浏览器诊断只改已交付的文件。每个重复都同时保存逐题结果和固定首例，与原同目标的三个对照分别比较。[问卷协议与逐阶段记录](../studies/webbench/form/flash_self_build/README.md)

## 公开语义控件的独立建库

十项目复测统一提供上游公开起始工程、资产与完整需求。建库模型自行确定一至六个语义控件、默认值和首例；装配器支持布尔值和有限枚举。仅对建库输出格式及默认/首例的公开加载错误允许一次修复。逐题规划在建库者声明的合法值中选择，直接生成仅接收同一当前需求前缀、起始工程和公共资产。两套订阅库均有独立会话和独立固定首例。目标生成模型相同的两套库共享同一份从零响应。WebApp1K-Duo 和 TodoMVC 使用各自的组件或任务协议；编辑器另有只用前半段需求建库的留出条件。费用、无响应和同一项目内重复分别报告。[十项目协议](../studies/public_library_transfer/PROTOCOL.md) · [其他基准协议](../studies/public_library_transfer/other_benchmarks/PROTOCOL.md) · [原实验模型及公开材料](../studies/results/public-library-transfer-history-20261123.json)

论文总表以目标生成模型为行，每个项目统一用 Direct（从零代码）、Human（人工组件库）、GPT-5（冻结 GPT-5 库）、Self（同模型自建并部署）四列。Web-Bench 的表格、SVG、问卷、文件管理器和计算器各登记 20 个当前任务。前三个项目覆盖七款目标模型，后两个项目覆盖 Gemma 3 12B、Qwen3.5、GPT-OSS 和 Flash。TodoMVC 与 Duo 使用各自的功能目标。未评测的方法标横线。Flash 的问卷 Self 主格采用登记顺序中的第一份库。本地复验记录给出第二份独立库及两份库各自的固定首例。各行只比较这些方法共同取得观察的目标；建库失败的成绩格留空。已通过建库准入的库，若目标方案不合法或官方任务未通过，则该目标判失败。缺失响应单独标记。Duo 只建成部分领域时，从零和 Self 在同一批已建成领域的目标上比较。表格和 SVG 共登记 12 个模型，问卷随后纳入全部 7 条可用路线。附录的早期供库实验沿用原协议，文件管理器基线逐步编辑前一页。供库、部署和从零的费用逐模型记账，固定首例另行重放。[同任务实验协议](../studies/webbench/backbone_matrix/PROTOCOL.md) · [总表逐格依据](../studies/results/paper-performance-matrix.json)

当前 WebGen-Bench 按原哈希顺序在每类取第 4 至第 6 个网站，共九站。锁定的数据文件只有站点编号、需求、类别、应用类型和操作期望五个字段。Human 的代码来自百度 amis 组件库，具体站点的行为由模型配置。每个模型只读当前站点的公开需求，分别交付从零页面和一份配置。人工 SDK、GPT-5 库以及目标模型自建库读取完全相同的配置。提示要求把操作对应到控件和可见结果；写整页与写配置使用相同模型、解码和输出上限。封存后，每个网站的每项操作在新的浏览器会话中执行。部分完成和未完成均不计通过，缺判从各方法的共同分母剔除。人工端对全部页统一使用 SDK 原生纵向标签，在原视口内把所有入口暴露给视觉判官。原横向模板的判决单独保存。C 区的完整通过由替代视觉判官判定，A、B 使用可执行测试。[方案与运行器](../studies/webgen_bench/site_completion/PROTOCOL.md) · [统一修订的导航模板](../studies/webgen_bench/site_completion/SDK_NAVIGATION.md)

早期 WebGen-Bench 六站试验中，每个网站各生成一个页面，每站各项操作在独立浏览器会话评分。Direct 输出单站完整 HTML，另外三种方法共用该模型为该站生成的同一份配置。人工实现来自百度 amis 6.13.0。自建库看六条公开建站需求，模型编写各类型交互，研究者提供 DOM 挂载、字段读取和输出绑定。建库公开检查使用独立的阅读室页面。评判器仅读网站功能操作和期望，完整、部分、失败分别得 1、0.5、0 分。可交付性和实际功能分别计数，原始三级判决和半分制保存在历史记录中。[生成与判分协议](../studies/webgen_bench/functional_pilot/PROTOCOL.md) · [函数接收与输出绑定](../studies/webgen_bench/functional_pilot/function_binding/PROTOCOL.md)

此前的独立复验在另外三个同类别网站上检验冻结库的迁移。建库者只见开发材料，新站只把自身公开需求交给页面生成器。Gemma 根据浏览器对首次挂载和切换的观察，局部修改自己的标签函数；Qwen 改用由自身子组件生成的 DOM 片段，再校正原生对话框的打开状态和表单提交反馈。宿主负责传参、挂载和事件分发，模型负责交互。移除新函数的对照接受相同宿主输入。实际放行仍须通过五项公开组合操作。各模型的首个准入库和此前失败都保留。TodoMVC 另外将纯状态函数的输入事件与预期变化成对展示，并用封存后产生的新条目标识、原方案和固定全开分别验证。[网站协议与运行顺序](../studies/webgen_bench/component_contracts/README.md) · [待办实验](../studies/public_library_transfer/compact_todomvc/state_examples/PROTOCOL.md)

库来源诊断首先固定实际页面、目标与已有实现，分别核对建库准入、可编译配置数、固定方案覆盖和逐题选择独有通过项。SVG 在控制目标规划的分支保存原设置与固定首例；自建实现的分支按模型原字段、真实 DOM 属性和公开绘图数组验收。后续新数组到候选封存后才进入检查。文件管理器按点击前后的新条目身份跟踪状态；TodoMVC 在新建两条记录后再切换、编辑、保存或刷新。各阶段固定页与原实现同步保留。对 TodoMVC 的原自建库另枚举全部布尔配置，在独立浏览器逐个执行新增、去空、保存和重载。保留全部公共操作都成功的配置，再让模型逐题选序号。原输出、固定首项和距原输出最近的合格配置分别复验。[公开准入协议](../studies/public_library_transfer/source_diagnosis/visible_choices/core_profiles/PROTOCOL.md) [库来源比较](../studies/public_library_transfer/source_diagnosis/PROTOCOL.md) · [SVG 属性与新数组](../studies/webbench/typed_components/svg_public_geometry/attribute_contracts/PROTOCOL.md) · [文件管理器新条目身份](../studies/webbench/file_explorer/interaction_contracts/entry_identity/PROTOCOL.md)

自建库复测把三件事分开记录：模型是否交付可加载的库、能否为该题交付合法配置、页面是否通过当前任务文件。每个独立库先冻结首个示例，再同时评估逐题配置和固定首例。另将已交付且不超过 32 种配置的旧库全部设置穷举，检查哪些需求能由现有实现达到。新建库使用的完整公开需求、源码生成与公开修复均计入准备成本。从零组按同一目标生成模型和解码设置配对，多个库共享同一份从零页。[自建库故障诊断](../studies/public_library_transfer/diagnostics/self_failures/PROTOCOL.md) · [可达性协议](../studies/public_library_transfer/diagnostics/self_capacity/PROTOCOL.md) · [原生接口对照](../studies/public_library_transfer/self_refinement/native/PROTOCOL.md)

对已经能加载的库，还可以让建库模型回到自己的源码，把一个明确的动作写成两个可执行取值。提案指定唯一原文片段、替换内容和预期行为，再用同一个公开交互检查两个取值。通过验证后才把选项交给逐题生成器，另行验证换值是否能通过原先失败的目标。[源码定位与交互验证协议](../studies/public_library_transfer/self_refinement/coherent/linker/executable_options/PROTOCOL.md)

对不合外层格式却包含完整实现的交付，还可以从同一冻结回复恢复源码。TodoMVC 接受完整控制器，绑定它实际声明的布尔键；从零调用使用同一源码提取规则。Duo 只抽取完整 React 模块，先建项目内索引，再按目标公开给出的两个功能名装配。两种部署都使用确定性程序。复验记录的 Bind 表示离线部署。主表的 Self 表示模型自己建库、自己选配置。Duo 的 Direct* 另允许只修正默认导出声明。两个项目按各自共同目标比较。[协议与直接对照](../studies/results/library-domain-replay-20261124.json)

本地小模型另测研究者给定的领域接口。计算器提供共享状态、按键注册表和有限运算语法；TodoMVC 提供事件函数签名、路由和持久化时机。每种接口均用两个独立库及同一组新从零代码。计算器同时比较两种固定顺序，以及不含模型代码的标准数学绑定；TodoMVC 同时比较可选事件组全开和全关。按函数建库与逐题从零的调用次数分别记录。[计算器协议](../studies/public_library_transfer/self_refinement/local_domain/typed_keys/PROTOCOL.md) · [TodoMVC 协议](../studies/public_library_transfer/self_refinement/todomvc/event_modules/PROTOCOL.md)

TodoMVC 的小模型配置按开关询问当前是否允许执行动作。相同模型、需求和开关只询问一次，两份独立控制器共用这次回答。此后保持开关答案，分别修复根据全部事项计算页脚的视图函数，以及在切换筛选时保留事项的路由函数。八个官方子集用原浏览器判定，另外九条短需求单独检查能否进入编辑，以及在刷新后能否保留事项并退出临时编辑状态。首次回答格式不合法时只允许澄清一次，仍无法解析就计部署失败。[逐开关协议](../studies/public_library_transfer/compact_todomvc/edit_choices/PROTOCOL.md)

计算器的 GPT-5 建库者原本给出了两个合法示例。表中四款模型先交付原生配置。编译器拒绝时，模型再从两个原示例中选一个编号。可编译的页面直接进入官方测试，传输缺失单列。两个固定示例在全部二十题上评分；只选编号的独立实验也逐模型报告。Mistral 另用同一流程测试部署。人工库及 Self 使用各自的接口。[按编译结果补问](../studies/webbench/calculator/compiler_fallback/PROTOCOL.md) · [只选编号的对照](../studies/webbench/calculator/example_selection/PROTOCOL.md)

## 1. 同一需求下的三种生成方式

Web-Bench 的 50 个正式项目各有 20 个编号任务。初始化可以由公开起始文件给出，也可以写在需求序列中。新实验的第 k 个目标取得截至第 k 项的累计描述。

| 阶段 | 人工库＋GUI-DNA | AI 建库＋GUI-DNA | 无库代码 |
|---|---|---|---|
| 准备 | 给定开发者实现的组件与可用绑定接口，登记规范、测试或参考代码的接触范围 | AI 从公开需求生成包、接口与编译器，冻结首个通过公开构建检查的包 | 按协议读取起始工程、需求及运行合同 |
| 目标生成 | 用数据方案实例化或连接组件 | 用数据方案配置冻结实现 | 生成页面代码；旧 dom1 是编辑前一页 |
| 反馈 | 依阶段协议；新双库来源实验均只取一次目标响应 | 同左；建库修复另计 | 与同项目两库组采用相同目标响应次数 |
| 评分 | 所有候选冻结后执行当前任务的官方断言 | 同一官方文件 | 同一官方文件 |

在 form 和 svg-chart，人工组的核心行为实现逐字来自上游参考源码，绑定胶水由本轮编码助手编写。AI 组分别复用旧 GPT-5 包、从零新建 GPT-5 包。实际建库费用和未知预留分别计入各阶段；本地人工准备工时没有可靠记录。

“无库”不表示不知道需求。当前历史实验的建库阶段额外知道未来需求、花了额外计算，因此这是工作流比较，尚未匹配全部信息和总预算。后续的 canvas 与 flex 匹配研究给双方全部公开需求、一次准备及同一美元上限。无库组用准备调用写自己的实施笔记，随后为各目标独立写页面。逐项目协议见 [设计记录](end_to_end_protocol.md)。

模型提议的库不等于自建数据集：任务与评分来自公开 Web-Bench，模型只构建被评估方法使用的实现。旧自建二元组合/交错诊断保留历史，不进入当前论文。

## 2. 库与方案

一个包包含 `files`、`plan_schema`、确定性的 `compiler` 和 `examples`。AI 建库实验由模型提出实现与接口。人工库实验提供与该项目相符的组件和固定绑定边界。一般模式检查负责约束格式，不能保证隐藏行为通过。

生成者选择方案 `p`，编译器计算 `compile(p, files)` 得到可运行页面。方案本身不生成任意函数体；库能表达什么，由冻结模式和实现共同决定。实际库可能暴露丰富行为，也可能仅有主题、字号等外观选项，必须区分。

旧 TodoMVC 人工库可用来直观说明组装：`toggle` 更新完成状态，`persistTodos` 保存新状态，`visibleByFilter` 推导筛选后的列表。把函数绑定到事件、后处理和视图就是一个方案。但这些人工准备的函数不是当前 AI 建库的证据；旧 dom1 库还使用了官方参考实现，来源必须明确。

### 同目标比较与可表达性

表格、图表和表达式编辑器各预定二十个当前目标。三组比较只取三组共同可判定的位置。表达式编辑器的 AI 库未能部署，单列人工库与无库笔记均收到响应的首轮位置，AI 列留空。已收到但无法形成页面的输出记失败，传输缺失另列。表格和图表分别冻结参考组件、一次装配代码、AI 库和起始文件的来源。表达式编辑器的无库组单独获得 GPT-5 阅读公开需求后写的实施笔记。不同准备条件分别报告。

表格参考库的六个控制器可各自打开或关闭。将 64 种组合分别用于 20 个官方文件，按每种组合等权计算随机选择的期望通过数；固定全开页和实际模型方案分别计数。编辑器的独立提示实验在原消息末尾重复相同的方案模式，并增加一个合法空方案示例。仅在两种提示都收到回答的目标上比较，另核对模型是否照抄空方案。[随机配置协议](../studies/webbench/table/controller_enumeration/PROTOCOL.md) · [编辑器提示协议](../studies/webbench/expression_editor/interface_examples/PROTOCOL.md)

在表达式编辑器的未来需求实验中，两个准备者只看到任务 1–10。冻结库或笔记后，逐目标生成器才能读取截至任务 11–20 各自位置的前缀。这检验同一应用中新增需求能否通过既有资产表达；输入边界只约束本次调用能读到的内容。[未来需求协议](../studies/webbench/expression_editor/held_out_requirements/PROTOCOL.md)

图表另用同一人工库和同一编译器比较两份接口说明；两组都让 Mistral 输出方案。测量库能否适应需求时，固定测试输入与视口，对两种互斥行为分别找一个可行方案。只有穷举了与该行为有关的全部合法选项，才能据此认定某个端点不可达。研究者给出的可行方案、实际生成方案、官方文件成绩各自有独立记录。

## 3. 真实分母与当前任务指标

历史报告按建库者分列。两项目每列 80 个目标（2 项目 × 2 生成模型 × 20 任务），三项目每列 120 个目标，draw 每列 10 个目标。两个 GUI-DNA 条件使用各自的库，共用同一组真实无库基线；不能把基线复制后称为更多独立样本。列名明确指建库模型，目标生成模型另外分层报告。

- **当前文件**：保存的 task-k 页面通过官方 task-k 文件中所有断言。

| 研究 | 无库基线 | GUI-DNA：GPT-5 建库 | GUI-DNA：Claude 建库 |
| --- | --- | --- | --- |
| dom1、form | 25/80（31.25%） | 43/80（53.75%） | 43/80（53.75%） |
| calculator、table、bom | 42/120（35.00%） | 49/120（40.83%） | 44/120（36.67%） |
| draw 五里程碑 | 3/10（30.00%） | 8/10（80.00%） | 6/10（60.00%） |

BOM 六文件统一排除后，无库为 39/108，GPT-5 建库为 43/108，Claude 建库为 36/108；两套库相对基线分别为 +3.70 和 −2.78 个百分点。 原官方分数不改。历史 GPT-5 三项目小试没有无库条件，不补造比较。主视图中旧合并字段仅供对账，展示使用 `by_builder`、`by_project_builder` 和 `by_generator_builder`；敏感性和费用同样按建库者拆分。

匹配批次按项目、模型、输出上限和独立准备另表呈现。GPT-5 在 canvas 的 16k 首批两个库均未通过准备检查，不能把五个失败位置当作五份生成的方案。32k 时两个库均通过公开检查，逐重复对照见 [实验记录](results.md) 第 38 节。flex 与 Claude 的 canvas 复验分别保留自己的目标、模型设置和费用上限。

绘图的鼠标诊断固定笔宽、起点和一个三单位水平拖动，比较任务 9 引入最小线长前后的已保存页面。预登记判据要求十八单位长拖对齐起点与终点。一个事后敏感性检查仅核对位移，因为个别页面把两个端点整体平移，两种结果分别呈现。[短拖动协议](../studies/webbench/draw/pointer_transition/PROTOCOL.md)

## 4. 费用、失败与复现

Web-Bench 作者估计资深工程师完成一个完整基准项目平均需要 4–8 小时。该数字的单位是整项目开发；本文的组件抽取、接口设计和绑定没有可追溯的历史人时，只报告本轮确实计时的准备工作。[Web-Bench 原文](https://arxiv.org/abs/2505.07473)

费用分成一次建库与后续各目标生成/修复。公开说明复用次数，包含失败建库与未知传输预留，不能只展示短 JSON 的生成费。绘图单库建库回执分别为 GPT-5 约 $0.185241、Claude 约 $0.152952；对廉价生成模型，这笔固定成本可能高于从零生成本身。不能从一次强模型实验推断所有模型都省钱。

匹配实验还单列无库组准备笔记的实际费用。每一重复的分母为五个预定目标位置，建库失败使该次重复的五个位置都判为流程失败。传输或预算缺失保留为空，只在两边都可观察的位置比较通过数。

在四套 32k 游戏库上，一次只替换一个顶层字段，在三个受控种子中都能改变按 d 后 96 毫秒的额外位移。对应的固定示例页面也与逐目标选择达到相同通过数。两项测量分别检验行为可控性与在这些任务上选择方案的价值。

构建通过加载不代表库足够。draw 的 GPT-5 库只有主题与字号选择，162 种合法配置的交互脚本字节不变；这不构成通用的行为组合证据。

当前 [主比较视图](../studies/results/end_to_end.json) 可用 `uv run python -m studies.end_to_end --check` 重算，含源哈希、真实记录路径、分组、当前任务成绩和费用。它是新增报告视图，不覆盖原始 JSON。历史 `free_lib` 消融仍保存真实方法名、源码与分数，只退出当前论文和展示。完整旧结果见 [results.md](results.md)，公开产物边界见 [reproducibility.md](reproducibility.md)。


## AI 库的改进实验

11 月 25 日的复测纳入原主表 18 个准备失败格和 7 个实测零通过格。每格独立登记两份库，共用真实的同模型对照。Web-Bench 的公开需求指定模块名，模型决定布尔配置并实现模块。默认配置和首例都须实际通过一个公开操作。某次重复交付失败时，该重复才尝试用一份 ES 模块实现完整入口；采用顺序由公开准备检查决定。TodoMVC 只暴露能稳定改变公开状态的开关。Duo 逐个写组件，使用公开单功能检查，只在可部署的领域比较两边相同的目标。首份库的实测零通过保留为 0/x，第二份独立结果和固定首例逐项存档。第一版 Web-Bench 文件名接收器的故障及费用另行记录。[协议、实现和结果](../studies/webbench/self_build_modules/README.md) · [TodoMVC 与 Duo 协议](../studies/public_library_transfer/self_refinement/suite_recovery/PROTOCOL.md)

参考库提供了几种可复用的设计。表格的多个输入处理器共享选区和编辑状态，图表按公开数据的类型绑定渲染类，表单把可用题型和构造参数写进接口。研究者将这些规律写成通用建库指令。新建库会话只接触协议登记的公开需求、起始工程、配置接口和示例。各参考库的来源与可迁移的设计见[逐项目分析](library-preparation-design.md)。

表格兼容重建固定公开配置模式和编译器，由同一建库模型各自独立运行普通提示两次、共享状态与事件优先级提示两次。两批历史 Mistral 响应逐条交给每个后端。另给本地 Qwen 每个目标一份全新、仅含公开接口的提示，并以第一份固定示例作为单独对照。SVG 的部署回退只在响应不可用时采用建库者预先提供的首例，评分成功后才知道它的行为覆盖度。原方案成绩、带回退的流程成绩和固定页成绩分别记录。[表格建库协议](../studies/webbench/table/compatible_rebuild/PROTOCOL.md) · [新表格规划协议](../studies/webbench/table/local_planning/PROTOCOL.md) · [图表部署规则](../studies/webbench/svg_chart/interface_refinement/RECOVERY.md)

表格还做了不继承旧接口的端到端复验。两次建库各自从公开需求和起始工程命名行为开关、撰写模块和指定可用首例。通用编译器提供闭合布尔配置，模型自由决定具体语义。每库各自取得 20 份全新的 Qwen 首轮方案。另行冻结的解码器按同一份方案模式输出键名和括号，由规划模型在每个合法值之间选择。既有库的嵌套对象和枚举也用同一算法，便于辨别语法合法与行为正确的差别。[独立自主建库](../studies/webbench/table/controller_build/PROTOCOL.md) · [受约束规划](../studies/webbench/table/schema_decoding/PROTOCOL.md)

Duo 的新协议让模型一次只写一个组件，在该功能原有的两条公共断言上检查；从零候选可以用两个公开功能各自的断言修复一次。TodoMVC 让模型写完整控制器、命名布尔配置，在同一公开操作下逐一翻转并重复两次，实测到差异的键才交给同模型规划。两者都独立建库两次，共用同目标的从零样本，另测固定部署。实际被选择的页面按文件散列与固定页比较。[Duo 协议](../studies/public_library_transfer/self_refinement/duo_components/PROTOCOL.md) · [TodoMVC 协议](../studies/public_library_transfer/self_refinement/todomvc/verified_controller/PROTOCOL.md)

问卷组从公开规范固定基类、八个题型和应用入口，子类读取同一库实际交付的基类；从零生成器也可读取和调用相同的组装器，含构造参数、挂载、按钮以及写入存储的胶水。SVG 组先生成共用基类，再按依赖生成六种渲染类，研究者提供从公开类型到类的挂载。运行时分别对照原提交、源文件依赖链接、模型根据公开浏览器异常修复及 DOM 类名接口诊断。相同的源代码接收与公开接口修复也适用于各自从零页面。[问卷协议](../studies/public_library_transfer/self_refinement/form_components/PROTOCOL.md) · [SVG 协议与分阶段改动](../studies/public_library_transfer/self_refinement/svg_renderers/README.md)

图表确认组在模型生成前固定依赖链接和 DOM 类名适配，重新付费独立抽取两个库及二十份逐库方案。两份库共用先前已恢复代码交付的二十份真实从零页面；按目标核对响应、页面和官方回执。结果 6/20、6/20 对 5/20，固定全开在每个库上逐题同分。[新库与对照溯源](../studies/public_library_transfer/self_refinement/svg_renderers/confirmation/result.json)

## 公开动作与跨组合代码来源

表格库分别执行单击、菜单和增行，再把选区集合及其页面样式放在同一次真实交互中检查。研究者提供通用集合到 CSS 类的绑定，模型写操作函数并声明集合、选择器及类名。只有实际动作通过且保留此前动作的扩展才交给规划器。按库报告全开页与无操作宿主。TodoMVC 同时保留解析失败的原回复、按唯一语法树恢复的函数、编号选择与固定全开页。

WebApp1K-Duo 的 GPT-5 列来自作者发布的模型代码。排除十个目标组合后，以事先固定的哈希顺序选择其他组合的完整模块。组件可能附带第二项行为，也可能缺少所需功能。使用实际 GPT-5 来源并记录外部生成费用未披露。独立回调实验中，模型写状态钩子与视图，Direct 针对每对功能写完整页面，两个流程均可见构成它们的公开单功能材料。[OneKQ 数据快照](https://huggingface.co/datasets/onekq-ai/WebApp1K-Duo-React-Generations/tree/fbda49ea521d9ddd22d2425d01237e17e3d6831c) · [来源与接收规则](../studies/public_library_transfer/duo_donor_library/PROTOCOL.md) · [回调实验](../studies/public_library_transfer/duo_react_callbacks/PROTOCOL.md)

文件管理器接收完整 HTML 入口，再实测模型编写的可选扩展。早期计算器实验保留官方起始页自带的基础算术，人工来源取上游参考实现，Self 的 HTML 和键组声明由同一个模型独立生成。两种来源分别测逐题选择、可选键全开和全部关闭；另存原始起始页。问卷的命名导入只在公共页面出现未定义标识符、同库存在唯一导出时添加。SVG 将新标签和新数组传给原渲染器，分别打开和关闭轴、图例和点，检查原有公开能力是否因修改退化。[文件管理器](../studies/webbench/file_explorer/document_library/PROTOCOL.md) · [计算器](../studies/webbench/calculator/key_groups/PROTOCOL.md) · [问卷](../studies/webbench/form/survey_workflow/module_links/PROTOCOL.md) · [SVG](../studies/webbench/typed_components/svg_public_geometry/decoration/PROTOCOL.md)

在控制器已经封存时，还可单独改变部署决策。模型必须为要关闭的选项提交公开需求原文；编译器核对引用是否存在及是否含否定措辞。没有依据的改动保留默认，有效空列表与无法解析的输出分开统计。另写的一对相反需求直接检查同一条待办是否实际翻转。这两项和八个基准任务分别计数。[有依据的禁用决策](../studies/public_library_transfer/compact_todomvc/state_examples/EVIDENCE.md)

WebGen-Bench 完整 HTML 接收失败的两份从零站点另有浏览器原生解析复验。对同站两次交付都审计结束原因，只把首份文档从起始标签原样交给浏览器。此比较发生在看到交付失败之后，按原站点分别报告。表格的选择状态复验则逐页重编原配置、核对原文件指纹后才换模型生成的四个函数，并保留固定全开对照。[HTML 接收协议](../studies/webgen_bench/heldout_transfer/incomplete_html/PROTOCOL.md) · [表格选择状态](../studies/webbench/table/action_sequences/selection_mode/PROTOCOL.md)
