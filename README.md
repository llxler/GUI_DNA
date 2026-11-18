# GUI-DNA: Building and Reusing Behavior Libraries for GUI Generation

GUI-DNA 研究如何让 AI **先建立可复用 GUI 行为库，再为具体需求生成组装方案**。主比较是这条完整流程与**不给库、从零编写页面**。基线仍获得目标需求和运行合同；建库的需求范围、额外计算与费用属于方法的一部分。

本仓库包含研究代码、冻结协议和派生结果。论文与展示材料仍仅在本地保存；大型原始产物、匿名下载地址和作者审核尚未完成，不能将源码仓库视为完整复现包。

## 结果概览

下表来自 [主比较 JSON](studies/results/end_to_end.json)，为六个历史项目的事后重算。每项是通过当前官方任务文件全部断言的候选数/真实候选数。**两位建库者各占一列，每列与无库基线分母一致；无库基线只显示一次，共同用于两项比较。** 列名是建库模型，不是目标生成模型；不同协议不合并，逐生成模型结果见 JSON 的 `by_generator_builder`。

| 研究 | 无库基线 | GUI-DNA：GPT-5 建库 | GUI-DNA：Claude 建库 |
| --- | --- | --- | --- |
| dom1、form | 25/80（31.25%） | 43/80（53.75%） | 43/80（53.75%） |
| calculator、table、bom | 42/120（35.00%） | 49/120（40.83%） | 44/120（36.67%） |
| draw 五里程碑 | 3/10（30.00%） | 8/10（80.00%） | 6/10（60.00%） |

BOM 六文件统一排除后，无库为 39/108，GPT-5 建库为 43/108，Claude 建库为 36/108；两套库相对基线分别为 +3.70 和 −2.78 个百分点。在这三批实验中，建库者看过全部公开需求，基线只看目标前缀。两种流程的准备机会也不同。

### 匹配工作流实验

双方均看到全部 21 条公开需求，使用相同模型、相同输出上限，各自有一次准备调用和同样的公开修复机会。无库组用自己的实施笔记逐目标写页面，GUI-DNA 组用冻结实现为目标生成方案。每次独立准备对应 5 个预定里程碑。每列都使用该次重复的同五个目标。

| 项目 | 双方模型 | 输出上限 | 重复一 无库 | 重复一 GUI-DNA | 重复二 无库 | 重复二 GUI-DNA |
|---|---|---:|---:|---:|---:|---:|
| canvas | GPT-5 | 16,000 | 1/5 | 0/5 | 1/5 | 0/5 |
| canvas | GPT-5 | 32,000 | 2/5 | 1/5 | 2/5 | 3/5 |
| canvas | Claude Sonnet 4.5 | 32,000 | 3/5 | 1/5 | 1/5 | 1/5 |
| flex | GPT-5 | 32,000 | 1/5 | 1/5 | 1/5 | 1/5 |

GPT-5 在 canvas 的 16k 设置下，两次建库及修复都因输出截断而无法使用。32k 下两套库可以使用，但第一个文档示例直接复用也分别通过了与逐任务选择相同的 1/5 和 3/5。flex 上两组在两次重复中都只通过第 4 项。另一项浏览器干预发现，四套 32k 游戏库都至少有一个字段能改变按键加速幅度，但各库固定复用第一个示例页也达到对应逐任务选择的通过数。完整费用、候选状态与配对见 [实验记录](docs/results.md) 第 38 节。

原同库自由代码实验保留在代码和历史 JSON 中，不进入当前论文正文、附录或汇报。历史方法标识和分数不会改成无库基线；没有真实无库组的旧小试不补造比较。

## 方法

1. **构建**：AI 读取公开需求，提出整页源码、方案模式、确定性编译器和示例；不接收官方参考实现或隐藏测试。
2. **冻结**：采用首次通过预定格式、编译与加载检查的库，记录失败与费用；加载通过不代表行为正确。
3. **组装**：针对目标累计需求生成数据方案，由冻结编译器产出页面。
4. **评估**：全部候选生成后执行官方浏览器测试，检查当前任务文件中的全部断言。

方法不训练新模型。现有证据研究已知公开应用范围内的构建与复用，不声称学到了跨项目通用抽象。具体数据边界、成本口径及旧人工库实验的区别见 [方法说明](docs/method.md)。

## 安装与零 API 检查

需要 Python 3.13、[uv](https://docs.astral.sh/uv/) 和 Chromium 的系统依赖。

```bash
git clone https://github.com/llxler/GUI_DNA.git
cd GUI_DNA
uv sync --extra dev
uv run playwright install chromium
uv run pytest -q
uv run python -m studies.end_to_end --check
```

Linux 系统缺少浏览器库时可运行 `uv run playwright install-deps chromium`（需要管理员权限）。现有无 sudo 环境也支持从 `.browser-deps/` 加载依赖。项目目录改名导致旧 venv shebang 失效时，运行 `uv venv --clear` 后重新同步依赖。

上述结果重算读取已保存汇总，不产生 API 费用，也不代表重新生成所有候选或重跑全部浏览器报告。真实生成需要独立阶段、冻结协议、明确预算和环境变量中的 API 密钥；旧账本不重开。完整入口和原始产物范围见 [复现说明](docs/reproducibility.md)。

## 仓库结构

| 路径 | 内容 |
|---|---|
| [`studies/`](studies/README.md) | 公开基准实验、冻结协议、分析与派生结果 |
| [`tests/`](tests/README.md) | 工程回归测试；不是研究实验目录 |
| [`experiments/`](experiments/README.md) | 早期冻结原型及历史运行器，第三轮仍暂停 |
| `src/gui_dna/` | 核心运行时、编译器、评测器、模型客户端与预算账本（被历史清单冻结） |
| `configs/`、`data/` | 原始配置和早期开发数据；不混入当前公开基准主表 |
| [`docs/method.md`](docs/method.md) | 数据、流程、指标和信息边界 |
| [`docs/results.md`](docs/results.md) | 追加式研究结果记录；历史事实保留 |
| [`docs/roadmap.md`](docs/roadmap.md) | 精简后的未完成任务 |
| [`docs/reproducibility.md`](docs/reproducibility.md) | 零 API 复算、环境与发布范围 |
| `docs/archive/` | 旧长指令和计划，仅在查证历史时阅读 |
| `scripts/` | 环境与余额检查工具 |
| `artifacts/` | 本地原始产物、响应、页面、账本与归档包，大部分不入 Git |
| `DNA_latex/`、`presentation/` | 本地论文和展示，不入 Git |

`test -> studies` 只服务旧导入和冻结清单；新代码、命令和文档使用 `studies`。旧中文文档名和 `experiments/TODO.md` 也是兼容链接，不是第二份文档。不能通过批量修改旧路径或哈希破坏历史证据。

## 来源与研究范围

设计受到 [Divide and Abstract（DNA）](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9f94298bac4668db4dc77ddb0a244301-Abstract-Conference.html) 的分解与复用思路启发；独立实现 GUI 行为构建与组装，不复制上游 Python/Lean 源码。当前主实验采用 [Web-Bench](https://github.com/bytedance/web-bench) 的公开需求与官方测试；TodoMVC、WebApp1K-Duo 及早期人工库实验保留各自来源和原协议。

项目目标为 ICML 2027 研究稿。作者审核和匿名材料发布仍待完成，更多独立项目列入研究计划。给编码代理的操作规则只维护在 [AGENTS.md](AGENTS.md)。
