# 两个模型逐组件构建 WebApp1K-Duo 库

Qwen3.5-9B 与 GPT-OSS-120B 各自独立生成两套组件。每套由十五个单功能 React 模块构成，分属博客与任务管理两个域。每个模块先运行一份公开单功能文件，失败时允许一次修复。同一目标模型生成的新从零候选也有一次相同机会，用它负责的两个公开单功能文件检查；原始和修复后成绩都保留。组合的逐题方案、组件名直接匹配、域内固定两组件分开报告。两个域的十个组合共四十个用例，其断言与公开单功能用例重合。[冻结协议](PROTOCOL.md) · [逐组件与逐目标成绩](result.json)

以下核对命令只读仓库中的发布记录。具有原始回执和冻结 Jest 环境时可用 `check-local` 复验页面哈希、Jest 报告及逐阶段支出。历史付费调用不续跑。

```bash
uv run python -m studies.public_library_transfer.self_refinement.duo_components.report check
uv run python -m studies.public_library_transfer.self_refinement.duo_components.report check-local
```

首批 GPT-OSS 的两套库中，单功能公开检查分别由初次的 9/15、8/15 提升到 14/15、11/15；十个组合的模型规划依次为 9/10、6/10。新 Direct 的初始、同等公开反馈修复后分数为 8/10、9/10。Qwen 两套库虽都交付过可解析组件，最终分别只有 0/15、1/15 个组件过公开单功能，组合以及从零组均为 0/10。两模型的四十份逐题计划都与公开组合名列出的组件一致，域内固定两项均为 0/10。

[Qwen 精简契约复验](compact/PROTOCOL.md)把同一份公开规格改写为原有请求、渲染 props、动作及断言的有序序列，要求模型只编写所需控件。单功能和从零采用同一变换，两套独立新库与新 Direct 都保留。[复验全组数据](compact/result.json)

```bash
uv run python -m studies.public_library_transfer.self_refinement.duo_components.compact.report check
```

精简契约后，Qwen 两个库提交了 14/15、15/15 份可解析的组件，分别只有 2/15、1/15 个组件通过两项公开行为测试。新 Direct、两次组装和固定对照均为 0/10。格式交付改善未转化为整题通过。两项公开单功能检查与一个组合文件遇到同一 Direct 候选的未捕获 JavaScript 错误，保留原进程日志并用实际失败断言复验。[异常记录办法](compact/RUNTIME.md)
