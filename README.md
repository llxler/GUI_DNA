# GUI-DNA: Building and Reusing Behavior Libraries for GUI Generation

GUI-DNA 把「点击后怎样改变应用状态」写进可复用的行为库，让模型为每个目标生成配置。例如，文件管理器里的「新建」按钮既可能在选中目录下插入条目，也可能在选中文件旁插入条目。论文分别研究开发者准备的组件，以及模型从公开需求和起始工程独立构建的行为库。两种流程都与同协议的无库代码生成比较。[方法说明](docs/method.md)

## 目录与阅读入口

| 路径 | 用途 |
| --- | --- |
| [studies/](studies/README.md) | 论文研究、基准协议、运行器与结果。两个研究入口分别是[公开需求建库与迁移](studies/public_library_transfer/README.md)和 [Web-Bench 项目研究](studies/webbench/README.md)。 |
| [tests/](tests/README.md) | 工程回归测试，使用 `pytest` 运行。 |
| `test/` → `studies/` | 为兼容旧导入与冻结清单而保留的链接。论文研究从 `studies/` 进入。 |
| [experiments/](experiments/README.md) | 早期冻结原型及历史运行器，保留原实验环境与记录。 |
| [src/gui_dna/](src/gui_dna) | GUI-DNA 的核心运行时、编译器和预算账本。 |
| [docs/](docs) | [方法](docs/method.md)、[实验结果](docs/results.md)、[复现说明](docs/reproducibility.md)和[研究计划](docs/roadmap.md)。 |

## 论文结果

Table 1 的 A 区列出表格编辑器、SVG 图表、问卷、文件管理器与计算器；B 区并列 TodoMVC 子集和 WebApp1K-Duo 功能对。各行用相同目标比较 Direct、Human、GPT-5 和 Self。C 区单列 WebGen-Bench 六个网站的 43 项功能操作。使用替代视觉评判器，完整和部分完成分别计 1 和 0.5 分。人工库让 Gemma 从 13 分升到 19 分，Qwen3.5 从 11.5 分升到 24.5 分；Flash 从零生成 35.5 分，人工库 21 分，自建库 29 分。未获回执记横线，建库失败留空；通过建库检查并实测零通过的格子保留 0/x。[逐模型主表](studies/results/paper-performance-matrix.json) · [六站样本、评判与费用](studies/webgen_bench/README.md)

**低分原因。** 在原 20 个 SVG 目标上，Gemma 配置同一套 GPT-5 库，改为返回编号后从 0/20 到 15/20，固定首例为 17/20。它自己的冻结库用相同方法只从 0/20 到 2/20。进一步按父子类构建渲染器后，DeepSeek Flash 的 Self 在原 20 个目标上从 1/20 到 7/20，固定全开也是 7/20。三个 3B 至 4B 模型均在得分前登记；原从零满分的三款模型另保留完整记录。[逐格原题诊断与费用](studies/results/component-followup-20261125.json) · [小模型](studies/public_library_transfer/compact_todomvc/PROTOCOL.md)

Qwen3.5-9B 已能在表格内部维护选区，却漏掉了选中样式。让模型声明如何把集合映射到 CSS 后，两份开发库分别通过 3/20、4/20，各自的固定页通过同样的任务。移除模型写的操作函数后，两个宿主都为 0/20。从头换两个种子，首库只交付 14/15 个操作；另一库通过准入，逐题和固定页均为 3/20。[选区绑定与逐题回执](studies/webbench/table/selection_binding/typed-result.json)

**人工准备的行为库。** 在原始七模型协议中，表格、SVG 和问卷三个项目各有 6/7 个模型的人工库组装通过数高于本模型从零生成。在同一批 20 项表格任务上，GPT-OSS-120B 从零通过 7 项，组装参考组件通过 20 项。旧自建库所有配置实测均为零，新建的两份库分别通过 7 项和 4 项，各自固定首例通过相同题目。早期文件管理器实验中，参考组件组装为 126/140，逐步编辑前一页为 52/140。[组件来源与评测协议](docs/method.md)

**从公开需求建库。** DeepSeek V4 Flash 在 TodoMVC 的从零代码为 2/8，自建库组装为 8/8。固定复用建库时的首例同样为 8/8。在 Duo 的十个双功能组合上，早期逐个生成组件时，两份 Flash 自建库分别为 4/10、3/10，同设置从零为 6/10。改为分别生成状态回调与视图后，两份自建库各过 6/10，同设置从零过 9/10，两个固定组件对均为 0/10。另从作者发布的其他 GPT-5 组合中取得 11/15 个所需功能；按功能名装配通过 4/10，固定组件对通过 2/10。每个实验分别报告哪份实现能工作，以及逐题更改配置增加了哪些通过项。[多模型实验](studies/webbench/backbone_matrix/README.md) · [完整记录](docs/results.md)

在第一轮完整项目比较中，生成器、方法和目标逐行配对。计算器的 Qwen3.5 从零、人工库、GPT-5 库、自建首库分别为 4/20、20/20、10/20、6/20，Flash 分别为 10/20、16/20、10/20、6/20。文件管理器两模型的自建首库均过 2/20，Flash 的第二份自建库过 8/20，固定页也过相同的题。Llama 的 TodoMVC 改为逐个选择事件和视图后，四组各为 0/8、1/8、8/8、1/8。[逐格复核、独立库与费用](studies/results/library-capabilities-20261126.json)

