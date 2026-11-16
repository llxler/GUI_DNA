# GUI-DNA：GUI 行为库的构建、复用与组装方案评估

> 研究模型怎样构建和复用 GUI 行为库。模型可以自由编写、修改代码，也可以输出由冻结编译器解释的**组装方案**；实验区分库提供的知识、输出约束、反馈与评测覆盖。
> 早期提供库的实验有明显收益，但更强对照收窄了结论：三个模型建库的 Web-Bench 项目中，代码可直接调用整个编译器，方案与同库代码分别通过 93/240、90/240 个当前任务文件；在同一页面检查完整历史后为 26/240、27/240。两个开发集建库诊断中，确定性控制也复现了大部分成功。当前证据支持有条件的库复用，尚不能证明普遍的规划优势或新的抽象学习算法。完整结果和保留的负结果见 [实验结果.md](实验结果.md)，剩余关键问题见 [实验 TODO](experiments/TODO.md)。

目标会议：ICML 2027（具体日期以官方征稿通知为准）。本仓库是研究原型。第一次读代码请先看 [代码逻辑.md](代码逻辑.md)：数据长什么样、各做法每一步做什么、结果怎么算。原第三轮保持冻结和暂停；后续实验使用独立目录、协议和账本。2026-11-16新增匹配公开反馈与费用审计，并发现BOM/task-20存在空白页也能通过的官方断言路径；原分数保留，解释边界见结果第29–31节。

## 1. 想法

### 1.1 借用的思路：DNA（ICLR 2026）

[DNA：Divide and Abstract](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9f94298bac4668db4dc77ddb0a244301-Abstract-Conference.html) 做数学定理的自动形式化：先从已有语料学习一批**可复用抽象**，遇到新定理时不让模型一次写完全部证明，而是**分解 → 逐块翻译 → 组合**，再用符号验证的反馈修复。核心是用可复用抽象降低单次生成复杂度，全程不训练模型。

### 1.2 早期原型中的迁移

| DNA 中的对象 | 本项目的对应 |
|---|---|
| 可复用数学定义与依赖图 | 冻结的原子函数库：20 个状态操作函数，附读/写字段等接口信息 |
| 分解、翻译、组合数学陈述 | 分解功能需求，选函数、排顺序、绑事件 |
| 符号验证 + 反馈修复 | Playwright 操作真实控件，逐步比对 DOM 与内部状态；最多两轮修复 |
| 本项目比较的变量 | 模型输出**组装方案**或代码；编译器的静态检查和诊断是否帮助修复 |

早期原型聚焦列表管理 GUI 的七类交互：搜索、筛选、排序、分页、编辑、删除、撤销，以及五种语义变体（前缀/子串搜索、排序并列保留顺序/按 ID、视图变化时保留/取消草稿、重置/保留页码、撤销恢复原位/末尾）。页面渲染由一个固定的 HTML/JS 外壳负责，模型只决定交互逻辑 `window.candidate = {reduce(state, event), select(state)}`。

### 1.3 早期提供库的观察：组装错误

前两轮实验发现，直接让模型拼代码时，失败主要不是函数写错，而是**组装错误**：漏绑 `draft/save/cancel` 等事件、事件名写错（`pagination` 而不是 `page`）、选错语义变体、分页没放在流水线最后。这类错误用浏览器测试能发现，但修复反馈不够明确，模型三轮都修不好。

这一观察限于早期提供库的条件。后续让模型自行提出接口和整页实现，也发现冻结库的实现缺陷；如果接口内没有正确页面，再好的方案选择和格式检查也不能修复它。正向可达见证、完整有限枚举的否定证据与搜索后仍未知的情况必须分开。

### 1.4 原型机制：受检查的组装方案

模型不写代码，只输出三部分的 JSON 组装方案：

```json
{
  "view":     ["searchContains", "filterRows", "pageRows"],
  "handlers": {"search": "searchReset", "filter": "filterReset", "page": "pagination"},
  "after":    ["normalizePage"]
}
```

