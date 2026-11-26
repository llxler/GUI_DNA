# 同模型复测与论文核对

建库方法和模块实现见[自建库研究](../self_refinement/README.md)。本目录保存单独登记的问卷复测、表格条件重复、同解码设置的供库对照，以及论文按任务编号配对的代码。

| 入口 | 内容 |
| --- | --- |
| [清单复测](PROTOCOL.md) · [短格式复测](LINE_CONTRACT.md) | 在表格开发任务之外，用相同提示在问卷重新建库，保存两模型全部 20 个目标。 |
| [独立重复登记](CONFIRMATION.md) | 按事先规定的门槛检查哪些表格试验应另行采样。 |
| [人工库与原 GPT-5 库](supplied/PROTOCOL.md) | 在与新 Self 相同的部署设置下，重新测原有库。 |
| [论文逐格配对](paper.py) | 从公开 JSON 核对双库复验的每一行，以及单列的共同可判定来源对照。[公开结果](../../results/paper-library-followups-20261124.json) |
| [费用核对](accounting.py) | 合并不重复的只读账本，分别列出 API 已结金额、未知预留和 GPT-6 Astra 订阅 token。 |
