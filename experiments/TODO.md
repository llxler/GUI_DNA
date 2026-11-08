# 实验 TODO（论文主表补强）

给 AI 编码代理和人看的**待做实验清单**。规则：

1. 每次开工先读本文件，挑一项，先查余额（`uv run python scripts/check_openrouter_credits.py --required-usd <预算>`），付费项目要用户点头。
2. 做完一项：结果写进 `实验结果.md`（追加一节或补进第 12 节汇总表），论文 `DNA_latex/main.tex` 同步改数字，然后**把该项从本文件删掉**（不要留「已完成」条目，历史在 git 和 `实验结果.md` 里）。
3. 新阶段用新的 `--out` 目录和独立账本（`artifacts/<stage>/budget.sqlite3`），不碰冻结文件（见 AGENTS.md 第 4 节）。
4. 费用估算基于已结算账本（`实验结果.md` 第 11 节、各 `results/summary.json` 的 `cost_usd`），实际以账本为准。余额 2026-11-08：约 $21.4。

按「对主表的帮助 / 成本」排序。主表 = 论文 `tab:main`（四个数据集 × 五种做法 × 配对）与 `tab:models`（逐模型）。

## A. 零成本（只算不跑）

- [ ] **提示词附录**：把四个数据集每种做法的 system / user 提示词逐字导出成 LaTeX 附录（`app:prompts` 目前是 TODO）。入口：`experiments/scale_study/domain.py: messages_for`，`test/todomvc_dna/domain.py`，`test/webbench_dna/domain.py: messages_for / free_messages`，`test/webapp1k_dna/run.py`。写一个导出脚本放 `test/export_prompts.py`，输出到 `DNA_latex/prompts.tex`（本地）。
- [ ] **编译器放宽的时间线**：从 `artifacts/todomvc-dna*/runs/**/record.live.json` 与 `artifacts/webapp1k-dna*/` 的时间戳整理「每次放宽在哪些模型跑完之后引入」，填 `app:relax` 的 TODO。
- [ ] **费用表重算**：`tab:cost` 的合计标了 TODO；用各账本 `Ledger.summary()` 重算（第一轮 / 第二轮 / 第三轮 / Duo / TodoMVC / Web-Bench 各阶段，含 `-2/-3/-4/-5` 目录），写进 `实验结果.md` 第 5 节与论文。
- [ ] **修复预算消融（K=0 vs K=2）**：现有数据已含首次与最终版本，按数据集 × 做法整理「首次即对 / 修复后才对 / 修复也不对」三分表，比单独的 first/final 列更能说明「收益在修复阶段还是首次」。

## B. 付费、便宜（≤ $2）

- [ ] **TodoMVC 每族采样 2 → 5**（Free 与 GUI-DNA，8 模型）：n 从 128 到 320，弱模型差距的区间会收窄。估 $0.6–1.0。命令：复制 `artifacts/todomvc-dna-4/runs` 到 `artifacts/todomvc-dna-5/runs` 后 `uv run python -m test.todomvc_dna.run --arms free dna --samples 5 --models <8 个> --out artifacts/todomvc-dna-5 --extra-ledgers artifacts/todomvc-dna*/budget.sqlite3`。注意 `--samples` 是每族总数，已有样本直接复用。
- [ ] **Web-Bench 强模型多种子（Free+Lib vs GUI-DNA）**：2026-11-08 补全后，四个较强模型「自由 + 同一函数库」68/80 对方案 73/80，GPT-OSS 还反超 1 个任务；再跑 2 个种子的 `free_lib` 与 `dna`（Gemini Flash、Haiku、GPT-5-mini、GPT-OSS）看 +5/80 是否稳定，并看 Free+Lib 在任务 9/20（复制粘贴、剪切）的失败是否系统性。估 $2.5（Haiku 的 free_lib 一轮 $0.9）。
- [ ] **Web-Bench 弱模型多种子**：Qwen / Mistral / Gemma / DeepSeek Flash 的 Free 与 GUI-DNA 再跑 2 个种子，回答「一个样本/任务」的质疑。估 $0.4。`--seed` 改值、`--out artifacts/webbench-dna-seed<k>`。
- [ ] **方案提示词敏感性**（TodoMVC + Web-Bench，4 个便宜模型）：去掉原子描述只留签名 / 打乱原子顺序 / 不给变体说明，看选变体的正确率是否变化。估 $0.3。需要在 `test/*/domain.py` 加一个开关（不改默认行为）。

## C. 付费、中等（$2–5）

- [ ] **前沿模型上 Web-Bench dom1**（论文 Limitations 的 TODO）：Gemini 2.5 Pro（估 $1.5–2）或 GPT-5（估 $2）或 Claude Sonnet 4.5（估 $4）各跑 Free 与 GUI-DNA。回答「差距是否只存在于 Flash/Haiku/mini 级」。注意 `model_price_caps` 要在 `test/webbench_dna/run.py` 的 config 里补上该模型的价格上限，OpenAI 模型经 `test/provider_ext.py`。
- [ ] **WebApp1K-Duo 扩到 ≥100 个 Duo**（Qwen3 Coder 这类会出组合错误的模型 + 一个强模型）：先清洗不可满足用例（`postPerformanceReport` 类），再加 `plan_unchecked` 对照。估 $3–6/模型。入口 `test/webapp1k_dna/README.md` 第 4 节。

## D. 付费或高工时、大（> $5 或 > 1 天）

- [ ] **第二个 Web-Bench 项目**：选一个原生 DOM / 列表类项目（候选：`dom2`、`form*`、`table*`，先看 `artifacts/web-bench/projects/*/tasks.jsonl` 与参考实现规模），把参考实现拆成原子库 + 变体（工时 0.5–1 天），8 模型 Free vs GUI-DNA 估 $2–3。这是对「只做了 1/50 个项目」最直接的回应。
- [ ] **盲建库实验**（论文认为最重要的缺失实验）：不看隐藏测试，只用需求句子 + 公开冒烟检查让一个强模型写原子并冻结（TodoMVC 最合适：24 个原子、需求是公开规范），再用弱模型写方案。估 $1–2 + 设计工时。回答「库是否必须人工给」。
- [ ] **第三轮续跑**：Qwen3 Coder Plus 已下线，只能另立阶段换 `qwen/qwen3-coder` 等模型补 450 个候选。估 $2–3。价值：List-16 的 n 从 47 到 160；但规则解析满分的边界不变。
