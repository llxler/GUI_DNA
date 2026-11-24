# 根据公开数据类型构建 SVG 图表库

项目为 ByteDance Web-Bench 的 svg-chart，单位是一个官方当前任务文件的全部断言。Qwen3-Coder-30B-A3B-Instruct 独立生成两份库，也为两份库逐题制定方案及从零生成二十份页面。共享基类先生成，后续模块读取本库真实的依赖源码。六种公开类型的挂载、布尔开关和入口由研究者提供；类、绘图、样式和交互由模型实现。两份库共用同设置从零候选，不重复计入对照。[原始预登记](PROTOCOL.md)

两项后续试验沿用同一批源码。第一项对两边补上可从同项目唯一具名导出确定的父类导入，重放原计划。第二项捕获网页实际派发的错误，向同一模型发出一次精确修改请求，同时允许从零页面得到相同的公开诊断和编辑机会。再对两库重新规划，另外保留原计划、全类型固定页和仅用起始工程与接线的控制页。程序能加载、图表容器可见、容器内确有图形以及官方文件通过，分别记录。[显式导入](module_linking/PROTOCOL.md) · [公开异常修复](runtime_patch/PROTOCOL.md)

另有两项不使用模型的敏感性分析。宽松解析给每个候选保留原始公共数据，接受与源码有明确分界的说明文字。类名接口诊断只在同一公开页面确实报 DOMTokenList 空白错误时，令原有的单参数 classList.add 调用按空白分开类名。各组均保留相应从零页面和固定页。[源文件交付](source_delivery/PROTOCOL.md) · [DOM 类名接口](dom_tokens/PROTOCOL.md)

在全套二十个目标中，正确计入收到但不能交付的失败后，严格协议的两库各过 1 项，从零过 2 项。仅链接父类两库各过 2 项，额外一轮公开模型补丁仍是各 2 项。放宽直接源码交付后，从零过 5 项。这些阶段与相同从零目标的对照见[四阶段逐题判定](source_delivery/comparisons.json)。

最终两份库的六类公共数据都绘出了图元（333、350 个）。在 20 个官方任务中，按模型方案为 7/20、5/20，固定全开逐题相同。宽松代码接收下的从零为 5/20，仅用起始工程和挂载为 1/20。去除仅检查公共资产的第一题后，模型库分别 6/19、4/19，从零 4/19。相同来源上另请区分严格交付、补模块导入和定点模型修复，不将它们当作新建库重复。[全部目标及方法差集](dom_tokens/result.json)

从仓库根目录只读复算发布数据：

```bash
uv run python -m studies.public_library_transfer.self_refinement.svg_renderers.run check
uv run python -m studies.public_library_transfer.self_refinement.svg_renderers.report check
uv run python -m studies.public_library_transfer.self_refinement.svg_renderers.module_linking.run check
uv run python -m studies.public_library_transfer.self_refinement.svg_renderers.runtime_patch.run check
uv run python -m studies.public_library_transfer.self_refinement.svg_renderers.source_delivery.report check
uv run python -m studies.public_library_transfer.self_refinement.svg_renderers.dom_tokens.run check
```
