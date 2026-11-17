# 官方断言空过诊断

2026-11-17，零 API。先静态登记六项目 126 个官方测试文件，再独立比较 BOM 六文件中可空 frame 的检查。协议见 [PROTOCOL.md](PROTOCOL.md)。所有 BOM 浏览器评分串行，36 份原始报告含原参考、删框参考和空白页，以及原断言/仅收紧空值检查的诊断版本。

```bash
uv run python -m test.assertion_audit.analyze
```

结果写入 `test/results/assertion-audit-20261117.{json,md}`。分析逐份复查冻结字节、原始报告哈希和测试结果；另从旧三项目结果统一排除六个被标记的 BOM 文件，保留独立的事后敏感性，不能当作修订后的官方分数。

`run.py`、`__init__.py`、`PROTOCOL.md`、`artifacts/assertion-audit-20261117/snapshot.json` 列出的输入与依赖已经冻结，不能修改。`analyze.py` 与本文件可维护。文本检索范围有限，未命中不是健全性证明；没有新模型调用、没有删除或重评分旧模型候选。
