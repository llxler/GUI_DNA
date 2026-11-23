# 表格 AI 行为库的固定配置覆盖率

本研究回答两份 Codex 行为库的逐目标成绩能否由一个合法的固定配置覆盖。两份库分别有 2 个和 8 个设置，每个设置使用相同的 20 个官方任务文件。覆盖要求一个固定页通过逐目标方法成功的每一项。两者仅通过相同数量的任务不足以判定覆盖。

[事后研究协议](PROTOCOL.md) · [机器可读结果](../results/public-library-transfer-table-space-20261123.json)

| 建库重复 | 合法配置数 | 首例 | 最佳固定页 | 均匀随机期望通过数 | 逐题可达上界 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2 | 18/20 | 19/20 | 18.5/20 | 19/20 |
| 2 | 8 | 17/20 | 19/20 | 14/20 | 19/20 |

第一份库唯一的最优设置为初次排序降序。第二份库唯一的最优设置为全部启用单元格编辑、行列缩放和移动。Qwen 和 Mistral 在第二份库上都比首例多通过任务 15、16；这一个固定设置覆盖两种模型通过的全部 19 项。两份库的全部设置均未通过任务 9。200 个配置与目标组合中，新运行 140 份官方文件，另 60 份使用完全相同页面与合同的原始报告。

```bash
uv run python -m studies.public_library_transfer_table_space.run freeze
uv run python -m studies.public_library_transfer_table_space.run score --workers 3
uv run python -m studies.public_library_transfer_table_space.report --write
uv run python -m studies.public_library_transfer_table_space.report
```

`freeze` 枚举正式库接口，封存 200 个配置与目标组合。`score` 只测试每个目标自己的官方文件。`report` 从浏览器原始收据复算随机期望、单页最优和可达上界，再逐项核对 Qwen 和 Mistral 实际使用的页面字节与通过集合。原始报告在 `artifacts/public-library-transfer-table-space-20261123/`，源研究的同一报告通过哈希引用。
