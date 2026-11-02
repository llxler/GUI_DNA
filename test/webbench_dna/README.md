# test/webbench_dna — 在 Web-Bench（字节跳动，2025）的 dom1 项目上对比「自由增量代码」与「GUI-DNA 冻结原子函数组装」

[Web-Bench](https://github.com/bytedance/web-bench)（arXiv 2505.07473）是近两年最热的 Web 开发 benchmark 之一：50 个项目 × 20 个**顺序依赖**任务，
官方 Playwright 测试，公开榜单，SOTA 模型 pass@1 也只有二三成。这里取 `dom1` 项目（单文件文件管理器：新建文件/目录、选中、删除、拖拽、右键菜单、
复制粘贴、重命名、导入导出、编辑自动保存、快捷键、生成、侧栏拖宽、过滤、剪切），任务之间通过共享状态强耦合，与 `data/dev/` 的结构同构。

## 1. 外部材料（不改动）

| 材料 | 来源 | 用途 |
|---|---|---|
| 任务描述 | `projects/dom1/tasks.jsonl`（逐字） | 任务 k 的需求 = 官方描述 1..k |
| 隐藏测试 | `projects/dom1/test/*.spec.js`（21 个文件、85 项，逐字复制到 `harness/dom1-tests/`，有测试断言哈希一致） | 官方 `task-k.spec.js` 评任务 k |
| 测试工具库 | `libraries/test-util`（Apache-2.0，去掉了嵌套依赖） | 官方测试 `require('@web-bench/test-util')` |
| 初始页面 | `projects/dom1/src-init/index.html` | 自由代码组的起点（基准协议） |
| 参考实现 | `projects/dom1/src`（Apache-2.0） | **拆成冻结原子函数库** `library.py`，并加入语义变体 |

运行器 `harness/playwright.config.js` 只换掉了官方配置的服务方式（我们自己起静态服务、`CANDIDATE_URL` 指向候选目录），超时 12 s / 3 s。
校准：参考实现 21/21 文件通过；按规范写出的正确方案 20/20 任务；不读需求的规则控制 8/20。

## 2. 三种做法

- `free` 自由增量代码（基准协议）：从官方初始页面开始，任务 k 给模型「当前 index.html + 任务 k 描述」，返回整个文件；输出带到任务 k+1。
- `rule` 规则组装（零 API）：每个必需项都接上，有变体的槽位取字母序第一个，不读需求。
- `dna` GUI-DNA：模型只写组装方案 `{tools, select, fileClick, insert, delete, drag, menuLabel, menu, shortcuts, autosave, resizer, resizerDrag, filter}`，
  `compile_plan` 做特征感知链接（禁用功能的项静默丢弃）+ 覆盖检查（启用功能必须接上）后逐字拼接冻结原子，注入公开外壳 `shell.html`（只有布局 CSS 与空的 tools/entries/editor）。
- 语义变体（需求句子决定正确项）：选中是否切换目录展开、点击文件是否打开到编辑器、新建插入位置（选中文件之后/目录内 vs 一律追加）、
  删除后选中下一个/上一个/父目录 vs 不选中、拖放左半/右半规则 vs 一律追加、菜单项是否显示快捷键。
- 公开反馈：页面/控制台错误 + 每个工具按钮点一次不报错；最多 2 轮修复。隐藏测试在全部生成结束后对首次与最终版本各评一次。
- 报告两种口径：独立任务通过数 /20；基准顺序分（按顺序累计、连续两次失败即停）。

## 3. 运行

```bash
(cd test/webbench_dna/harness && npm install)                 # @playwright/test 1.63.0 + 本地 test-util
uv run pytest test/webbench_dna -q
uv run python -m test.webbench_dna.run --arms rule            # 零 API
export OPENROUTER_API_KEY=...
uv run python -m test.webbench_dna.run --arms free rule dna --models qwen/qwen3-coder-30b-a3b-instruct mistralai/mistral-small-3.2-24b-instruct google/gemma-3-12b-it deepseek/deepseek-v4-flash
uv run python -m test.webbench_dna.run --evaluate-only
```

账本 `artifacts/webbench-dna/budget.sqlite3`（上限 $1.5）。结果 [results/summary.md](results/summary.md)；结论在 实验结果.md 第 11 节。

## 4. 还不能确认的是

- 原子函数库来自 benchmark 自带的参考实现：这里证明的是「弱模型能否按 20 条需求把一个已验证的库接对」，不是「模型能否实现这些功能」。
- 外壳承担了布局；拖拽、右键菜单、调宽的 DOM 机制在原子里。自由代码要从零写全部 DOM/CSS/JS，这是基准本身的设定。
- 只做了 50 个项目中的 1 个；扩到其他项目需要为每个项目拆一套库。
