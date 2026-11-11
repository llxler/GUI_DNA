# GUI-DNA：面向 GUI 功能组合的「方案 → 编译 → 验证」免训练生成

> 不让大模型直接写 GUI 代码，而是让它输出一份**组装方案**，由编译器静态检查、给出明确诊断、再把冻结的函数体拼成可运行代码。
> 在当前实验中，组装方案相对自由代码提高最终正确率：自建列表任务 27/47 → 47/47、TodoMVC 官方测试 116/128 → 128/128、Web-Bench dom1 官方测试 52/140 → 126/140（主表统一排除传输缺失的 Gemma）；WebApp1K-Duo 十题没有提升。函数库、人工接口及生成协议共同影响这些差值，不能只归因于输出格式。最新对照与边界见 [实验结果.md](实验结果.md) 第 16 节。

目标会议：ICML 2027（具体日期以尚待发布的官方征稿通知为准）。本仓库是 idea 验证原型，不是通用网页生成器。第一次读代码请先看 [代码逻辑.md](代码逻辑.md)：数据长什么样、两种做法每一步做什么、结果怎么算。

## 1. 想法

### 1.1 借用的思路：DNA（ICLR 2026）

[DNA：Divide and Abstract](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9f94298bac4668db4dc77ddb0a244301-Abstract-Conference.html) 做数学定理的自动形式化：先从已有语料学习一批**可复用抽象**，遇到新定理时不让模型一次写完全部证明，而是**分解 → 逐块翻译 → 组合**，再用符号验证的反馈修复。核心是用可复用抽象降低单次生成复杂度，全程不训练模型。

### 1.2 迁移到 GUI

| DNA 中的对象 | 本项目的对应 |
|---|---|
| 可复用数学定义与依赖图 | 冻结的原子函数库：20 个状态操作函数，附读/写字段等接口信息 |
| 分解、翻译、组合数学陈述 | 分解功能需求，选函数、排顺序、绑事件 |
| 符号验证 + 反馈修复 | Playwright 操作真实控件，逐步比对 DOM 与内部状态；最多两轮修复 |
| 本项目新增的变量 | 模型只输出**组装方案**而不是代码；编译器做静态检查并给出明确诊断 |

领域是列表管理 GUI 的七类交互：搜索、筛选、排序、分页、编辑、删除、撤销，以及五种语义变体（前缀/子串搜索、排序并列保留顺序/按 ID、视图变化时保留/取消草稿、重置/保留页码、撤销恢复原位/末尾）。页面渲染由一个固定的 HTML/JS 外壳负责，模型只决定交互逻辑 `window.candidate = {reduce(state, event), select(state)}`。

### 1.3 关键观察：失败在「组装」，不在「函数」

前两轮实验发现，直接让模型拼代码时，失败主要不是函数写错，而是**组装错误**：漏绑 `draft/save/cancel` 等事件、事件名写错（`pagination` 而不是 `page`）、选错语义变体、分页没放在流水线最后。这类错误用浏览器测试能发现，但修复反馈不够明确，模型三轮都修不好。

### 1.4 新机制：受检查的组装方案

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

### 1.5 结果与边界（一句话）

第三轮（190 个候选、47 个完整四方法组）中，受检查的组装方案对预先指定的预加载自由胶水代码基线：Qwen 14/20 → 20/20，DeepSeek 13/27 → 27/27，功能家族聚类 bootstrap 95% 区间下界均高于 0；方案的输出 token 约为该基线的 1/8–1/4。但这个环境是受控的：一个不调用模型的固定句式解析规则系统也能满分，因此目前能支持的结论是**「明确的接口完整性诊断帮助修复」这个机制有效**，而不是模型推理能力变强，也不能推广到任意网页。完整数据、负结果和论文表述建议见 [实验结果.md](实验结果.md)。

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
uv run python -m experiments.resume_scale --resume                    # 明确继续第三轮（付费）
```

所有付费调用经过 `artifacts/budget.sqlite3` 这个唯一账本：每次 POST 先原子预留费用上界，按 OpenRouter 回执结算，硬上限 $9、$8.8 停止新请求。各轮实验的完整命令与注意事项见 [AGENTS.md](AGENTS.md)。

## 3. 仓库结构

| 路径 | 内容 |
|---|---|
| `src/gui_dna/` | 第一轮：任务定义、固定渲染器、Playwright 评测器、独立 oracle、函数库学习、OpenRouter 客户端、预算账本 |
| `src/gui_dna/followup/` | 第二轮：原子函数库、方案编译器 v1、行为/状态分离评测、八方法消融 |
| `experiments/scale_study/` | 第三轮（当前主线）：语义变体函数库、策略盲编译器、新隐藏评测、家族聚类 bootstrap 分析 |
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
