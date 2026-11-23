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

**人工准备的行为库。** TodoMVC 上，GUI-DNA 组装通过 128/128 个候选，无库生成通过 116/128。Web-Bench 文件管理器 `dom1` 的库来自基准参考实现，组装通过 126/140，无库组逐步编辑前一版页面，通过 52/140。两项各自使用对应协议和分母。[实验记录](docs/results.md)

**从公开需求独立建库。** 跨项目研究覆盖十个 Web-Bench 项目，每项目 20 个当前任务。以表格编辑器为例，在同一批任务上，Mistral 直接写代码通过 **3/20**。使用 GPT-6.2 Astra 独立构建的两份库进行配置，分别通过 **18/20、19/20**。固定使用第二份库的首个示例通过 17/20。穷举其八种合法配置后，三个开关全开的固定页覆盖了模型通过的全部 19 项。[跨项目对照与固定页复验](studies/public_library_transfer/README.md)

WebApp1K-Duo 要求在同一页组合两个功能。在独立的 GPT-6.2 Astra 部署实验中，无库组通过 9/10，两份库按题配置分别通过 5/10、9/10，固定首例均为 1/10。各基准的目标、建库者、部署模型和缺测情况分别记录。[跨基准研究](studies/public_library_transfer/README.md)

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
