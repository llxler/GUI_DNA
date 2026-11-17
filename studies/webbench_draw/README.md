# Web-Bench draw：公开图形交互项目

2026-11-17 独立里程碑研究，协议见 [PROTOCOL.md](PROTOCOL.md)。五个固定任务前缀（4/8/12/16/20）；GPT-5 medium 和 Sonnet 4.5 各自根据全部公开需求建库，GPT-OSS-120B low 与 GPT-5 medium 对比无库代码、同库代码和方案，共计划 50 候选。同库代码可以直接调用完整编译器，两种同库输出的用户消息相同。固定文档示例与最终方案控制预先保留。

这里官方需求包含 SCSS，因此所有方法、参考和控制统一使用 Vite 7.1.5 / sass-embedded 1.83.1、Playwright 1.57.0；与原静态服务的三项目实验是独立协议。参考校准在付费前通过 21 个文件 / 70 条测试，五个当前文件的空白页都失败。

主要本地阶段：`webbench-draw-build-20261117`、`webbench-draw-oss-20261117`、`webbench-draw-frontier-20261117`、`webbench-draw-eval-20261117`，前缀均为 `artifacts/`。运行时依赖锁在 `artifacts/webbench-draw-runtime-20261117/package-lock.json`。API 统计只读入口为 `test.authorized_costs --date 20261117`；不重新打开已关闭的账本。

```bash
uv run python -m test.webbench_draw.analyze
uv run python -m test.draw_interface_audit
```

这个入口重算当前文件与同页 init+全部历史两种端点，首次和最终输出分开；原始记录、源码、完整响应/传输流、提示词、浏览器报告均保留。完成的无效输出计入失败；缺失的传输/预算位置单列。不会用较早可执行版本替换最终无效响应。

另有事后接口字节审计：GPT-5 库的 schema 仅有 theme 和 labelSize，完整162合法配置（含省略）产生106份不同源码；index.js/app.js 在所有配置中均逐字复用。这个入口的代码/包哈希和枚举列表注册在 `artifacts/webbench-draw-interface-audit-20261117/registration.json`。不应再修改 `test/draw_interface_audit.py`；它是源码字节检查，CSS/HTML 仍可影响交互位置，不能当作行为等价或完整历史不可达证明。

`core.py`、`run.py`、`browser.py`、`server.mjs`、`check.cjs`、`evaluate.py`、`__init__.py` 和 `PROTOCOL.md`，以及各 `review-manifest.json` / 评分 `inputs.json` 列出的源文件和输入已经冻结。不得原地修改；`analyze.py` 和本文件可维护。新数据没有自动进入之前已验证的匿名包，也不代表跨机器复验。
