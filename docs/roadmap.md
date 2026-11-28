# 研究任务清单

论文比较人工库、从公开需求建立的 AI 库与同协议的从零生成。主表按模型和共同目标报告。WebGen-Bench 的主表使用九个新网站、统一的人工 SDK 导航模板和完整通过数。[11 月 28 日诊断与结果](results.md#webgen-site-completion)

## 1. 主表优先事项

**将库来源和部署失败分开。** 表中 GPT-5 指建库者，行名是负责选配置的目标模型。Flash 问卷的最初两次请求都没交付源码；按文件验收的首库过 8/20，同解码复测为 11/20。冻结 GPT-5 代码后，Qwen3.5 图表从 1/20 到 15/20，固定示例是 17/20。Qwen 的同一份自建待办库有 32 种合法配置，仅 4 种满足所有任务共有的新增、去空、保存和恢复。逐题选择这四种配置由 0/8 恢复至 5/8，固定首例也为 5/8。后续先查未编译份数、枚举或抽查固定页覆盖，再决定改接口还是改函数。[全部低于 Self 的原格子及原因](../studies/results/library-source-diagnosis-20261126.json)

- [ ] **Duo 下一次换未用过的业务域。** 原题六行已补 Human，两个 AI 库在五行超过 Direct，Flash 原十题三者均为 9/10。新抽十题首次 Direct、GPT-5、Self 为 6/10、10/10、7/10，统一路由后为 7/10、10/10、8/10。每个官方导入入口均已执行四例。下一次在抽样前冻结这套接口与路由版本，给 Direct 和库相同的公开组件规格、修复机会和版本信息。另记独立通过但合并后失败的组件对，逐题保留首次结果与固定配置。原十题的性能报告请求计数冲突已复现，继续保留原判决与分母。[四种来源与独立组合](results.md#duo-verified-features)
- [ ] **优先复验 AI 库能否同时超过 Direct 和固定页。** 表格的 GPT-5 自查文件与入口修复已经做过四种组合。下一次把同一套事件观察和首库准入规则预登记到另一款尚未用来调试的编辑器，逐项列出只在逐题配置通过和只在固定页通过的任务。Mistral 关闭重复选格监听器后达到了公开准入。Qwen3-Coder 与 GPT-OSS 的新表格库仍未准入。下一轮先记录错误栈中首个模型文件和函数，核对原监听器是否已完成该操作，再把相同规则用到新编辑器。计算器 Qwen 在五项记忆操作上全过，正式结果仍为 2/20。下一份独立需求先明确每次存入、扣减、召回之后显示框和寄存器各应怎样变化，再用新数字检验。Gemma 三份记忆实现都把追加数字写成了数值相加，先在其余应用验证模型能否区分这两种状态变化。未交付的 GPT-5 计算器待该模型在本地区恢复可用后按原接口补建。[本轮重建、同题对照和未解决项](results.md#ai-library-rebuilds)
- [ ] **先让 Self 的跨视图状态变化可验收。** 建库时要求同一条公开动作给出状态变化前值和后值，再切换视图读回。检查真实改变的样例、保持原值的惰性按钮，以及所有一级标签能否进入评判视口。优先从当前低分格检查这三个条件，确认缺的是实现、计划还是入口以后，只改对应部分。下一轮在未见站点封存原库、改后库和同题 Direct，同时报告失分，保留缺判交集。[完整通过数与逐项判决](../studies/webgen_bench/site_completion/README.md)
- [ ] **表格补查反向 Tab。** 第二份 Qwen 库改为仅计算目标行列后，两次均能完成新的双向箭头序列。两个实现都会先进入普通 Tab 分支，反向 Tab 到不了上一格。下一次在不同的表格尺寸上先验证同一位置的正向与反向 Tab，再测试同行和跨行两端，并保留固定不移动的对照。[真实行列接口与函数回复](../studies/webbench/table/coordinate_navigation/documented_reception/PROTOCOL.md)
- [ ] **待办核对首库在空筛选下的页脚。** 路由修复后，Ministral 两份自建库在八题上分别过 6、8 项，主表保留第一份。首库剩余两题均在当前筛选链接的选中状态出错。下一次用没有可见事项但仍有已保存事项的公开页面，分别检查页脚、选中链接和返回后的事项身份。Gemma 首库的五项失分另行定位。[冻结开关](../studies/public_library_transfer/compact_todomvc/edit_choices/PROTOCOL.md) · [路由与视图交叉复算](../studies/public_library_transfer/compact_todomvc/route_preservation/interaction/PROTOCOL.md)
- [ ] **复核 WebGen-Bench 原判官。** 本轮已拿到 GPT-5 建库代码并通过五项公开检查。作者指定的 32B 评判器仍返回 404。该型号可用后，在相同页面复查正负校准和同题判决，保留与当前视觉判官的差异。[九站实验](../studies/webgen_bench/site_completion/PROTOCOL.md)

主表只收通过公开建库检查的库。零表示已经观测且零通过；空白表示准备失败，横线表示缺测。每行方法用同一批目标。补传旧请求保留原未知费用，恢复目标另列；开发格上的改进与独立基准的成绩分别报告。表格与计算器的最新建库、逐题配置、固定页和费用见[第 59 节](results.md#ai-library-rebuilds)。此前独立重复见[第 53 节](results.md#53-检查可见状态与库的实际能力)。

## 2. 补充实验

- [ ] **用独立需求验证整页问卷检查。** 三个模型已用同一份逐题语义配置连接各个库，并实测创建题目、保存和重载。Gemma 和 Mistral 的目录类漏导入，仅在公开异常指向唯一已有导出时接线。下一次预登记新的题型组合及不同的导出顺序，用同一任务比较从零、人工库、GPT-5、Self 与固定页，并记录哪些功能只在切换方案后通过。[整页协议](../studies/webbench/form/survey_workflow/PROTOCOL.md) · [连接条件](../studies/webbench/form/survey_workflow/module_links/PROTOCOL.md)
- [ ] **小模型 TodoMVC 的固定与逐题选择。** Llama 已补完全部分槽选择。接下来记录哪些任务只在固定全开或逐题选择时通过，以及增加的选择次数。
- [ ] **验证强建库者的迁移。** 计算器已有 0.5B 领域辅助诊断，固定按键顺序可复现两份库的成绩，单用数学绑定器已过 6/20。独立强模型建库须保留这一对照。 表格的两份 GPT-6 Astra 库用同一 Qwen 原生配置，各通过 13/20，同时固定首例也各通过 13/20。文件管理器已经用 Qwen3.5 和 Flash 在 20 个共同目标上验证两份库，Qwen 逐题分别 15/20、12/20，固定页分别 15/20、11/20。文件管理器和计算器均已加入同目标对照。后续用未参与调试的项目检验强库相对固定页新增哪些通过题。[强库复测](../studies/public_library_transfer/strong_builder/native/result.json)
- [ ] **补当前缺测的常用模型。** 11 月 26 日重传原任务的 Gemini 2.5 Flash、GPT-5 mini、Haiku 4.5 和 Sonnet 4.5 均再次返回 403；同日 GPT-5 的真实表格建库请求也返回 403。[四个模型的回执](../studies/webbench/backbone_matrix/route_completion/result.json) 当相应型号的服务可用时，另登记表格和 SVG 的完整 20 项。Qwen3-Coder-30B 原表格人工库有 13/20 个请求无返回，本轮在独立账本补传，原七个共同目标的结果单独保存。历史 TodoMVC、文件管理器数据在各自协议下单列。
- [ ] **扩展完整项目。** 文件管理器和计算器已登记 Gemma、Qwen3.5、GPT-OSS、Flash 四款模型。下一项目先做 BOM，追溯人工组件和绑定来源，在同一生成模型上登记全部当前目标与四种方法。随后按同一条件补表达式编辑器。[计算器四模型与额外部署复验协议](../studies/webbench/calculator/compiler_fallback/PROTOCOL.md)

- [ ] 在已有问卷、表格等零分诊断之外，继续复查全部历史 AI 库来源。SVG 已补三个模型的公开几何与绘制后修饰检查。GPT-OSS 的逐题结果从 4/20 到 7/20；Mistral 的公开检查从 52 到 58，官方结果从 5/19 降到 3/19。下一步冻结新图形、输入数据和标签的检查，在独立项目中验证公开通过数能否预测实际行为。Qwen3-Coder 的两次新 SVG 库均为 6/20，真实从零为 5/20，固定全开也是 6/20。[SVG 前瞻确认](../studies/public_library_transfer/self_refinement/svg_renderers/confirmation/result.json)

### 原模型复测与泛化

此前十个 Web-Bench 项目及 TodoMVC、WebApp1K-Duo 已有复测。历史 60 个组或终点中，44 个取得同名部署模型在调整库来源后的有效配置；原身份与原协议严格复现仍为 0。[本轮结论](results.md#public-library-transfer) · [表格全部配置](../studies/results/public-library-transfer-table-space-20261123.json)

- [ ] **恢复可用的原建库模型后，先补 GPT-5、Claude Sonnet 4.5。** 11 月 23 日对十项 Web-Bench 分别请求两种原模型的库，20 笔均返回 HTTP 403，保留未决预留与缺失标记。以历史组索引为清单，同名项目的旧样本数、建库所见需求、部署模型、token 上限和复用的直接对照逐项核对；canvas 按 16k/32k、独立重复和模型分开，flex 保留五个里程碑，编辑器保留准备窗口和笔记对照。TodoMVC 原四个部署模型每项有两次采样，Duo 使用其各自模型与两个域。每套新库保留首例，记录费用与失效原因。[逐原组复测状态](../studies/results/public-library-transfer-retest-crosswalk-20261123.json) · [旧组及共用对照](../studies/results/public-library-transfer-history-20261123.json)
- [ ] **建库格式先给模型可执行的反馈。** 11 月 24 日的 Web-Bench 接口已支持两种等价布尔表示。下一版把非法字段、允许值及锚点在公开 HTML 中的匹配次数写入纠错消息。冻结提示后再各采一次，比较首轮准入、一次修复后的准入及通过题数；本轮原始拒绝和事后的等价解析仍各自保留。[原始协议](../studies/public_library_transfer/deployments/open_weights/PROTOCOL.md) · [等价域诊断](../studies/public_library_transfer/diagnostics/boolean_domains/PROTOCOL.md)
- [ ] 泛化验证优先使用此前未用于调提示的独立应用族，预登记建库者可见的公开材料；对同模型、同目标同时保存逐题方案、固定示例、从零代码，报告双方各自独有的通过项。当前闭集装配支持布尔值和有限枚举。连续几何参数、数组和复杂数据结构须各有可执行基线及合法范围。[跨项目协议及代码](../studies/public_library_transfer/README.md)

### Web-Bench 尚待覆盖的项目

分母来自 ByteDance 论文附录 A 表 5–7。已把冻结快照逐目录对齐，50 个正式项目各有 20 个当前任务文件，共 1,000 个项目－目标位置。ChartBuilder 对应目录 `chart`；额外目录 `demo`、`project-template`、`pull-loading` 不在论文 50 项清单中。TodoMVC 单列。重复生成、不同建库者、校准和空白页都不增加目标覆盖数。[官方项目清单](https://arxiv.org/html/2505.07473v1#A1) · [冻结快照](https://github.com/bytedance/web-bench/tree/7b31ca2b786eef120dd49ce63dd03d0c0006046d/projects)

原协议中，人工组件覆盖 **5/50 个项目、89/1,000 个目标**，AI 库为 **9/50 个项目、135/1,000 个目标**。11 月 23 日两套独立订阅库各在十个项目的全部二十个当前目标上交付了方案，AI 库已有输出的并集增至 **10/50 个项目、200/1,000 个目标**。下表保留 11 月 23 日按目标去重的快照。此后计算器已在全部 20 项补齐人工库，BOM 仍缺人工来源。[本轮覆盖及预算](../studies/results/public-library-transfer-overview-20261123.json) [逐项目目标与计数依据](../studies/results/webbench-coverage-20261123.json)

| 项目 | 人工库目标数 | AI 库目标数 | 待补工作 |
|---|---:|---:|---|
| dom1、form | 各 20 | 各 20 | 保留需求与生成合同不同的历史比较 |
| table、svg-chart | 各 20 | 各 20 | 复验文档与固定配置的影响能否跨模型重现 |
| calculator、bom | 各 0 | 各 20 | 计算器人工库后来已补齐，BOM 仍待追溯 |
| draw、canvas、flex | 各 0 | 各 20 | 补人工库，原里程碑另列 |
| expression-editor | 9 | 20 | 补人工库未观测的 11 项，分别复查准备窗口 |
| 其余 40 个正式项目 | 0 | 0 | 见下表其余目录，先校准再生成 |

| 官方类别 | 数量 | 项目目录（同族变体仍按官方项目计） |
|---|---:|---|
| 浏览器标准及图形 | 19 | table、flex、grid、float、color、selector、bom、dom、dom1、form、esmodule、canvas、svg、svg-solar、svg-chart、typescript、survey、draw、chart |
| UI 框架 | 6 | react、vue、angular、svelte、threejs、react-no-ts |
| CSS 框架 | 6 | tailwind、unocss、styled-components、less、sass、stylus |
| 全栈 | 5 | nextjs、nuxt、expressjs、fastify、fastify-react |
| 数据存储 | 4 | sequelize、nosql、lowdb、prisma |
| 构建工具 | 3 | vite、webpack、parcel |
| 状态管理 | 4 | redux、jotai、mobx、zustand |
| 其他 | 3 | calculator、calculator-files、expression-editor |

- [ ] 优先扩展有明确组件来源的独立应用族。逐项记清初始工程自带的组件、从最终参考源码取得的组件、研究者另写的绑定逻辑。每次固定目标、生成器与无库基线，先在同一项目内报告两种库来源。
- [ ] draw、canvas、flex 已触及的 5 个里程碑不能代替全部 20 个任务。补测余下 15 项前先固定方法与运行合同，保留旧协议的原分母。
- [ ] 框架与后端按运行环境安排；先验证构建、官方参考页、空白或失效对照与数据重置，再接入双库实验。相同任务设计的技术栈变体不计作独立应用族重复。

### 规划能力、成本与断言

- [ ] **P1 扩大应用与模型覆盖。** React 博客的 20 个官方文件均已接受参考页、拒绝起始页和空白页。下一步登记全部目标、人工组件与绑定来源、两组准备的信息与额度，再运行无库、人工库、AI 库三组。用第二个目标生成模型复验。相同需求的 Vue 等框架变体不计作独立应用族。[React 校准记录](../studies/results/react-blog-calibration-20261123.json)
- [ ] **P2 检验规划器能否按目标切换互斥操作。** 图表 AI 库可覆盖两端，现有模型页各只命中一端；绘图短拖的 162 种设置都固定为后期最小线长。下一步优先寻找有两种经验证可选状态转移的库，在新生成前冻结相同按键或拖动、两端要求和固定页对照，检验实际方案能否两端都命中。[绘图回放](../studies/results/draw-pointer-transition-20261123.json)
- [ ] **P3 人工准备与维护成本。** 三个 20 目标序列的准备、部署和修复支出已逐项核对。下一批请独立开发者前瞻计时组件选择、绑定与维护，分别记录首次准备和需求变更的实际人时；现有代理墙钟不能换算为人工工时。
- [ ] **P4 扩展剩余断言审查。** 已有 BOM、canvas、flex 和图表公共数据对照。优先检查参考界面可做但旧候选普遍失败的行为。用已知具体缺陷和空操作对照验证判据的区分能力，维持原断言和原分数。

已审阅指定的 LaTCoder 及五篇交互生成研究，并据此改写引言。[逐篇笔记与原文出处](related-work-notes.md)

## 3. 会议后续与作者审阅

- [ ] 在 Overleaf 审阅本地主稿、流程图与多模型总表，确认人工库来源、占位符和逐模型分层在双栏排版中清楚可读。
- [ ] 多端适配若纳入后续研究，先定义同一交互在桌面与窄屏的配对断言，以及修复一端后另一端发生回归的判据。

## 4. 论文与公开交付

- [ ] **R1 作者审核。** 复核论文结论、引用、署名与 AI 使用披露，确定匿名审稿链接。
- [ ] **R2 跨机器复验。** 当前报告包已在本机另行解包复算；在干净机器上重新安装锁定依赖、验证两个入口并重跑浏览器抽样，登记环境与差异。
- [ ] **R3 公开材料授权。** 审核仓库自身许可证、上游及生成资产分发边界，确定原始产物可获取范围与匿名托管方式。保留旧路径兼容和冻结证据。

执行新实验前查看 [操作规则](../AGENTS.md)，先冻结协议与输入，再生成、评分并记录全部失败和费用。已关闭的实验不续跑。
