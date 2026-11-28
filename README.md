# GUI-DNA: Building and Reusing Behavior Libraries for GUI Generation

GUI-DNA 让模型用配置组装可复用的界面行为。例如，文件管理器的「新建」操作需要根据当前选中的是文件还是目录决定插入位置。论文比较三类工作流：从零编写页面、组装人工提供的组件、组装模型根据公开需求建立的库。[方法与组件来源](docs/method.md)

## 按数据集、模型和方法查 Table 1

点下表中的项目，找到**模型所在行**和**方法所在列**。点成绩可查看主表 JSON 的对应位置，展开表下的「来源记录」可查实验数据。

| 分区 | 评测对象 | 项目成绩 |
| --- | --- | --- |
| **A · Web-Bench** | 一项当前任务的官方测试 | [表格编辑器](paper-results/A/table-editor.md) · [SVG 图表](paper-results/A/svg-charts.md) · [问卷](paper-results/A/question-form.md) · [文件管理器](paper-results/A/file-explorer.md) · [计算器](paper-results/A/calculator.md) |
| **B · 功能组合** | 待办功能子集、业务功能对 | [TodoMVC](paper-results/B/todomvc.md) · [WebApp1K-Duo](paper-results/B/webapp1k-duo.md) |
| **C · WebGen-Bench** | 九个网站上的操作 | [网站操作](paper-results/C/webgen-bench.md) |
| **Other · 补充实验** | 独立复验、固定配置、建库费用和早期协议 | [按研究问题查找](paper-results/Other/README.md) |

四列共用该模型、该项目的目标和分母。**Direct** 从零写代码。**Human** 用人工提供的组件。**GPT-5** 用 GPT-5 建好并冻结的库。**Self** 由该行的目标模型建库并选择配置。分数表示通过数 / 同题数；项目页将论文中的空白格标为「建库失败」，横线标为「无数据」。

例如，要查 Qwen 自建库在表格编辑器上的表现，打开上面的「表格编辑器」，读 Qwen3.5-9B 或 Qwen3-Coder-30B 对应行的 Self 列。也可以在仓库根目录用 Python 3.13 查项目、模型和单格 JSON，无需 API key。

```bash
python -m studies.lookup
python -m studies.lookup web-bench/table
python -m studies.lookup web-bench/table "Qwen3.5-9B" Self
```

单格输出给出主表文件、矩阵键、分母和可用的实验记录。多阶段结果还列出适用的补测文件或筛选条件。完整矩阵也可直接下载。[Table 1 JSON](studies/results/paper-performance-matrix.json)

## 文档导航

| 想了解什么 | 从这里开始 |
| --- | --- |
| GUI-DNA 怎样工作、人工库与 AI 库分别看到了什么 | [方法与指标](docs/method.md) · [逐项目建库设计](docs/research/library-preparation-design.md) |
| 怎样安装环境、复算报告、运行浏览器测试 | [环境与复现命令](docs/reproducibility.md) |
| 某次实验为什么这样设计、结果如何、花了多少 | [按日期的实验记录](docs/results.md) · [匹配需求与预算的实验设计](docs/research/end_to_end_protocol.md) |
| 下一步要做什么、论文参考了哪些工作 | [投稿前待办](todo.md) · [相关研究笔记](docs/research/related-work-notes.md) |
| 某个项目的运行器、协议或旧版本在哪里 | [研究代码索引](studies/README.md) · [归档文档](docs/archive/) |

## 代码结构

```text
paper-results/{A,B,C,Other}/           按论文分区浏览成绩和补充实验
studies/
  webbench/                     Web-Bench 各项目的运行器、协议与逐题记录
  public_library_transfer/      TodoMVC、Duo 与跨项目建库实验
  webgen_bench/                 网站生成、浏览器操作与判决
  results/                      发布的 JSON 矩阵、汇总与核验记录
  lookup.py                     按项目、模型、方法查询一格
src/gui_dna/                    方案编译、页面渲染与评测
tests/                          工程回归测试
experiments/                    早期冻结原型及其运行器
configs/                        原型配置
data/dev/                       开发样例
docs/                           方法、复现、结果记录与研究笔记
todo.md                         当前待办
```

旧清单使用的 `test/` 指向 `studies/`。大体积响应、截图和账本保存在本地 `artifacts/`，论文与展示的本地目录分别为 `DNA_latex/` 和 `presentation/`。[目录与冻结路径](studies/README.md)

GUI-DNA 的分解与复用思路受到 Divide and Abstract 启发。Web-Bench 的需求、起始工程与官方测试来自字节跳动发布的基准。[Divide and Abstract](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9f94298bac4668db4dc77ddb0a244301-Abstract-Conference.html) · [ByteDance Web-Bench](https://github.com/bytedance/web-bench)
