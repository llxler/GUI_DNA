# AGENTS.md — GUI-DNA 操作手册

给 AI 编码代理（Claude Code / Codex / Cursor 等）和人用的速查。研究内容看 [README.md](README.md)，结果看 [实验结果.md](实验结果.md)。本文件只讲**怎么跑、怎么改、什么不能动**。

## 1. 项目现状（2026-10-30）

- 这是投 ICML 2027 的 idea 验证仓库。主线是**第三轮**（`experiments/scale_study/`）：模型输出受检查的组装方案，编译器拼冻结函数。
- 第三轮按用户要求**暂停**在 190/640 个候选；账本 `artifacts/budget.sqlite3` 的 `halted=1` 是人工暂停，不是超支。
- `qwen/qwen3-coder-plus` 已在 OpenRouter 下线，续跑会在模型检查处停下（预期行为）。
- 第三轮产物里的 `result.json` / `results.json` 记录的是**绝对路径** `/home/lxler/work/gui_test/...`（项目旧目录名）。目录已改名为 `GUI_DNA`，所以保留了符号链接 `/home/lxler/work/gui_test -> /home/lxler/work/GUI_DNA`；删掉它 `resume_scale`、`audit_scale`、`analyze` 都会 FileNotFoundError。换机器时把仓库放到同一路径或建同名链接。
- OpenRouter 余额约 $5.5（2026-10-30），用户预算很紧，**任何付费调用先问清楚、先查余额**。
- 2026-11-01 新增 `test/webapp1k_dna/`：在公开 benchmark WebApp1K-Duo 上对比自由代码与 GUI-DNA 组装（10 个样本，独立账本）。`test/` 是实验目录，`tests/` 才是主代码的 pytest。
- 2026-11-02 新增 `test/todomvc_dna/`：TodoMVC 规范 + Playwright 官方 TodoMVC 测试集（24 项，隐藏）上的三种做法对比；功能通过共享状态互相影响，与 `data/dev/` 同构。Node 侧运行器在 `test/todomvc_dna/harness/`（需 `npm install`）。
- 2026-11-02 新增 `test/webbench_dna/`：Web-Bench（字节）dom1 项目上的对比，官方测试逐字、参考实现拆成原子函数库。2026-11-03 TodoMVC 与 Web-Bench 都扩到 8 个模型并加了两个对照（自由代码 + 同一函数库、方案不做覆盖检查）；结果汇总在 `实验结果.md` 第 12 节。OpenAI 模型要经 `test/provider_ext.py`（冻结客户端的子类：允许低强度推理、去掉 GPT-5 不接受的参数）。账本不能放宽，扩展时用新的 `--out` 目录并拷入旧 `runs/`，费用用 `--extra-ledgers` 合并。余额约 $1.8（2026-11-03）。Node 运行器在 `test/webbench_dna/harness/`（需 `npm install`）；上游仓库克隆在 `artifacts/web-bench/`（只读）。
- 2026-11-05 整理：第二轮辅助脚本归档到 `experiments/round2/`（模块方式运行）；事后连接器复验 `experiments/replay_linked_plans.py` + `plan_linker.py` 留在原处，因为 `artifacts/linked-plan-posthoc/manifest.json` 记录了它们的路径与哈希，挪动或格式化都会让复验断言失败。新增 `DNA_latex/`（ICML 2027 论文源，英文；只在本地，`.gitignore` 忽略，不入库），旧论文模板目录已删。
- 2026-11-08：新增 `experiments/TODO.md`（**实验待做清单**，开工先读，做完的项从清单删除、结果进 `实验结果.md`）；零成本脚本 `test/paired_intervals.py`（TodoMVC / Web-Bench 配对差的聚类 bootstrap 区间 → `test/results/paired-intervals.{json,md}`）与 `test/webbench_dna/taskmap_figure.py`（`uv run --with matplotlib`，输出 `DNA_latex/figures/webbench_taskmap.pdf`）；Web-Bench 第五阶段 `artifacts/webbench-dna-5/` 已完成（「自由 + 同一函数库」「方案不做覆盖检查」补到全部 8 个模型，已结算 $1.68；结论见 `实验结果.md` 第 13 节：强模型拿到函数库写自由代码 68/80 对方案 73/80，函数库本身是强模型收益的大头）。余额 2026-11-08 约 $21.4（用户已充值），本次用掉约 $1.7。
- 中文为文档语言；代码注释与标识符为英文；`DNA_latex/` 内为英文论文。

## 2. 环境与常用命令

