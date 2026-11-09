# 实验 TODO（论文主表补强）

给 AI 编码代理和人看的**待做实验清单**。规则：

1. 每次开工先读本文件，挑一项，先查余额（`uv run python scripts/check_openrouter_credits.py --required-usd <预算>`），付费项目要用户点头。
2. 做完一项：结果写进 `实验结果.md`（追加一节或补进第 12 节汇总表），论文 `DNA_latex/main.tex` 同步改数字，然后**把该项从本文件删掉**（不要留「已完成」条目，历史在 git 和 `实验结果.md` 里）。
3. 新阶段用新的 `--out` 目录和独立账本（`artifacts/<stage>/budget.sqlite3`），不碰冻结文件（见 AGENTS.md 第 4 节）。
4. 费用估算基于已结算账本（`实验结果.md` 第 11 节、各 `results/summary.json` 的 `cost_usd`），实际以账本为准。余额 2026-11-09 收工时：约 $13.7（用户要求本轮之后不再花 API 费用）。

按「对主表的帮助 / 成本」排序。主表 = 论文 `tab:main`（四个数据集 × 五种做法 × 配对）与 `tab:models`（逐模型）。

## A. 零成本（只算不跑）


## B. 付费、便宜（≤ $2）

- [ ] **方案提示词敏感性**（TodoMVC + Web-Bench，4 个便宜模型）：去掉原子描述只留签名 / 打乱原子顺序 / 不给变体说明，看选变体的正确率是否变化。估 $0.3。需要在 `test/*/domain.py` 加一个开关（不改默认行为）。

## C. 付费、中等（$2–5）

- [ ] **WebApp1K-Duo 扩到 ≥100 个 Duo**（Qwen3 Coder 这类会出组合错误的模型 + 一个强模型）：先清洗不可满足用例（`postPerformanceReport` 类），再加 `plan_unchecked` 对照。估 $3–6/模型。入口 `test/webapp1k_dna/README.md` 第 4 节。

## D. 付费或高工时、大（> $5 或 > 1 天）

- [ ] **第二个 Web-Bench 项目**：选一个原生 DOM / 列表类项目（候选：`dom2`、`form*`、`table*`，先看 `artifacts/web-bench/projects/*/tasks.jsonl` 与参考实现规模），把参考实现拆成原子库 + 变体（工时 0.5–1 天），8 模型 Free vs GUI-DNA 估 $2–3。这是对「只做了 1/50 个项目」最直接的回应。
- [ ] **盲建库实验**（论文认为最重要的缺失实验）：不看隐藏测试，只用需求句子 + 公开冒烟检查让一个强模型写原子并冻结（TodoMVC 最合适：24 个原子、需求是公开规范），再用弱模型写方案。估 $1–2 + 设计工时。回答「库是否必须人工给」。
- [ ] **第三轮续跑**：Qwen3 Coder Plus 已下线，只能另立阶段换 `qwen/qwen3-coder` 等模型补 450 个候选。估 $2–3。价值：List-16 的 n 从 47 到 160；但规则解析满分的边界不变。