- `view`：视图流水线，用哪些纯行函数、什么顺序；
- `handlers`：事件路由，每个事件绑到库里哪个函数；
- `after`：每个事件之后的钩子（草稿策略、页码规范化）。

编译器（`experiments/scale_study/domain.py` 的 `compile_plan`）做静态检查：

1. 所有启用的事件都已路由，且绑到该事件允许的函数；
2. 视图里只有只读的行函数；每个启用的 search/filter/sort 恰好选一个语义变体；`pageRows` 恰好出现一次且在最后；
3. `after` 以恰好一个 `normalizePage` 结尾；启用编辑时恰好选一个草稿策略；
4. 未知函数名/事件名直接拒绝；已知但未启用的节点自动裁剪（不补齐、不改绑定）。

检查不通过时，反馈**明确列出缺了什么**（例如「缺少 draft/save/cancel 路由，允许的处理函数为…」），模型据此修复；通过后编译器把冻结函数体拼成代码。编译器**不知道**任务的正确语义策略，选错变体仍能通过编译，必须由行为测试检出。

### 1.5 从原型到模型建库

后续实验让模型从公开需求提出整页源码、方案模式、编译器和示例，不再提供人工槽位或固定外壳。两种同库做法获得相同用户输入；自由代码还可以调用整个编译器、修改其结果或自行实现。模型提出的模式经过通用格式检查，不能因此继承早期人工接口的覆盖保证，更不能保证行为正确。

评估分别检查库访问、方案输出、公开反馈和评分端点。固定示例、固定最终方案及无需模型的组合规则用于判断是否真的需要逐任务决策；当前任务文件与同页全部历史分开报告。某个方案失败时，还要区分模型选错、库内不存在正确配置、以及有限搜索后仍不知道三种情况。完整结果见[实验结果.md](实验结果.md)，复验入口见[test/REVIEW.md](test/REVIEW.md)。

## 2. 安装

