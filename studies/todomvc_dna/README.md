# test/todomvc_dna — 在 TodoMVC 规范 + 官方 Playwright 测试集上对比「自由代码」与「GUI-DNA 冻结原子函数组装」

为什么换这个数据集：WebApp1K-Duo 的两个功能互不相干，组合只是并排挂载，强模型本来就接近天花板（见 实验结果.md 第 9 节）。
本仓库 `data/dev/` 里的任务之所以适合本方法，是因为功能之间**通过共享状态互相影响**（搜索重置页码、排序平局、撤销恢复位置……），
错误集中在组装语义而不是单个功能的实现。TodoMVC 正是这种结构：切换完成状态会影响计数、「全选」复选框、「清除已完成」按钮和当前筛选视图；
编辑的保存/取消/清空各有规定；持久化贯穿所有操作。它是最广为人知的前端规范，官方网站明确称可作「AI 编码代理的可测基准 prompt」。

## 1. 外部材料（不改动）

| 材料 | 来源 | 用途 |
|---|---|---|
| 需求文本 | TodoMVC 应用规范 `app-spec.md`「Functionality」各节（tastejs/todomvc） | 按任务启用的功能拼成 requirement，三种做法字节相同 |
| 隐藏测试 | Playwright 官方 TodoMVC 示例测试 `demo-todo-app.spec.ts`（create-playwright 1.17.129 附带，24 项） | 只在评测时运行；标题与内容从不进入提示词（有测试保证） |

`harness/demo-todo-app.original.spec.ts` 是原件；`harness/demo-todo-app.spec.ts` 唯一的改动是把 `page.goto('https://demo.playwright.dev/todomvc')`
换成 `page.goto(process.env.CANDIDATE_URL)`，以便指向本地候选页面（有测试断言只差这一行）。测试里用的 `localStorage['react-todos']` 键和
`todo-item` / `todo-title` / `todo-count` 测试 id 来自官方示例应用，作为公开接口写进 shell 与需求。

## 2. 三种做法（同任务、同种子、同反馈协议）

- 公开外壳 `shell.html`：负责全部 DOM 与事件（新建、勾选、全选、双击编辑、Enter/blur 保存、Escape 取消、清除已完成、hash 路由），
  只调用候选的 `window.candidate = { init, reduce, select }`；状态/事件/视图协议写在文件头，所有做法看到同一份。
- `free` 自由代码（常规方法）：模型按需求与协议直接写 `init/reduce/select`。
- `rule` 规则组装（零 API 控制）：每个启用槽位取库里**字母序第一个**允许的函数，不读需求。
- `dna` GUI-DNA：模型只写 JSON 组装方案 `{init, handlers, after, view}`，`compile_plan` 做特征感知链接 + 覆盖检查（每个启用事件、每个启用视图槽位都要有允许的函数；
  禁用功能的路由静默丢弃），然后逐字拼接冻结函数体。
- 冻结原子函数库 `library.py`（人工编写，24 个函数）：对同一槽位故意保留语义不同的变体（如 `saveRaw` / `saveTrimDelete`、`toggleAllComplete` / `toggleAllMatch`、
  `initEmpty` / `initFromStorage`、`visibleAll` / `visibleByFilter`），需求文本决定哪个正确，所以方案必须读规范。
- 任务：8 个功能族（`domain.FAMILIES`），核心 = 新建 + 持久化；隐藏评测取官方 24 项中「所需功能 ⊆ 启用功能」的子集（4–24 项）。
- 两个对照（2026-11-03）：`free_lib` 自由代码 + 同一函数库（函数原样放进提示词，随便用）；`dna_unchecked` 方案不做覆盖检查（`compile_plan(..., checked=False)`）。
- 反馈：公开冒烟检查（页面错误、添加一条后列表与 localStorage 是否正确）或编译拒绝回传，最多 2 轮修复；隐藏测试在全部生成结束后对首次与最终版本各评一次。
- 校准：按规范写出的正确方案 24/24；规则控制 16/24（失败的正是需要读规范的槽位）。

## 3. 运行

```bash
# 首次：安装 Node 侧测试运行器（版本钉到与 python playwright 相同，复用 ~/.cache/ms-playwright 里的浏览器）
(cd test/todomvc_dna/harness && npm install)
uv run pytest test/todomvc_dna -q                          # 离线检查（映射完整性、编译器、提示词边界）
uv run python -m test.todomvc_dna.run --arms rule          # 零 API：规则组装 + 官方测试评分
export OPENROUTER_API_KEY=...
uv run python -m test.todomvc_dna.run --arms free rule dna --samples 2     # 本次设置
uv run python -m test.todomvc_dna.run --evaluate-only                      # 只重新评分已保存版本
```

跑过的 8 个模型见 `results/summary.md`。OpenAI 模型要经 `test/provider_ext.py`（允许最低强度推理、去掉 GPT-5 不接受的温度/种子参数）。账本只能收紧不能放宽，所以每次扩展都用新的 `--out` 目录（`artifacts/todomvc-dna-2/3/4`），把上一轮的 `runs/` 拷进去（已有记录直接复用、不再付费），费用列用 `--extra-ledgers` 把旧账本加总；账本 `artifacts/todomvc-dna/budget.sqlite3`（上限 $1）。
结果：[results/summary.md](results/summary.md)（四个模型，编译器含两处格式放宽后的零成本重放）、[results/summary-strict-compiler.md](results/summary-strict-compiler.md)
（DeepSeek/Qwen 的严格版实跑）；结论写在 实验结果.md 第 10 节。`--recompile` 会把 dna 组已保存的响应用当前编译器重新链接并重评，不花钱；
实跑记录保留为 `record.live.json`。

## 4. 扩大实验

- `--samples N` 提高每族样本数；加功能族只需改 `domain.FAMILIES`；统计口径可直接复用第三轮的 `paired_interval()`。
- 加语义变体（像第三轮那样让规范本身变化）需要同时改需求文本与库，但**官方测试集固定了语义**，变体只能作为干扰项存在。
- 加 `checked=False` 消融对照：`compile_plan(..., checked=False)` 已实现。
