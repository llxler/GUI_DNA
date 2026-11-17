# 复算与公开材料说明

研究代码在 `studies/`，工程测试在 `tests/`。旧记录的 `test/...` 路径仍有效；迁移仅改变目录组织，冻结源码、原始实验 JSON 和账本不重新解释。

## 零 API 复算

```bash
uv run python -m studies.end_to_end --check
uv run pytest -q
uv run python -m experiments.audit_scale
```

主视图脚本检查两项目/三项目的原当前结果与历史复验一致，按真实候选去重；独立保留 draw 端点、BOM 敏感性、反馈负结果和建库费用。只读分析不等于全历史浏览器重跑。完整旧研究命令见 [历史索引](../studies/REVIEW.md)。

本地拥有完整 `artifacts/` 时可进一步复验研究快照与原报告。请使用对应研究 README 的只读分析入口，不执行生成、修复或恢复命令。代码 checkout 不包含被忽略的响应、页面、账本、浏览器缓存或上游 checkout；仅有源码不能重放全部历史结果。

## 本地论文与展示

```bash
uv run python -m studies.paper_end_to_end --write
bash artifacts/paper-build/build.sh
# 编译成功且日志无错误后，将 build/main.pdf 同步到 DNA_latex/main.pdf。
uv run --with pymupdf python -m studies.paper_format --report studies/results/paper_format_end_to_end.json
artifacts/presentation-build/venv/bin/python artifacts/presentation-build/build_presentation.py
artifacts/presentation-build/venv/bin/python artifacts/presentation-build/render_and_check.py
```

这些目录/工具为本地编辑资产，尚未作为公开论文材料发布。旧 `paper_cells`、`paper_public_review`、`paper_nov17 --write` 等针对历史稿件；不得用其旧模板覆盖当前稿件。新稿全部活跃表格由 `paper_end_to_end` 登记和核对。

## 路径兼容与匿名包

- `test -> studies` 保持旧 Python 导入和哈希路径；`实验结果.md`、`代码逻辑.md`、`experiments/TODO.md` 指向正式 `docs/` 文件。克隆时须保留符号链接；无符号链接环境可使用匿名导出器的实文件副本。
- 匿名导出需同时保留正式路径和旧 `test/...` 可执行副本，不能把路径变更当作改写冻结证据的理由。新清单登记原始与匿名化字节的区别。
- 最后已完整验收的大包是 `anonymous-replay-20261116-final-2.zip`，12 个入口通过；该包不含本日新实验与本次迁移，不宣称新版已验收。旧包不覆盖、不自行上传。
- 仓库保留上游许可证和来源说明。数据与匿名下载地址仍待作者审核，见 [roadmap](roadmap.md)。
