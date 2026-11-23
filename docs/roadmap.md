# 研究任务清单

论文以人工行为库＋GUI-DNA 为主，AI 从公开需求建库＋GUI-DNA 检验缺少现成实现时能否复用，两者均对照同研究的无库生成。

## 0.1 首要任务：补齐历史 AI 建库的原模型条件

本轮已覆盖此前十个 Web-Bench 项目及 TodoMVC、WebApp1K-Duo。表格由同一 Mistral 部署时，两次新建库分别通过 18/20、19/20，本轮从零为 3/20；两套库各有一个固定配置能覆盖实际逐题规划通过的全部目标。原 60 个组或终点中，有 44 个取得同名部署模型在调整来源后的有效配置，原身份与原协议严格复现仍为 0。[本轮结论](results.md#public-library-transfer) · [全部配置验证](../studies/results/public-library-transfer-table-space-20261123.json)

- [ ] **恢复可用的原建库模型后，先补 GPT-5、Claude Sonnet 4.5。** 本次对十项 Web-Bench 各请求一套两种原模型的库，20 笔均返回 HTTP 403，保留未决预留与缺失标记。以历史组索引为清单，同名项目的旧样本数、建库所见需求、部署模型、token 上限和复用的直接对照逐项核对；canvas 按 16k/32k、独立重复和模型分开，flex 保留五个里程碑，编辑器保留准备窗口和笔记对照。TodoMVC 原四个部署模型每项有两次采样，Duo 使用其各自模型与两个域。每套新库保留首例，记录费用与失效原因。[逐原组复测状态](../studies/results/public-library-transfer-retest-crosswalk-20261123.json) · [旧组及共用对照](../studies/results/public-library-transfer-history-20261123.json)
- [ ] **建库格式先给模型可执行的反馈。** 在下一版接口里直接支持布尔域的两种等价表示，把非法字段、允许值及锚点在公开 HTML 中的匹配次数写入纠错消息。冻结提示后再各采一次，比较首轮准入、一次修复后的准入及通过题数；本轮原始拒绝和事后的等价解析仍各自保留。[原始协议](../studies/public_library_transfer/deployments/open_weights/PROTOCOL.md) · [等价域诊断](../studies/public_library_transfer/diagnostics/boolean_domains/PROTOCOL.md)
- [ ] 泛化验证优先使用此前未用于调提示的独立应用族，预登记建库者可见的公开材料；对同模型、同目标同时保存逐题方案、固定示例、从零代码，报告双方各自独有的通过项。当前闭集装配支持布尔值和有限枚举。连续几何参数、数组和复杂数据结构须各有可执行基线及合法范围。[跨项目协议及代码](../studies/public_library_transfer/README.md)

## Web-Bench 尚待覆盖的项目

分母来自 ByteDance 论文附录 A 表 5–7。已把冻结快照逐目录对齐，50 个正式项目各有 20 个当前任务文件，共 1,000 个项目－目标位置。ChartBuilder 对应目录 `chart`；额外目录 `demo`、`project-template`、`pull-loading` 不在论文 50 项清单中。TodoMVC 单列。重复生成、不同建库者、校准和空白页都不增加目标覆盖数。[官方项目清单](https://arxiv.org/html/2505.07473v1#A1) · [冻结快照](https://github.com/bytedance/web-bench/tree/7b31ca2b786eef120dd49ce63dd03d0c0006046d/projects)

原协议中，人工组件覆盖 **5/50 个项目、89/1,000 个目标**，AI 库为 **9/50 个项目、135/1,000 个目标**。本轮两套独立订阅库各在十个项目的全部二十个当前目标上交付了方案，AI 库已有输出的并集增至 **10/50 个项目、200/1,000 个目标**。以下按目标去重，覆盖表示取得输出。[本轮覆盖及预算](../studies/results/public-library-transfer-overview-20261123.json) [逐项目目标与计数依据](../studies/results/webbench-coverage-20261123.json)

| 项目 | 人工库目标数 | AI 库目标数 | 待补工作 |
|---|---:|---:|---|
| dom1、form | 各 20 | 各 20 | 保留需求与生成合同不同的历史比较 |
| table、svg-chart | 各 20 | 各 20 | 复验文档与固定配置的影响能否跨模型重现 |
| calculator、bom | 各 0 | 各 20 | 追溯人工组件与绑定来源 |
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

## 0. 仍决定论文结论的实验

- [ ] **P1 扩大应用与模型覆盖。** React 博客的 20 个官方文件均已接受参考页、拒绝起始页和空白页。下一步登记全部目标、人工组件与绑定来源、两组准备的信息与额度，再运行无库、人工库、AI 库三组。用第二个目标生成模型复验。相同需求的 Vue 等框架变体不计作独立应用族。[React 校准记录](../studies/results/react-blog-calibration-20261123.json)
- [ ] **P2 检验规划器能否按目标切换互斥操作。** 图表 AI 库可覆盖两端，现有模型页各只命中一端；绘图短拖的 162 种设置都固定为后期最小线长。下一步优先寻找有两种经验证可选状态转移的库，在新生成前冻结相同按键或拖动、两端要求和固定页对照，检验实际方案能否两端都命中。[绘图回放](../studies/results/draw-pointer-transition-20261123.json)
- [ ] **P3 人工准备与维护成本。** 三个 20 目标序列的准备、部署和修复支出已逐项核对。下一批请独立开发者前瞻计时组件选择、绑定与维护，分别记录首次准备和需求变更的实际人时；现有代理墙钟不能换算为人工工时。
- [ ] **P4 扩展剩余断言审查。** 已有 BOM、canvas、flex 和图表公共数据对照。优先检查参考界面可做但旧候选普遍失败的行为。用已知具体缺陷和空操作对照验证判据的区分能力，维持原断言和原分数。

已审阅指定的 LaTCoder 及五篇交互生成研究，并据此改写引言。[逐篇笔记与原文出处](related-work-notes.md)

## 1. 会议后续与作者审阅

- [ ] 在 Overleaf 审阅本地主稿、流程图与三方法结果表，确认人工库来源、占位符和逐模型分层在双栏排版中清楚可读。
- [ ] 多端适配若纳入后续研究，先定义同一交互在桌面与窄屏的配对断言，以及修复一端后另一端发生回归的判据。

## 2. 论文与公开交付

- [ ] **R1 作者审核。** 复核论文结论、引用、署名与 AI 使用披露，确定匿名审稿链接。
- [ ] **R2 跨机器复验。** 当前报告包已在本机另行解包复算；在干净机器上重新安装锁定依赖、验证两个入口并重跑浏览器抽样，登记环境与差异。
- [ ] **R3 公开材料授权。** 审核仓库自身许可证、上游及生成资产分发边界，确定原始产物可获取范围与匿名托管方式。保留旧路径兼容和冻结证据。

执行新实验前查看 [操作规则](../AGENTS.md)，先冻结协议与输入，再生成、评分并记录全部失败和费用。已关闭的实验不续跑。
