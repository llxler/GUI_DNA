# calculator/GPT-5完整有限模式审计

[协议](PROTOCOL.md)已在任何新候选评分前写明事后选择原因和端点。只枚举原库的全部1215个语义配置，包含字段省略，不改变库或官方测试。init包含布局及基础计算；它只是完整历史的必要条件。

```bash
uv run python -m test.finite_schema_audit.run prepare
uv run python -m test.finite_schema_audit.run evaluate
uv run python -m test.finite_schema_audit.analyze
```

已有阶段不能重建或覆盖。run.py、协议及snapshot列出的文件冻结；analyze.py/README可维护。原始报告必须完整，运行器错误不能记作模型失败。依赖补充快照在评分前另固定原VM编译器与运行时工具，保留最初准备清单，不回写它。
