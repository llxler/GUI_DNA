# WebGen-Bench 组件建库与跨站验证

原六站用于开发建库方法，每类按同一哈希规则预选的第三站用于验证。方法、站点、实际页面和逐项判决都能从结果索引追到对应的生成批次。一个模型在一个站点只交付一份配置，各库共用；同一份页面只评一次。两批站点和分母独立。[结果索引](../../results/component-validation-20261127.json)

| 要核对的问题 | 代码与记录 |
|---|---|
| 库与子组件之间首先在哪里中断？ | [公开输入及单元检查](PROTOCOL.md)、[保留导航与内容挂载点](function_bodies/PROTOCOL.md) |
| 同一模型修改了哪一行？ | [具名参数](typed_inputs/PROTOCOL.md)、[DOM 探针校正](typed_inputs/FRAGMENT_REPLAY.md)、[原作者修改表达式](typed_inputs/LOCAL_EDITS.md) |
| 为什么 Qwen 的弹窗与反馈后来可见？ | [同模型先渲染子组件](typed_inputs/DOM_INPUTS.md)、[检查打开状态及独立反馈元素](typed_inputs/NATIVE_VISIBILITY.md) |
| Flash 的跨站验证是否重新建库？ | [六站旧库的字节核验及新三站部署](../heldout_transfer/PROTOCOL.md) |
| 如何核对截断的从零页面？ | [浏览器原生 HTML 接收规则及同题复评](../heldout_transfer/incomplete_html/PROTOCOL.md) |
| 如何复算分数和费用？ | [逐站配对与账本归属](report.py)。仓库根目录运行 `uv run python -m studies.webgen_bench.component_contracts.report`。有本地原始账本时可加 `--ledgers`。 |

各阶段保留独立候选和判决以区分实际修改、未准入及服务缺失。读主结果时使用索引里的 `webgen.cohorts.development` 或 `webgen.cohorts.holdout`，再选模型 ID 与 `methods`。每种方法的 `sources` 同时给出配置候选与正式判决的位置。

开发六站新增的 Self 页面和三站的可运行页面另有一次哈希抽样复评。复评按站点选一项，单列两位评判器都给出结果的数量。[独立评判协议](../heldout_transfer/SECOND_JUDGE.md)