需要 Python 3.13 与 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/llxler/GUI_DNA.git
cd GUI_DNA
uv sync --extra dev
uv run playwright install chromium
# Linux 缺少浏览器运行库且有管理员权限时：
uv run playwright install-deps chromium
```

没有 sudo 的 Debian/Ubuntu 环境可以把缺失的 `libnspr4` / `libnss3` 解包到项目内的 `.browser-deps/`，评测子进程会自动加入 `LD_LIBRARY_PATH`：

```bash
mkdir -p .browser-deps
(cd .browser-deps && apt download libnspr4 libnss3)
for package in .browser-deps/*.deb; do dpkg-deb -x "$package" .browser-deps; done
```

如果项目目录改过名，`.venv/bin/` 里的脚本会指向旧路径（表现为 `Failed to spawn: pytest`），重建即可：`uv venv --clear && uv sync --extra dev`。

### 2.1 验证安装（不调用 API）

```bash
uv run pytest -q                                             # 工程测试，含真实浏览器，约几分钟
uv run gui-dna evaluate --self-check --out artifacts/selfcheck # 评测器校准：8 个正确实现通过、4 个注入故障被检出
uv run python -m experiments.scale_study.calibrate           # 第三轮：16 个参考实现 + 5 种策略错误校准
```

离线演示（四种方法共用参考组合器，只验证工程流程，不是模型对照）：

```bash
uv run gui-dna learn-library --offline
uv run gui-dna generate --offline --requirement '支持搜索、筛选、排序、分页、编辑、删除和撤销的列表' --out artifacts/demo
uv run gui-dna compare --offline
```

生成的 `artifacts/demo/index.html` 可直接用浏览器打开，无服务器、无网络依赖。

### 2.2 真实实验

真实实验通过 [OpenRouter](https://openrouter.ai/docs/api_reference/overview) 调用模型，只从环境变量读取密钥，不写入任何文件：

```bash
export OPENROUTER_API_KEY=...
uv run python scripts/check_openrouter_credits.py --required-usd 1   # 查余额，不产生费用
uv run python -m experiments.resume_scale --check                     # 第三轮断点检查，只读
uv run python -m experiments.resume_scale --resume                    # 仅在另获明确第三轮续跑授权后使用（付费）
```

第三轮使用 `artifacts/budget.sqlite3`，硬上限 $9、$8.8 停止新请求，目前人工暂停；后续阶段各有独立账本。每次 POST 先原子预留费用上界，再按 OpenRouter 回执结算，传输不完整时保留未知预留。已关闭账本不能放宽，新增实验按当次授权与实际余额分配。各阶段运行和只读复验入口见 [AGENTS.md](AGENTS.md) 与 [test/REVIEW.md](test/REVIEW.md)。

## 3. 仓库结构

| 路径 | 内容 |
|---|---|
| `src/gui_dna/` | 第一轮：任务定义、固定渲染器、Playwright 评测器、独立 oracle、函数库学习、OpenRouter 客户端、预算账本 |
| `src/gui_dna/followup/` | 第二轮：原子函数库、方案编译器 v1、行为/状态分离评测、八方法消融 |
| `experiments/scale_study/` | 第三轮（冻结、暂停）：语义变体函数库、策略盲编译器、隐藏评测、家族聚类 bootstrap 分析 |
| `experiments/*.py` | 第三轮续跑 / 审计 / 零 API 规则控制；`webapp1k_probe.py` 是 WebApp1K 探针（被 `test/webapp1k_dna/` 复用）；`replay_linked_plans.py` + `plan_linker.py` 是第二轮事后连接器复验（manifest 钉了路径，留在原处） |
| `experiments/round2/` | 第二轮辅助脚本（预加载强基线、同等接口配对、汇总），只用于复算 [实验结果.md](实验结果.md) 第 3 节 |
| `experiments/TODO.md` | 实验待做清单（按收益/成本排序，含费用估算与入口命令）；做完的项删掉，结果进 [实验结果.md](实验结果.md) |
| `configs/` | 三轮实验配置（模型、温度、预算、提供商路由） |
| `data/dev/` | 16 个开发任务及参考实现、人工契约标注 |
| `tests/` | 上下文边界、编译器拒绝规则、账本并发、评测器校准等测试 |
| `scripts/` | OpenRouter 余额检查 |
| `实验结果.md` | 三轮实验全部结果、失败案例、费用、续跑说明与外部 benchmark 对比 |
| `代码逻辑.md` | 面向新读者的流水线说明：数据示例、普通做法与 GUI-DNA 做法逐步对照、指标含义、术语表 |
| `test/` | 三个外部数据集上的对比实验（WebApp1K-Duo、TodoMVC、Web-Bench dom1），各有 README；`paired_intervals.py` 算配对差的聚类 bootstrap 区间，`webbench_dna/taskmap_figure.py` 画逐任务通过图 |
| `AGENTS.md` | 给 AI 编码代理（以及人）的操作手册 |
| `DNA_latex/` | ICML 2027 投稿的 LaTeX 源（`main.tex`、`custom.bib`、样式文件；未定数字与图以 TODO 占位）。**只在本地，已被 `.gitignore` 忽略，不入库** |
| `artifacts/` | 本地实验产物（不入库；仅少数 report/protocol 入库） |

## 4. 来源与致谢

- 论文：Marcus J. Min, Yeqi Gao, Wilson Sy, Zhaoyu Li, Xujie Si, Osbert Bastani. *Divide and Abstract: Autoformalization via Decomposition and Abstraction Learning*. ICLR 2026。[官方代码](https://github.com/marcusm117/DNA)（Apache-2.0）。
- 本项目借鉴 DNA 的分解、冻结组件、组合与验证反馈，独立实现交互逻辑组装原型；目前没有自主学习抽象或组件接口的证据，**没有复制上游任何 Python 或 Lean 源码**；提示词、GUI 参考代码、浏览器评测器、预算账本均为新编写。状态契约与受检查的组装方案是本项目新增的机制。
- 浏览器依赖依据 [Playwright 安装文档](https://playwright.dev/python/docs/intro)；费用结算依据 [OpenRouter 用量记录说明](https://openrouter.ai/docs/cookbook/administration/usage-accounting)。
