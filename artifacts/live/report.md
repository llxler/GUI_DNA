# GUI DNA 组合实验

模型候选先通过公开检查与最多两轮修复，然后冻结。所有生成调用结束后才运行隐藏测试。

方法限制：自动契约归纳在开发校验中失败，最终函数库学习使用开发参考实现的人工契约注释作为种子，再做浏览器验证。此实验检验附加这些约束的效果，不能证明模型自主发现契约的能力。失败学习费用包含在项目总成本中。

完整四方法配对组：32；未完成组：0。以下统计仅包含完整组，所有部分结果仍保留于 results.json。

| 模型 | 方法 | 组合任务通过 | 基础功能保留 | 可运行 | 生成费用 USD | 平均秒数 | 修复次数 |
|---|---|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v3.2 | direct | 12/16 (75.0%) | 83.3% | 100.0% | 0.031777 | 129.6 | 17 |
| deepseek/deepseek-v3.2 | retrieval | 15/16 (93.8%) | 97.2% | 100.0% | 0.021696 | 71.0 | 8 |
| deepseek/deepseek-v3.2 | dna | 16/16 (100.0%) | 100.0% | 100.0% | 0.012212 | 49.4 | 1 |
| deepseek/deepseek-v3.2 | constrained | 16/16 (100.0%) | 100.0% | 100.0% | 0.014648 | 52.2 | 0 |
| qwen/qwen3-coder-30b-a3b-instruct | direct | 2/16 (12.5%) | 11.1% | 100.0% | 0.111735 | 36.1 | 29 |
| qwen/qwen3-coder-30b-a3b-instruct | retrieval | 8/16 (50.0%) | 55.6% | 100.0% | 0.080669 | 24.1 | 18 |
| qwen/qwen3-coder-30b-a3b-instruct | dna | 15/16 (93.8%) | 94.4% | 100.0% | 0.038746 | 15.6 | 4 |
| qwen/qwen3-coder-30b-a3b-instruct | constrained | 15/16 (93.8%) | 94.4% | 100.0% | 0.053302 | 18.6 | 10 |

组合任务通过：该候选全部隐藏单功能、组合与边界场景通过。基础功能保留：组合候选中独立功能场景通过数 / 总场景数。可运行：页面可加载且操作无 JavaScript 运行异常；行为错误可以仍然可运行。耗时包含生成、公开检查、修复和最终隐藏评测，不含函数库构建。

项目账本已结算费用 **$0.424867**，其中函数库构建 **$0.060082**（单独记录，只计一次）。包含未结算预留的最大记账敞口 $0.496063；未结算调用 2。表中生成费用不含函数库；项目总成本包含全部已结算调用及其他/部分运行。金额按调用向上取整到微美元。

- deepseek/deepseek-v3.2：约束方法相对 dna，胜 0 / 负 0 / 平 16。
- deepseek/deepseek-v3.2：约束方法相对 retrieval，胜 1 / 负 0 / 平 15。
- deepseek/deepseek-v3.2：约束方法相对 direct，胜 4 / 负 0 / 平 12。
- qwen/qwen3-coder-30b-a3b-instruct：约束方法相对 dna，胜 0 / 负 0 / 平 16。
- qwen/qwen3-coder-30b-a3b-instruct：约束方法相对 retrieval，胜 7 / 负 0 / 平 9。
- qwen/qwen3-coder-30b-a3b-instruct：约束方法相对 direct，胜 13 / 负 0 / 平 3。

只有两个模型中 constrained 都高于 dna 和 retrieval、且基础功能保留率不下降，才将结果视为继续研究的积极信号。持平或下降按负结果报告。每个任务仅两次采样，固定模板和窄领域可能导致天花板效应；本实验不提供统计显著性或独特性主张。

失败证据（全部轨迹与截图见各候选 hidden 目录）：

- qwen/qwen3-coder-30b-a3b-instruct / direct / test-search-pagination / base-search：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}, {'id': 115, 'name': 'Basil', 'category'。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-search-pagination/repeat-0/direct/hidden/base-search.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-search-pagination / base-pagination：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}, {'id': 115, 'name': 'Basil', 'category'。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-search-pagination/repeat-0/direct/hidden/base-pagination.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-search-pagination / heldout-order-1：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}, {'id': 115, 'name': 'Basil', 'category'。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-search-pagination/repeat-0/direct/hidden/heldout-order-1.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-search-pagination / heldout-order-2：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}, {'id': 115, 'name': 'Basil', 'category'。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-search-pagination/repeat-0/direct/hidden/heldout-order-2.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-search-pagination / alternate-page-size：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}], got [{'id': 101, 'name': 'alpine', 'ca。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-search-pagination/repeat-0/direct/hidden/alternate-page-size.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-filter-pagination / base-filter：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}, {'id': 115, 'name': 'Basil', 'category'。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-filter-pagination/repeat-0/direct/hidden/base-filter.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-filter-pagination / base-pagination：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}, {'id': 115, 'name': 'Basil', 'category'。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-filter-pagination/repeat-0/direct/hidden/base-pagination.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-filter-pagination / heldout-order-1：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}, {'id': 115, 'name': 'Basil', 'category'。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-filter-pagination/repeat-0/direct/hidden/heldout-order-1.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-filter-pagination / heldout-order-2：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}, {'id': 115, 'name': 'Basil', 'category'。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-filter-pagination/repeat-0/direct/hidden/heldout-order-2.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-filter-pagination / alternate-page-size：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}], got [{'id': 101, 'name': 'alpine', 'ca。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-filter-pagination/repeat-0/direct/hidden/alternate-page-size.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-edit-filter / base-edit：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}, {'id': 115, 'name': 'Basil', 'category'。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-edit-filter/repeat-0/direct/hidden/base-edit.png。
- qwen/qwen3-coder-30b-a3b-instruct / direct / test-edit-filter / base-filter：view.items: expected [{'id': 101, 'name': 'alpine', 'category': 'A', 'score': 0}, {'id': 108, 'name': 'ALPHA', 'category': 'A', 'score': 8}, {'id': 115, 'name': 'Basil', 'category'。截图：/home/lxler/work/gui_test/artifacts/live/runs/qwen__qwen3-coder-30b-a3b-instruct/test-edit-filter/repeat-0/direct/hidden/base-filter.png。
