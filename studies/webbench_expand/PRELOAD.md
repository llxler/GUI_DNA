# 调用前的完整库预载补充

在候选生成前，公开建库结果显示 GPT-5 的 calculator 把主要实现放在冻结编译器内，而 `files` 只有占位文件。只预载 `files` 会迫使自由代码重抄编译器，不能充分实现同库对照。

因此正式规划入口为 `test.webbench_expand.generate`，替代 README 中原始 `run generate`。建库输出不改。新入口将**完全相同的冻结编译器**预载为 `__gui_dna_support/compiler.mjs`（命名导出 compile），将原文件映射预载为 `__gui_dna_support/files.json`。自由代码可导入/调用它们，也可任意覆盖。它仍负责在浏览器加载/挂载生成的文件，未提供按任务预生成的答案。两种同库做法的用户消息逐字一致，都说明此辅助资源；方案仍在原编译器和严格模式下执行。

这项补充在所有规划请求及所有候选隐藏评分之前固定。它不是隐藏分数驱动的修库，也不改变两建库者已经输出的模式、文件或编译器。第一次公开校准的 BOM 初始页缺陷与后续 ES module 设置照实保留。

为避免仍由自由代码承担浏览器文件映射加载的额外负担，另提供等价的构建时入口：它可输出 `{"program":"function build(files, compile) { ...; return outputFiles; }"}`。同一个纯 VM 预载原文件映射与冻结 compile，代码可以一行调用 compile、任意修改产物或重写整个页面；不受方案模式约束。仍可选择原 `files` 输出。两种同库做法都看到该能力说明；无库代码继续直接输出完整文件。这个基线强于上轮仅文件预载版本，不能跨阶段把差值归因于严格检查本身。

```bash
# 建库中断：保留已完成输出/反馈，仅补缺失请求，仍最多3次有效尝试
uv run python -m test.webbench_expand.resume build --workers 2
uv run python -m test.webbench_expand.run build --workers 3
# 正式候选和不完整传输恢复（同一入口）
uv run python -m test.webbench_expand.generate --workers 6
uv run python -m test.webbench_expand.generate --resume-transport --workers 3
uv run python -m test.webbench_expand.evaluate --workers 6
uv run python -m test.webbench_expand.controls --workers 6
uv run python -m test.webbench_expand.analyze
uv run python -m test.webbench_expand.audit
```

六并发下三个官方最终参考页各复验3次，9/9通过。没有给候选测试反馈；并发检查只用于排除明显的运行环境问题。
