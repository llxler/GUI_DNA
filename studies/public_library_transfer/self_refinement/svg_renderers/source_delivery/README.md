# SVG 源文件交付

Qwen3-Coder 为同一组 20 个 Web-Bench svg-chart 任务生成了从零页面。严格交付允许模型修改应用文件。模型同时返回公共资产，或给文件标签加 Markdown 标题时，解析器可能连应用文件也一起拒收。此项敏感性分析丢弃回复中的公共资产，使用上游固定字节，按清晰的文件边界接收模型已经写出的应用代码。相同原则也用于两份库的模块；没有额外模块因此得到接收。

严格条件下有 12 个最终页面成功交付，2/20 通过。按宽松规则处理同一批真实回复后，20 个最终页面全部交付，5/20 通过。公开选择规则改变了一个原先已经交付的页面，有九份最终页面需要单独运行官方当前任务文件；本次新通过的任务是 4、12、13。资产题 1 也能由空白页通过，去掉后两组为 1/19 和 4/19。[逐题结果](result.json)

源交付协议于 11:13:46 UTC 登记，页面于 11:15:18 UTC 封存，首份新增当前任务收据在 11:16:06 UTC 产生。原严格组当时在后台评分，完整结果于 11:21 UTC 写出。原组源码、选择和结果均可独立核对。整个重放新增模型调用数为零。[协议](PROTOCOL.md)

从仓库根目录运行以下命令。第一条从发布数据重建配对，第二条还需要原始响应、页面和官方浏览器收据。第三条单独复核各库优化阶段与同条件从零页面的比较。

```bash
uv run python -m studies.public_library_transfer.self_refinement.svg_renderers.source_delivery.report check
uv run python -m studies.public_library_transfer.self_refinement.svg_renderers.source_delivery.report check-local
uv run python -m studies.public_library_transfer.self_refinement.svg_renderers.source_delivery.report check-comparisons
```