**Flash 问卷自建库。** 原两次建库耗尽输出而没有源码。文件级公开验收得到两份可部署的库，原部署分别过 8/20、14/20。保持这两份库与全部任务不变，在所有方法同时关闭额外推理后，Self 分别过 11/20、16/20，两份固定页也分别过相同的题。从零过 10/20，人工库过 20/20。相同解码下，GPT-5 库沿用原混合提示过 0/20，迁移已有问卷配置提示后过 12/20。[原始协议](studies/webbench/form/flash_self_build/transport_completion/result.json) · [同解码复验](studies/webbench/form/flash_self_build/visible_targets/result.json) · [配置提示迁移](studies/webbench/form/flash_self_build/visible_targets/schema-transfer-result.json)

在另一项 Web-Bench 独立建库中，Qwen3-Coder 的两份 SVG 库在补全同库父类导入和浏览器类名接口后通过 **7/20、5/20**，同样接受可交付源码的从零通过 **5/20**；固定全开页在两库逐题同分。把这两项修复提前固定，再让模型生成两套全新的库，两次均为 **6/20**，同一份冻结的从零对照为 **5/20**；各自固定全开也为 6/20。[前瞻确认](studies/public_library_transfer/self_refinement/svg_renderers/confirmation/result.json)

GPT-OSS 的问卷库各覆盖九种独立控件，但整页分别通过 **5/20、6/20**，对称修复输出空白后的从零为 **12/20**。两项实验均按各自二十个相同官方文件计分。[逐题与协议对照](docs/results.md#47-按公开运行反馈独立建库再用同模型组装)

六模型的离线复测按已交付的源码重建接口。TodoMVC 的 Gemma 控制器通过 6/8，从零通过 4/8，固定该实现也通过相同六题。Duo 按公开功能名组装两个模型组件，GPT-OSS 通过 6/10（从零 5/10），Qwen3.5 通过 3/10（从零 2/10）。修正从零代码的默认导出后，Mistral 两者都为 4/10，另外三模型仍以从零更高。离线绑定结果见逐题复验记录。主表的 Self 记录模型自己建库后生成的配置。Duo 的 GPT-OSS 两次为 9/10、6/10，同等公开修复后的从零为 9/10。TodoMVC 的 Gemma 两次为 0/8、5/8，固定默认值逐题相同；给双方相同的分支作用域修复，从零为 6/8。[历史源码对照](studies/results/library-domain-replay-20261124.json) · [两次新建库逐行分母](studies/results/prospective-domain-builds-20261124.json)

本地 Qwen2.5-0.5B 使用按键注册表与有限数学语法，两次独立准备的计算器库通过 5/20、7/20，同模型从零为 0/20。固定同一种按键顺序已有相同成绩，仅使用起始工程与确定性数学绑定也通过 6/20。[领域辅助建库与对照](studies/public_library_transfer/self_refinement/local_domain/typed_keys/result.json)

Qwen3-Coder 按依赖顺序生成的两个表格库分别通过 5/20、1/20，同设置从零为 3/20，两个固定首例分别过相同的题。[代码模型逐题结果](studies/results/self-dependency-resume-20261124.json)

建库质量与逐题选配置可以分别检验。保持 Qwen3.5-9B 和同一组 20 个表格任务不变，换用两份独立 GPT-6 Astra 库，原配置协议分别通过 9/20 和 12/20。两份库直接复用首例各通过 13/20。关闭额外推理并约束配置输出后，Qwen 为两份库分别选了 20 次首例。原 GPT-5 库在原协议通过 1/20。[双库复验与同目标人工对照](studies/results/paper-library-followups-20261124.json) · [同目标结果与逐题标识](studies/public_library_transfer/strong_builder/result.json) · [受约束配置](studies/public_library_transfer/strong_builder/native/result.json)

## 安装与核验

需要 Python 3.13 和 [uv](https://docs.astral.sh/uv/)。在仓库根目录运行以下命令，可从随仓库发布的 JSON 核验目标数、配对成绩与费用汇总。

```bash
uv sync --extra dev
uv run python -m studies.public_library_transfer --check
```

运行工程测试还需要 Chromium 及其系统依赖。

```bash
uv run playwright install chromium
uv run pytest -q
```

这两种检查均不调用模型 API。逐份浏览器报告的核验需要本地 `artifacts/` 中保存的原始产物。论文源文件和展示材料也在本地维护，匿名材料下载地址待发布。[环境、数据和复验范围](docs/reproducibility.md)

冻结 GPT-5 库后，Qwen3.5 只需在两个已有 SVG 示例中选择，成绩就从 1/20 提到 15/20；固定首例通过 17/20。它自己的 TodoMVC 库提供 32 种合法配置，其中仅 4 种能完成共同的新增、去空、保存和恢复。限选这四种后，逐题从 0/8 到 5/8，固定页同为 5/8。文件管理器按新增条目身份复验后，Qwen 的两份自建库逐题过 1、2 项，Flash 过 2、6 项，各组分母均为 20。另一个公开图表修复让 Qwen 的几何检查从 36 增至 46，却让自建库正式成绩从 4/20 降至 3/20。逐项复核覆盖登记时 GPT-5 库低于 Self 的全部 12 格。[逐模型、固定对照与费用](studies/results/library-source-diagnosis-20261126.json)

## 来源

GUI-DNA 的设计受到 Divide and Abstract 的分解与复用思路启发。Web-Bench 实验采用上游公开需求、起始工程与官方测试。TodoMVC、WebApp1K-Duo 的来源和运行协议在研究索引中分别说明。[Divide and Abstract](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9f94298bac4668db4dc77ddb0a244301-Abstract-Conference.html) · [ByteDance Web-Bench](https://github.com/bytedance/web-bench) · [论文研究索引](studies/README.md)
