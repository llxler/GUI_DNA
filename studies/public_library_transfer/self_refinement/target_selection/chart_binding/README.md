# 已生成图表组件的浏览器接线

原先的 SVG Self 库都能打开页面，但两个模型在公开数据上都没有把一个 SVG 挂到屏幕。研究者按公开起始工程调用图表对象已有的绘制方法，并将其已有的 SVG 挂入容器。对于确定的局部作用域错误，还允许把生成库自己的计算表达式移动到有效作用域。没有补画图形或复制参考实现。[协议及修复边界](PROTOCOL.md)

两次独立的公开浏览器观察得到相同结果。Qwen3-Coder 接线后报告 `min is not defined`。将原模块中的 `min`、`max`、`range` 三条现有声明移动到条件分支之前后，共渲染 9 个 SVG、138 个图形，无页面错误。DeepSeek Flash 的包只有修改现有渲染结果的控件，没有新增绘制类；它能挂载起始工程提供的 9 个 SVG，里面仍为零个图形。两个模型都保留独立的原规划、从零、固定配置和只接线的对照。[逐文件数据](result.json)

在根目录运行发布数据核对。本地持有原库、起始工程与浏览器回执时可复验公开交互及官方报告。

```bash
uv run python -m studies.public_library_transfer.self_refinement.target_selection.chart_binding.report check
uv run python -m studies.public_library_transfer.self_refinement.target_selection.chart_binding.run freeze
uv run python -m studies.public_library_transfer.self_refinement.target_selection.chart_binding.run score
uv run python -m studies.public_library_transfer.self_refinement.target_selection.chart_binding.report check-local
```

Qwen 的原始 Direct 请求实际返回了文件名到代码的映射，缺少要求的外层 `files`。DeepSeek 有些请求返回空文本。为使从零比较可解释，另对两模型的全部原响应尝试等价封装，并逐题提供相同的公开接线和作用域修复。[无库对照协议](direct_control/PROTOCOL.md) · [原始与恢复后的配对结果](direct_control/result.json)

对应的无库回放入口如下。该阶段先对两款模型的全部逐题原响应冻结页面，再运行原任务文件并核验比较。

```bash
uv run python -m studies.public_library_transfer.self_refinement.target_selection.chart_binding.direct_control.run freeze
uv run python -m studies.public_library_transfer.self_refinement.target_selection.chart_binding.direct_control.run score
uv run python -m studies.public_library_transfer.self_refinement.target_selection.chart_binding.direct_control.report check-local
```

Qwen 图表库从原先的 1/20 到只接线的 2/20，再到公开作用域修复后的 5/20。Qwen 从零原来的严格接口为 0/20；仅补外层包装便为 5/20，对从零页也开放相同接线和修复后仍为 5/20。两个修复流程通过的恰好都是任务 1、2、4、5、6，固定修复页也通过同一组。这一批没有观测到相对格式恢复后的从零页的额外通过项。

DeepSeek 的已接线库为 1/20，仅通过空白页也能通过的公共资产题；从零为 1/20，独有通过的是第 2 题。去掉不能区分空白页的第 1 题后，二者分别为 0/19 和 1/19。保留两份实现的缺口，可分别检验入口接线失败和根本没有绘图代码的情况。