```bash
# 安装（Python 3.13 + uv）
uv sync --extra dev
uv run playwright install chromium            # 首次；浏览器放在 ~/.cache/ms-playwright
# 项目目录改名后 .venv 里脚本的 shebang 会失效（Failed to spawn: pytest）：
uv venv --clear && uv sync --extra dev

# 测试（含真实 Chromium，约 1 分钟，40 项）
uv run pytest -q
uv run pytest tests/test_scale_study.py -q                     # 单文件
uv run pytest tests/test_followup.py::test_ablation_context_boundaries -q   # 单测
uv run pytest -q -k "compiler or linker"                       # 关键字

# 不花钱的验证
uv run gui-dna evaluate --self-check --out artifacts/selfcheck   # v1 评测器校准
uv run gui-dna compare --offline                                 # v1 离线四方法流程
uv run python -m experiments.scale_study.calibrate               # v3 参考实现 + 策略错误校准
uv run python -m experiments.scale_rule_control                  # v3 零 API 规则控制
uv run python -m experiments.scale_study.analyze                 # 从 results.json 重算 analysis.json / report.md
uv run python -m experiments.audit_scale                         # 第三轮只读审计（哈希、账本、链接）
uv run python -m experiments.round2.summarize_followup          # v2 汇总（无 API）
uv run python experiments/replay_linked_plans.py                 # v2 连接器离线复验（无 API；manifest 钉了路径，不要挪）

# 付费（需要 export OPENROUTER_API_KEY=...；密钥只读环境变量）
uv run python scripts/check_openrouter_credits.py --required-usd 1   # 查余额，退出码 2 = 不足
uv run python -m experiments.resume_scale --check                     # 只读断点检查
uv run python -m experiments.resume_scale --resume                    # 明确继续第三轮
uv run gui-dna generate --method constrained --task test-delete-pagination --out artifacts/custom-run   # v1 单次生成

# 外部 benchmark 探针（WebApp1K-Duo，官方 Jest 评分，独立小账本 artifacts/benchmark-probe/budget.sqlite3）
#   首次：git clone --depth 1 https://github.com/onekq/WebApp1k.git artifacts/benchmark-probe/WebApp1k
#         (cd artifacts/benchmark-probe/WebApp1k/staging && npm install && npm install react-router-dom@6 node-fetch@2)
#         （fetch-mock 钉 9.11.0、react-router-dom 钉 6.x、node-fetch 2.x，否则官方测试在 CRA 5 / Jest 27 下无法加载）
uv run python -m experiments.webapp1k_probe --models deepseek/deepseek-v4-pro-0813 --categories blogging taskmanagement --per-category 5
uv run python -m experiments.webapp1k_probe --evaluate-only        # 只重新评分已保存的实现，不花钱

# WebApp1K-Duo 上的方法对比（test/webapp1k_dna/，独立账本 artifacts/webapp1k-dna/budget.sqlite3，上限 $1）
uv run pytest test/webapp1k_dna -q                                  # 方案编译器离线测试
uv run python -m test.webapp1k_dna.run --arms rule                  # 零 API：建冻结原子函数库 + 规则组装 + Jest
uv run python -m test.webapp1k_dna.run --arms free rule dna         # 付费：自由代码 vs GUI-DNA 组装方案（默认 10 个 Duo）

# TodoMVC 规范 + 官方 Playwright 测试集（test/todomvc_dna/，独立账本 artifacts/todomvc-dna/budget.sqlite3，上限 $1）
(cd test/todomvc_dna/harness && npm install)                        # 首次：@playwright/test 钉 1.63.0，复用已装浏览器
uv run pytest test/todomvc_dna -q                                   # 离线检查
uv run python -m test.todomvc_dna.run --arms rule                   # 零 API：规则组装 + 官方测试评分
uv run python -m test.todomvc_dna.run --arms free rule dna --samples 2   # 付费三种做法对比

# Web-Bench dom1（test/webbench_dna/，独立账本 artifacts/webbench-dna/budget.sqlite3，上限 $1.5）
#   首次：git clone --depth 1 https://github.com/bytedance/web-bench.git artifacts/web-bench ；(cd test/webbench_dna/harness && npm install)
uv run pytest test/webbench_dna -q
uv run python -m test.webbench_dna.run --arms rule                                  # 零 API：规则组装 + 官方测试
uv run python -m test.webbench_dna.run --arms free rule dna --models <...>           # 付费；--evaluate-only 只重评，--grade-workers 并行评分
```

