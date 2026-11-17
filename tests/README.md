# Software Regression Tests

本目录仅保存工程回归测试：协议边界、编译器、账本、导出器、结果重算及浏览器运行行为。研究实验位于 [`studies/`](../studies/README.md)。

```bash
uv sync --extra dev
uv run playwright install chromium
uv run pytest -q
```

部分测试需要 Chromium 和系统运行库。安装说明见根 README；测试成功不等于重新生成模型输出、复跑全部历史浏览器页面或完成论文复现。旧测试中的 `test.*` 导入通过兼容链接加载同一份研究源码，新增测试使用 `studies.*`。
