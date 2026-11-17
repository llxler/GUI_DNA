# 传输中断与逐请求费用核实

初次六并发及随后三并发遇到本机代理的SSL握手失败/流中断。默认代理和直连的只读models接口分别检查后，剩余请求改用直连；模型、供应商约束、消息、种子、输出上限与有效响应次数不变。所有原流和错误记录保留，完整模型输出不重抽。

独立命令`python -m test.library_repair.billing --apply`只查询已归档中断流里唯一的generation ID，通过[OpenRouter逐请求元数据接口](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation)核实终止状态与`total_cost`，保存回执后调用原`Ledger.settle`正常结算。它不生成内容、不恢复截断文本，不修改cap/stop或删除请求。没有generation ID、费用/终止状态未确认、查询失败的记录均保持原预留；不因SSL握手错误推定零收费。后续余额差也不能替代逐请求凭证。

结算与候选完成是不同状态：已归档的部分响应即使费用被确认，仍不是可用模型输出。缺失响应按原协议续补，主运行器仅处理当前未完成请求；已归档记录不再参与模型输出选择。