`.browser-deps/` 里是无 sudo 环境解包的 `libnspr4`/`libnss3`，评测子进程自动加到 `LD_LIBRARY_PATH`；没有也不影响有系统库的机器。

## 3. 架构：三轮代码并存，第三轮是主线

三轮实验的代码**叠加而不替换**，后一轮 import 前一轮：

```
v1  src/gui_dna/            tasks/prompts/generation/experiment  四方法 direct|retrieval|dna|constrained
      ├─ render.py           shell.html 外壳 + reference.js（带 @function 契约注释的参考函数）
      ├─ evaluation.py       Playwright 子进程评测器；perform()/check() 被 v2、v3 复用
      ├─ oracle.py / suites.py   独立期望语义 + 隐藏用例（只被评测器 import）
      ├─ provider.py         OpenRouter 单次请求：预留→POST→结算；重放已结算响应；只重试 429
      └─ budget.py           SQLite 账本 Ledger(path, cap, stop)；只能收紧、不能放宽
v2  src/gui_dna/followup/   atomic_library()（v1 库人工拆成原子函数）+ compile_plan v1 + 八方法 study
      + experiments/round2/   预加载强基线、同等接口配对、汇总（只复算 实验结果.md 第 3 节，不在冻结清单内）
      + experiments/replay_linked_plans.py / plan_linker.py   事后连接器复验（路径被其 manifest 钉住）
v3  experiments/scale_study/ library()（v2 库人工扩成 20 个语义变体）+ 策略盲 compile_plan + 四方法 study
      + experiments/resume_scale.py / audit_scale.py / scale_rule_control.py
ext test/{webapp1k_dna,todomvc_dna,webbench_dna}/  三个外部数据集上的对比（各有 README）；experiments/webapp1k_probe.py 被 test/webapp1k_dna 复用
paper DNA_latex/           ICML 2027 投稿 LaTeX（main.tex 正文，TODO 标记待补数字与图；本地目录，不入库）
```

一个候选的生命周期（三轮一致）：

1. `tasks()` 给出 `{requirement, features, initial}`（v3 另有评测专用 `policy`，**不进 prompt**）。
2. `messages_for(task, method, lib)` 按方法构造消息；plan 两组初始消息字节相同，三个预加载组用户数据字节相同（有测试保证）。
3. `OpenRouter.call()`：`Ledger.reserve()` → POST → `settle()`；目录下已有 `request.json` 且账本已结算则直接重放 `response.json`，不再付费。
4. 输出 → `parse_json` → 代码直接用 / `compile_plan(plan)` 拼装；失败则 `compile_error` 作为公开反馈。
5. `write_app()` 把代码注入 `shell.html` → `evaluate()` 在子进程跑公开用例 → 失败反馈追加到消息，最多两轮修复。
6. 写 `result.json`（含 fingerprint 与各版本 sha256）。目录已存在时校验哈希后复用，配置变了就报错，不覆盖。
7. **全部生成结束后**才统一跑隐藏评测（首次与最终版本都评），再 `analyze` 做配对比较与家族聚类 bootstrap。

上下文边界靠结构保证：`oracle.py`、`fixtures.py`、`suites.py` 只被评测器 import；`messages_for` 用字段白名单；`tests/test_protocol.py`、`tests/test_scale_study.py` 断言隐藏数据、策略字段不出现在 prompt 里。改 prompt 或库时先跑这些测试。

## 4. 红线（改之前先看）

- **不要修改** `experiments/scale_study/*.py`、`src/gui_dna/**`（含 assets）和 `configs/scale-study.json`：第三轮 manifest 冻结了它们的 SHA-256，`resume_scale --check` / `audit_scale` 会失败，第三轮结果也会失去可比性。要改方法就新建目录（如 `experiments/round4/`）和新配置，另立实验阶段。
- **不要删除、替换、手改** `artifacts/budget.sqlite3`；不要手动把 `halted` 改回 0（只能通过 `resume_scale --resume` 的受控流程）。小预算探针请用**独立账本**：`Ledger(ROOT/'artifacts/<probe>/budget.sqlite3', cap, stop)` 传给 `OpenRouter(config, ledger)`。
- 新的付费实验用**新的 `--out` 目录**；不要覆盖已有运行清单。
- 不要把隐藏失败、`policy` 字段、oracle 逻辑放进任何模型消息。
- 不要在同一模型组里静默换模型；模型下线就另立阶段并写进报告。
- `artifacts/` 默认不入库（`.gitignore` 只放行各轮 `report.md` / `protocol.md`）；不要把截图、响应、账本提交上去。
- 费用、通过率等数字一律从 `results.json` / `analysis.json` / 账本重算，不要凭记忆改文档。

