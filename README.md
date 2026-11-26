# GUI-DNA: Building and Reusing Behavior Libraries for GUI Generation

GUI-DNA 将「用户操作如何改变应用状态」写进可复用的行为库，让模型根据需求选择配置。例如，文件管理器中同一个「新建」按钮，要根据当前选中的是目录还是文件来决定插入位置。论文比较从零生成代码、组装人工组件，以及组装模型从公开需求建立的库。[方法说明](docs/method.md)

## 按数据集、模型和方法查 Table 1

在仓库根目录运行。查询只读取随 Git 发布的记录，使用 Python 3.13 标准库，无需 API key、浏览器或本地实验产物。

```bash
python -m studies.lookup                                             # 列出数据集和项目
python -m studies.lookup web-bench/form                              # 列出该项目在表中的模型
python -m studies.lookup web-bench/form "DeepSeek V4 Flash"           # 列出方法名及其 JSON 标识
python -m studies.lookup web-bench/form "DeepSeek V4 Flash" Self      # 查看一个格子的成绩和出处
```

最后一条查询返回 **11/20**。打开输出的 `matrix`，按 `row_keys` 依次进入模型和实验记录，在 `passed.self` 看分子，在 `n` 和 `targets` 看分母和目标。再打开 `method_record`。这次实验把首份自建库记作 `file-a`，其 20 行分别给出任务编号、是否通过和浏览器报告哈希。同目录的协议说明建库及解码条件，运行器给出实现。早期协议的 0/20 仍保存在矩阵的 `current.form` 中。[主表 JSON](studies/results/paper-performance-matrix.json) · [本格逐题记录](studies/webbench/form/flash_self_build/visible_targets/result.json) · [协议](studies/webbench/form/flash_self_build/visible_targets/PROTOCOL.md) · [运行代码](studies/webbench/form/flash_self_build/visible_targets/run.py)

| Table 1 | 查询用的数据集／项目名 | 实验代码入口 |
| --- | --- | --- |
| A · Web-Bench 完整项目 | `web-bench/table`、`web-bench/svg-chart`、`web-bench/form`、`web-bench/dom1`（文件管理器）、`web-bench/calculator` | [Web-Bench 分项目索引](studies/webbench/README.md) |
| B · TodoMVC 功能子集 | `todomvc` | [人工库](studies/todomvc_dna/README.md) · [小模型建库](studies/public_library_transfer/compact_todomvc/PROTOCOL.md) · [配置筛选](studies/public_library_transfer/source_diagnosis/visible_choices/core_profiles/PROTOCOL.md) |
| B · WebApp1K-Duo 双功能组合 | `webapp1k-duo` | [公开功能与配对](studies/public_library_transfer/other_benchmarks/README.md) · [GPT-5 组件来源](studies/public_library_transfer/duo_donor_library/PROTOCOL.md) · [Self 回调与视图](studies/public_library_transfer/duo_react_callbacks/PROTOCOL.md) |
| C · WebGen-Bench 网站功能 | `webgen-bench` | [站点、页面生成、逐项评分与评判器](studies/webgen_bench/README.md) |

模型名指负责当前目标的**生成模型**，支持上表命令列出的显示名和完整模型 ID。四种方法的 JSON 标识分别为 `direct`（从零写代码）、`human`（人工库＋GUI-DNA）、`gpt5-library`（冻结 GPT-5 库＋GUI-DNA）和 `self`（目标模型建库并配置）。固定示例和第二次独立建库可在对应研究记录中查阅。

- `status=measured` 给出实测分子和分母，零分也在此列。A、B 统计通过当前任务文件的次数。C 对功能操作按完整 1 分、部分 0.5 分计分。
- `build_failed` 对应论文空白格，`unavailable` 对应横线。两种状态都没有实测分数。每个项目的模型列表对应 Table 1 实际展示的行。
- 方法有独立来源记录时，`method_record` 指向该文件；补传目标另列于 `additional_targets_record`。多轮合并的格子可从 `assembly_code` 查到具体合并规则和输入。各研究 JSON 保留各自的字段名。历史模型、其他项目和固定页对照按研究索引查找。[研究索引](studies/README.md) · [历次结果](docs/results.md)

