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

论文 Table 1 按生成模型和项目报告当前任务文件通过数。表格和 SVG 登记 12 个模型，7 个获得新结果；问卷用相同的 7 个模型，TodoMVC 与 WebApp1K-Duo 用其中 6 个。计入单列的历史协议，共有 10 个生成模型有可比较成绩。GPT-5、GPT-5 mini、两款 Claude 4.5 和 Gemini 2.5 Flash 的本轮首个请求返回 403。表中保留其记录。[逐模型共同目标](studies/results/paper-performance-matrix.json) · [固定首例与分项费用](studies/results/backbone-overview-20261124.json)

**人工准备的行为库。** 在表格、SVG 和问卷这三个项目上，各有 6/7 个模型的组装通过数高于本模型从零生成。在同一批 20 项表格任务上，GPT-OSS-120B 从零通过 7 项，组装上游参考组件通过 20 项，使用自己的库通过 0 项。早期文件管理器实验中，参考组件组装为 126/140，逐步编辑前一页为 52/140。[组件来源与评测协议](docs/method.md)

**从公开需求建库。** DeepSeek V4 Flash 在 TodoMVC 的从零代码为 2/8，自建库组装为 8/8。固定复用建库时的首例同样为 8/8。在 Duo 的十个双功能组合上，同一模型从零为 6/10，自建库为 0/10。每个实验分别报告哪份实现能工作，以及逐题更改配置增加了哪些通过项。[多模型实验](studies/webbench/backbone_matrix/README.md) · [完整记录](docs/results.md)

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

## 来源

GUI-DNA 的设计受到 Divide and Abstract 的分解与复用思路启发。Web-Bench 实验采用上游公开需求、起始工程与官方测试。TodoMVC、WebApp1K-Duo 的来源和运行协议在研究索引中分别说明。[Divide and Abstract](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9f94298bac4668db4dc77ddb0a244301-Abstract-Conference.html) · [ByteDance Web-Bench](https://github.com/bytedance/web-bench) · [论文研究索引](studies/README.md)
