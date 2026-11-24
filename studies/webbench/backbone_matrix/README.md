# 多模型同任务比较

表格、SVG 和问卷各有 20 个官方当前任务。直接生成、人工库组装、冻结 GPT-5 库组装、同模型建库并组装共用同一模型的真实直接对照。首例重放单列。模型和输入在生成前登记。[首批协议](PROTOCOL.md) · [开放模型扩展](extension/PROTOCOL.md) · [七模型问卷复测](question_form/PROTOCOL.md) · [TodoMVC、Duo 的独立协议](../../public_library_transfer/backbone_suites/PROTOCOL.md)

公开结果可直接离线核对，无须 API 密钥、浏览器或私有原始产物。

```bash
uv run python -m studies.webbench.backbone_matrix.audit
uv run python -m studies.paper_performance  # 用公开 JSON 输出论文 Table 1 的 LaTeX
```

[公开开支与固定首例](../../results/backbone-overview-20261124.json) · [四批的预算敞口](../../results/backbone-allocations-20261124.json)

原始生成回执、预留与逐题浏览器报告存放在 `artifacts/backbone-matrix-20261124/`、`artifacts/backbone-extension-20261124/` 、`artifacts/backbone-form-20261124/` 与 `artifacts/backbone-suites-20261124/`。有本机原始产物时，首批用 `python -m studies.webbench.backbone_matrix.report score <模型简称>` 复验封存的候选。扩展模型用 `python -m studies.webbench.backbone_matrix.extension score <模型简称>`。问卷复测用 `python -m studies.webbench.backbone_matrix.question_form score <模型简称>`。两个套件用 `python -m studies.public_library_transfer.backbone_suites.run score <模型简称>`。[逐格目标与分母](../../results/paper-performance-matrix.json)