## 代码结构

```text
GUI_DNA/
├── src/gui_dna/                   核心库、方案编译、页面渲染与评测
├── studies/                       论文实验与结果
│   ├── lookup.py                  按项目、生成模型和方法查询 Table 1
│   ├── paper_performance.py       选择配对目标、生成主表
│   ├── results/                   随仓库发布的 JSON 汇总与主表矩阵
│   ├── webbench/                  Web-Bench 各项目的协议、运行器与逐题结果
│   ├── public_library_transfer/   跨项目建库、TodoMVC、Duo、固定页与独立重复
│   ├── webgen_bench/              六站生成、功能评分与评判器校准
│   ├── todomvc_dna/               TodoMVC 人工库研究
│   ├── webapp1k_dna/              WebApp1K-Duo 早期研究
│   └── webbench_dna/              早期 Web-Bench 文件管理器研究
├── tests/                         pytest 工程回归测试
├── experiments/                   早期冻结原型和历史运行器
├── configs/                       原型实验配置
├── data/dev/                      开发样例
├── docs/                          方法、结果、复现说明与研究计划
└── test -> studies/               旧导入和冻结清单使用的兼容链接
```

新研究从 `studies/` 进入，运行工程测试从 `tests/` 进入。本地 `artifacts/` 保存生成页面、原始回执、截图和账本；Git 只收录其中少量公开摘要。论文源文件和展示在本地的 `DNA_latex/`、`presentation/` 维护。[目录与冻结路径](studies/README.md) · [复现范围](docs/reproducibility.md) · [研究计划](docs/roadmap.md)

## 结果示例

| 问题 | 同协议观察 | 记录 |
| --- | --- | --- |
| 人工组件能提供多少可复用行为？ | 在同一批 20 项表格任务上，GPT-OSS-120B 从零生成通过 7 项，人工库组装通过 20 项。 | [组件与对照](docs/method.md) |
| 低分出在实现还是选配置？ | Qwen3.5 使用同一份 GPT-5 图表库，长配置通过 1/20，改选已有示例通过 15/20，固定首例通过 17/20。它自己的待办库限选满足共同操作的配置后从 0/8 升至 5/8，固定首例也通过相同五题。 | [原配置、固定对照与复验](studies/results/library-source-diagnosis-20261126.json) |
| 换到完整网站，哪种方法得分更高？ | 六站共 43 分。Gemma 从零得 13 分，人工库得 19 分；Qwen3.5 分别得 11.5 和 24.5 分。Flash 从零、人工库、自建库分别得 35.5、21 和 29 分。两款替代评判器在 32 个抽样配对中有 15 个等级一致。 | [六站逐项判决与校准](studies/results/webgen-functional-20261126.json) |

## 安装与核验

开发环境和工程测试使用 Python 3.13、uv 和 Chromium。在仓库根目录运行以下命令。

```bash
uv sync --extra dev
uv run python -m studies.webgen_bench.report --portable
uv run python -m studies.public_library_transfer.source_diagnosis.report
```

两条报告命令从版本库中的记录复算结果。完整工程测试还读取固定版本的 Web-Bench 需求和公开测试文件。首次检出且尚无 `artifacts/web-bench/` 时，准备公开快照后运行以下命令。

```bash
git init -q artifacts/web-bench
git -C artifacts/web-bench fetch --depth 1 https://github.com/bytedance/web-bench.git 7b31ca2b786eef120dd49ce63dd03d0c0006046d
git -C artifacts/web-bench checkout --detach FETCH_HEAD
uv run playwright install chromium
uv run pytest -q
```

已有对应快照的工作区只需安装浏览器并运行测试。重放完整浏览器实验还需要对应上游数据、系统运行库和本地原始产物。[环境与各项复验入口](docs/reproducibility.md)

## 来源

GUI-DNA 的设计受到 Divide and Abstract 的分解与复用思路启发。Web-Bench 实验采用上游公开需求、起始工程与官方测试。[Divide and Abstract](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9f94298bac4668db4dc77ddb0a244301-Abstract-Conference.html) · [ByteDance Web-Bench](https://github.com/bytedance/web-bench) · [研究索引与数据来源](studies/README.md)
