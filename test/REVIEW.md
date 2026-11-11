# 第 0 节审稿问题的复验入口

结论统一见 [`实验结果.md` 第 16 节](../实验结果.md)，未解决的问题见 [`experiments/TODO.md`](../experiments/TODO.md)。这里记录复现流程，避免把探索性检查误作新主实验。

## 只读汇总与本地复验

```bash
uv run python -m test.review_checks
uv run python -m test.review_metrics
uv run python -m test.random_plans --report
uv run python -m test.ledger_read artifacts/todomvc-blind-2/budget.sqlite3
uv run python -m test.name_sensitivity --no-generate --out artifacts/name-sensitivity-2 --extra-ledgers artifacts/name-sensitivity/budget.sqlite3
uv run python -m test.blind_library --summary --out artifacts/todomvc-blind-2 --extra-ledgers artifacts/todomvc-blind/budget.sqlite3 --planners qwen/qwen3-coder-30b-a3b-instruct mistralai/mistral-small-3.2-24b-instruct deepseek/deepseek-v4-pro-0813 openai/gpt-oss-120b
uv run python -m test.webbench_dna.continue_clean_prefix --no-generate
```

这些汇总入口使用只读账本。**不要为了看费用用很小的 cap 创建 `Ledger` 实例**：它会永久收紧已有阶段的上限。接手时 `todomvc-blind` 和 `name-sensitivity` 已遇到这一问题，本轮另立 `-2` 阶段，复制原始候选并通过 `--extra-ledgers` 复用已结算响应。旧账本不放宽；新目录的 `continuation.json` 记录复制来源和传输失败的归档。

下面只调用本地浏览器，不调用模型。TodoMVC 可在首个官方断言失败后停止，得到准确的「任务全过/不过」；不能把未执行测试当通过，也不汇报这种记录的测试级平均分。

```bash
uv run python -m test.random_plans --suite webbench --workers 3 --browser-workers 1
uv run python -m test.random_plans --suite todomvc --workers 3 --browser-workers 1
WORKERS=1 uv run python -m test.grade_review --stage artifacts/name-sensitivity-2 --workers 3
WORKERS=1 uv run python -m test.grade_review --stage artifacts/todomvc-blind-2 --workers 3
WORKERS=1 uv run python -m test.plan_counterfactuals --workers 1
uv run python -m test.webbench_dna.review_evaluate --stage artifacts/webbench-dna-clean-2 --workers 3
uv run --with matplotlib python -m test.failure_figure
uv run --with matplotlib python -m test.webbench_dna.taskmap_figure
uv run python -m test.export_review_snapshot
```

`taskmap_figure` 默认排除 Web-Bench 传输缺失的 Gemma；`--include-gemma` 可重画历史八模型图。最后一个命令仅准备本地匿名源码与汇总快照，不上传，不包含完整原始候选/响应/账本。匿名历史复验数据包仍需按 TODO 的 R11 单独完成。

## 付费阶段的固定范围

用户本轮明确授权总额不超过 $10。预算汇总保守计入接手前两个阶段的已结算与未确认预留，再加新账本的最大上限，始终不超过 $9.905890；未确认预留不等于已结算费用。新的授权不适用于继续第三轮或任意扩展实验。

| 新阶段 | 内容 | cap / stop（美元） |
|---|---|---:|
| `todomvc-blind-2` | 两个已冻结模型库 × 四个规划模型 × 两种做法 × 16 候选 | 2.80 / 2.60 |
| `name-sensitivity-2` | 补齐两套数据上四模型、四种提示词干预 | 0.35 / 0.30 |
| `webbench-dna-clean` | 六模型 × 20 任务 × 参考前缀代码/增量方案 | 2.40 / 2.30 |
| `webbench-dna-clean-2` | 复制有效记录；重做断连候选，Mistral 新调用改用官方供应商 | 0.85 / 0.80 |
| `webbench-dna-frontier-lib` | GPT-5 自由代码 + 同一函数库，20 任务 | 2.80 / 2.65 |

审稿专用生成脚本在发出新调用前写 `review-manifest.json`，校验配置、生成脚本和库的哈希。后续修改生成逻辑须另立阶段。先生成整组再隐藏评分；接手前已经产生的少量隐藏评分保留，但没有用于改库、改提示词或模型修复。GPT-5 对照沿用原运行器的清单与账本控制。源文件头部的简写不改变以下解释边界。

## 必须保留的解释边界

- **随机对照有条件**：只随机变体；菜单、快捷键、钩子等固定为参考方案。规则方案的变体投影不等于完整规则方案。
- **槽位一致不等于行为正确**：比较参考名字只度量参考一致率；同一任务的测试可能接受多个实现。最终方案必须从实际执行的版本回溯，不能误用后来被拒的提案。
- **建库只对测试文本盲**：建库模型看不到官方测试或参考函数，但获得人工固定槽位、功能标签与外壳协议。本次不是自动发现接口，也不能排除预训练见过公开 TodoMVC。
- **参考前缀有混杂**：前缀通过其上一任务的官方测试，未证明所有历史规格同时成立。相较自己上一版代码，参考代码还改变质量和表示，差值不能当作错误继承的因果占比。增量方案仍看到累计功能/槽位列表，所以“只给当前需求”并不等于两组全部信息等价。
- **统计单位有限**：任务相关、模型也可能相关；McNemar/符号检验仅作探索，按模型 bootstrap 仍不能证明跨项目推广。
- **缺失不是模型失败**：传输失败与评测器失败单独列出；只在有效共同候选上配对。旧主表和事后菜单/变体干预的分数均不覆盖。
- **成本口径分开**：报告生成调用、建库调用、未确认预留；人工工时没有记录，本地浏览器计算不折算为零成本生产开销。

本轮复评另外统一重跑了接手前使用旧 TodoMVC 全套评分器的缓存（名称干预 22 个版本、建库对照 20 个版本），而非只重跑失败项。旧评分保存在 `hidden-before-review-*.json`；排除了页面加载超时造成的假失败。评分器临时输出改为候选目录内的独立路径，官方断言与超时不变。Web-Bench 续跑可由 `test/webbench_dna/review_evaluate.py` 用独立临时目录并行评分；用已保存的通过/失败页面核对原评分一致。原续跑入口的串行评分保留作兼容路径。

当前用户要求本轮到此停止，所有实验进程已退出。Qwen 参考前缀 task-16 的末次候选先收到 12,000 tokens 的截断响应，随后修复调用断连；已保存 `record.json`（无可执行版本），保留所有传输重试和费用预留。`interruption-correction.json` 更正了过程中错指已结算调用的操作说明。该候选在四种协议的共同子集中统一排除，n=119；不是模型最终失败。下次续做流程见 TODO P1a，未获用户续做指示前不要重启生成。
