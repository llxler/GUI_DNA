# test/webapp1k_dna — 在公开 benchmark WebApp1K-Duo 上对比「自由代码」与「GUI-DNA 冻结原子函数组装」

目的：回答审稿人会问的「自建 16 个配置之外，本方法在广为人知的公开 benchmark 上有没有提升」。
本目录是**独立于第三轮冻结代码**的新实验阶段（不改 `experiments/scale_study/*`、`src/gui_dna/**`），
小预算先跑 10 个样本，额度充足时用同一套脚本扩到全部 1,000 个 Duo。

结果：[results/summary.md](results/summary.md)（2026-11-01 实跑，严格版编译器）、[results/summary-replay.md](results/summary-replay.md)
（放宽「自测选中字符串」检查后，对同一批已保存响应零成本 `--evaluate-only` 重放；仅 Qwen 一个任务变化）、[results/summary.json](results/summary.json)（原始数字）、
[results/library.json](results/library.json)（冻结原子函数库：源码、sha256、来源模型、是否通过各自公开单测）。
结论与讨论写在仓库根目录 [实验结果.md](../../实验结果.md) 第 9 节。

## 1. benchmark 与为什么选它

[WebApp1K](https://github.com/onekq/WebApp1k)（arXiv 2408.00019 / 2409.13773）：1,000 个单功能 React 任务，
每个任务 = 一份 Jest + React Testing Library 测试文件（即 prompt），官方评分 = 跑这份测试。
**WebApp1K-Duo** 把同类别内两个单功能测试拼成一份，要求一个模块同时满足两者。
这与本项目「原子 → 组合」的设定同构，评分确定、免费、能本地复现（CRA 5 / Jest 27）。
每个 Duo 任务 4 项断言，前两项属于原子 A、后两项属于原子 B，天然支持按功能归因。

## 2. 三种做法（同模型、同任务、同种子、同反馈协议）

| 做法 | 做什么 | 是否付费 |
|---|---|---|
| `free` 自由代码（常规方法） | 官方提示词「Generate X.js to pass the tests below … RETURN CODE ONLY」，模型直接写整个模块 | 是 |
| `rule` 规则组装（零 API 控制） | 不问模型：按文件名顺序把该模型自己的两个冻结原子挂到一个包装组件里 | 否 |
| `dna` GUI-DNA 组装方案 + 编译检查 | 模型只写 JSON 组装方案 `{select, order, relabel}`；`compile_plan` 静态检查后拼装冻结原子 | 是 |

- **冻结原子函数库**：每个单功能任务由各模型用官方提示词一次生成（来自 2026-10-30 的探针 `artifacts/benchmark-probe/runs/*/single/`），
  在各自公开单测上验证后冻结；库里每个原子有多个变体（`v1`=DeepSeek 来源，`v2`=Qwen 来源），prompt 里只给变体编号与源码，不给来源模型。
- **组装方案能做的事**：每个原子选一个变体；决定布局顺序；为避免两原子在测试选择器上撞车，可以改原子里**可见静态字符串**
  （JSX 文本、placeholder、aria-label、alt、title、data-testid）。原子逻辑不可改——编译器只按 `@babel/parser` 定位到的字面量区间做拼接替换，其余字节不动。
- **编译器静态检查**（只看公开测试文件与冻结库，不看任何隐藏信息）：结构合法；不得改掉本原子自己测试会选中的字符串；
  **跨原子选择器碰撞**——原子 X 测试里用到的任何 `getByText/LabelText/PlaceholderText/TestId/Role` 选择器都不得命中原子 Y 的静态字符串。
  这正是自由代码基线里观察到的失败形态（Qwen 的 `getByText(/Edit/i)` 同时命中标题和按钮）。运行期字符串（如 `setMessage('Failed …')`）的潜在碰撞只作为警告回传。
- **反馈协议**：三种做法一致——公开 Jest 失败（断言标题 + 失败信息）或编译拒绝回传给模型，最多 `--max-repairs`（默认 2）轮；`rule` 没有模型可修。
- **账本**：`artifacts/webapp1k-dna/budget.sqlite3`，独立于第三轮账本与探针账本，上限 `--cap-usd 1.0`。

## 3. 运行

```bash
# 前置：WebApp1k 官方仓库与钉版本依赖（见 experiments/webapp1k_probe.py 顶部注释）
#   git clone --depth 1 https://github.com/onekq/WebApp1k.git artifacts/benchmark-probe/WebApp1k
#   (cd artifacts/benchmark-probe/WebApp1k/staging && npm install && npm install react-router-dom@6 node-fetch@2)

uv run pytest test/webapp1k_dna -q                     # 编译器离线测试（不花钱、不跑 Jest）
uv run python -m test.webapp1k_dna.run --arms rule     # 零 API：建库 + 规则组装 + Jest 评分
export OPENROUTER_API_KEY=...
uv run python -m test.webapp1k_dna.run --arms free rule dna            # 本次 10 样本设置（默认参数）
uv run python -m test.webapp1k_dna.run --evaluate-only                 # 只重新评分已保存输出（改了编译器后用）
uv run python -m test.webapp1k_dna.run --summarize-only                # 只从 record.json 重建 summary
```
重放到新目录而不覆盖原始运行：`cp -r artifacts/webapp1k-dna/{runs,library.json} artifacts/<new>/ && ... --evaluate-only --out artifacts/<new> --label <tag>`。

默认：`--models deepseek/deepseek-v4-pro-0813 qwen/qwen3-coder --categories blogging taskmanagement --per-category 5 --max-repairs 2 --seed 20261101`。
已有 `record.json` 的任务直接复用，不重复付费；改配置请换 `--out`。

## 4. 额度充足时怎么扩成完整实验

1. `--per-category 50`（WebApp1K-Duo 每类 50 个，20 类 = 1,000）并加 `--categories`；缺的原子会用官方提示词生成（付费）并在各自单测上验证后入库。
   成本量级：探针实测每次调用 < $0.003，1,000 个 Duo × 两条付费做法 × ≤3 次 ≈ $10–20/模型；Jest 评分免费但约 10 s/次。
2. 先清洗不可满足用例（见 实验结果.md 8.3：`postPerformanceReport` 在 fetch-mock 9 下任何实现都 0/2）。
3. 加 `plan_unchecked` 消融：`compile_plan(..., checked=False)` 已实现，在 `run.py` 里加一种做法即可（第三轮同款对照）。
4. Trio / Quartet（每类 50 个）：`compile_plan` 对原子数无假设；`selectors_by_atom` 的「前后各半」切分需改成按原子数等分。
5. 统计口径沿用第三轮：配对比较（同任务下 dna 与 free 的通过差），`experiments/scale_study/analyze.py` 的 `paired_interval()` 可直接复用。

## 5. 还不能确认的是

- 这里的「组装方案」内容很薄（选变体、排顺序、偶尔改标签），原子函数组装本身由编译器完成；提升主要来自**冻结已验证原子 + 静态碰撞检查**，
  `rule` 做法与 `dna` 做法的差距才是「模型写组装方案」的边际贡献。
- 原子是模型自己一次生成的，不是人工库；Duo 测试恰好是两份单测的逐字拼接，所以「原子各自通过 ⇒ 组合通过」几乎只差跨原子干扰。
  更难的组合（Trio/Quartet、共享状态的需求）才是方法的真正考验，本次未覆盖。
- 10 个样本不能给出统计显著性；强模型在这 10 个任务上本来就接近天花板。
