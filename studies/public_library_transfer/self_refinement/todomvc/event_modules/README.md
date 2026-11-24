# 在本地小模型上按事件生成 TodoMVC

研究者从公开宿主确定共享状态、函数签名、五组可选事件和统一的持久化调用。Qwen2.5-0.5B-Instruct 自己写初始化、持久化、视图和九个事件处理函数，并逐目标选开关。两份库分别采样，使用八个同目标、同权重的从零生成结果。库按函数生成并可修复一次，从零按整个目标一次生成，两流程的 token 和准备工作量不同。

固定全开让所有已交付的事件可达，固定关闭只关闭五组可选事件。两者均保留新增、删除、视图及持久化。原始开发检查只在语法有效后封存源码；能否达到目标由当前任务的官方断言判定。[冻结协议](PROTOCOL.md) · [逐目标结果](result.json)

仅核对发布的 JSON 可在仓库根目录运行以下命令。有公布版本的模型权重、GPU、Node 及 Chromium 时，依次执行同入口的 `register`、`generate`、`score`。完整回放需要本机公开宿主、官方测试依赖和封存的运行材料。

```bash
uv run python -m studies.public_library_transfer.self_refinement.todomvc.event_modules.run check
```
