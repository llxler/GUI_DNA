# Web-Bench expression-editor 的未来需求

本研究对两个 AI 工作流做同目标比较。准备模型只收到公共起始文件和前十项公开需求。库或文字笔记冻结后，生成模型才看到第 11 至 20 步的相应前缀。初始登记写在 [协议](PROTOCOL.md)。完整需求先行的三流程实验使用独立的准备样本，见 [主研究](../library_sources/PROTOCOL.md)。

从仓库根目录调用 `python -m studies.expression_editor_unseen_requirements.run` 的 `freeze`、`prepare`、`generate`、`score` 阶段。首次 `freeze --budget-usd <本组获准额度>` 核对匹配实验的输入摘要、校准与可用余额；准备和生成使用独立账本，只有这两个阶段会发出本组模型请求。评分与结果核验均读取已冻结产物。

```bash
uv run python -m studies.expression_editor_unseen_requirements.report --write
uv run python -m studies.expression_editor_unseen_requirements.report
```

重建报告逐笔核对准备和生成的真实消息，包括公开错误修复。每个官方报告须只含当前任务文件。结果分别列准备及部署费用、传输缺失、无效响应、逐目标配对、固定库示例及校准可区分的位置。

本次两种原始准备都没有产生可部署材料。GPT-5 库首轮的编译器含语法错误，公开修复的 JSON 字符串未闭合。十个预定位置都因这一次建库失败记为流程失败，实际进行了零次模型部署。笔记首轮被服务端以 HTTP 402 拒绝，未返回任何模型内容，十个位置均缺失。两臂共同可判断的目标数为零。原账本三次请求结算 0.321139 美元，含未决预留的敞口为 0.498079 美元。逐位置记录见[原始报告](../../../results/expression-editor-unseen-20261123.json)。

原收据中，库的首轮正常结束（finish_reason 为 stop），输出 14,672 token，含 7,104 个推理 token。修复轮达到 16,000 的输出上限（finish_reason 为 length），其中 8,960 个为推理 token。可在 `artifacts/expression-editor-unseen-20261123/preparation/ai/{first,repair}/call/response.json` 复核。