## 5. 文档约定

- `README.md`：安装 + idea 介绍，不放逐轮细节。
- `代码逻辑.md`：给新读者的流水线讲解（数据、两种做法逐步对照、指标、术语表），改方法或加数据集时同步更新。
- 用词：说「做法/对照组」不说「臂」，说「组装方案 / 组装」不说「接线」，结论段用「目前明确的是 / 还不能确认的是」。
- `实验结果.md`：唯一的结果文档；新一轮实验追加一节，不再新建「第 N 轮研究报告.md」。
- `AGENTS.md`：本文件；`CLAUDE.md` 只是指向这里的入口。
- `DNA_latex/`：英文论文，只在本地（`.gitignore` 忽略），不要提交。数字只从 `实验结果.md` 与各 `results/` 文件取，改了实验结论要同步改论文；未定内容用 `\TODO{...}`、缺数字用 `\TBD`、缺图用 `\figplaceholder{宽}{高}{说明}`（都在 `preamble.tex` 定义，红字显示），交稿前全部清掉。`icml2027.sty` / `icml2027.bst` 是由 2026 版改年份的草稿，官方 2027 样式发布后替换。`custom.bib` 每条都已对照出版方记录核实（2026-11-05），新加引用也要核实。正文必须 ≤ 8 页（影响声明、参考文献、附录不计）。
- 报告风格沿用：先写结论，正负结果都保留，明确写出「还不能确认的是」。

## 6. 关键文件速查

| 想做什么 | 看哪里 |
|---|---|
| 改第三轮任务/语义变体/编译器（新阶段） | `experiments/scale_study/domain.py`：`tasks()`、`library()`、`compile_plan()`、`reference_plan()`、`messages_for()` |
| 看隐藏用例怎么生成 | `experiments/scale_study/fixtures.py`（v3）、`src/gui_dna/followup/fixtures.py`（v2）、`src/gui_dna/suites.py`（v1） |
| 看评测器怎么比对 DOM 与状态 | `experiments/scale_study/evaluator.py` 的 `check()`；`src/gui_dna/evaluation.py` 的 `perform()` |
| 看统计口径 | `experiments/scale_study/analyze.py`：完整组筛选、`paired_interval()` |
| 加新模型/改价格上限 | `configs/*.json` 的 `models`、`model_price_caps`、`provider_order`；`provider.py` 会校验模型在目录中 |
| 渲染外壳与事件协议 | `src/gui_dna/assets/shell.html`（`window.__gui.{reset,dispatch,snapshot}`）、`src/gui_dna/prompts.py` 的 `INTERFACE` |
| 外部 benchmark 候选与探针 | `实验结果.md` 第 8 节；`experiments/webapp1k_probe.py`；`artifacts/benchmark-probe/summary.md` |
| 在 Web-Bench dom1 上跑 GUI-DNA | `test/webbench_dna/README.md`；`shell.html`、`library.py`（参考实现拆成的原子 + 变体）、`domain.py`（任务阶梯、`compile_plan`、提示词）、`evaluate.py`、`run.py`；官方测试在 `harness/dom1-tests/`；结论在 `实验结果.md` 第 11 节 |
| 在 TodoMVC 官方测试集上跑 GUI-DNA | `test/todomvc_dna/README.md`；`shell.html`（公开外壳与协议）、`library.py`（冻结原子，含语义变体）、`domain.py`（任务族、需求、`compile_plan`、提示词）、`evaluate.py`（公开冒烟 + 官方隐藏评测）、`run.py`；结果 `test/todomvc_dna/results/`；结论在 `实验结果.md` 第 10 节 |
| 改论文 | `DNA_latex/main.tex`（正文与附录）、`preamble.tex`（宏与标记）、`custom.bib`；表格数字对应 `实验结果.md` 第 4、10、11、12 节 |
| 下一个该做什么实验 | `experiments/TODO.md`（按收益/成本排序，含费用估算与入口命令） |
| 在 WebApp1K-Duo 上跑 GUI-DNA（扩大实验入口） | `test/webapp1k_dna/README.md`；`run.py`（三种做法）、`compiler.py`（计划检查 + 拼装）、`analyze.js`（babel 静态字符串）；结果 `test/webapp1k_dna/results/`；结论在 `实验结果.md` 第 9 节 |
