# 工程回归测试

`tests/` 是 `pytest` 的默认测试目录，覆盖编译器、协议校验、预算账本、结果汇总和浏览器评分逻辑。论文研究及其正式实验结果从 [studies/](../studies/README.md) 查阅。

首次检出时先按根目录 README 取得固定提交的 Web-Bench 公开快照。5 项协议用例会读取其中的需求或公开断言。之后在仓库根目录安装依赖并运行测试。[获取上游快照](../README.md#安装与核验)

```bash
uv sync --extra dev
uv run playwright install chromium
uv run pytest -q
```

运行单个文件时可使用 `uv run pytest -q tests/test_protocol.py`。部分测试需要 Chromium 的系统运行库，具体环境见[复现说明](../docs/reproducibility.md)。

根目录的 `test/` 指向 `studies/`，用于解析旧研究导入和冻结清单。新增工程用例放在 `tests/`，引用研究源码时使用 `studies.*`。
