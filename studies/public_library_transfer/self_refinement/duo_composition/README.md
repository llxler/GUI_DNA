# WebApp1K-Duo 单功能组件的恢复与组合

六个模型曾各为博客和任务管理两个域写过一次组件库。本研究从保存的答复中抽取独立 React 模块，按公开单功能名和接口建立组件目录。部署器读取公开组合文件名列出的两个功能，按原装配器并列挂载。这是旧模型实现的确定性复用，建库和规划均未重新调用模型。两个原始建库请求的费用保存在[同模型套件汇总](../../../results/backbone-suites-20261124.json)。

每行评估相同的十个完整组合文件。固定组取同域抽得的头两个可用组件。Direct 恢复包括六十份原答的对称格式检查，还给从零组单独增加默认导出声明的语法修正规则。全部原成绩仍保留。

| 模型 | 原 Direct | 修正声明的 Direct | 原 Self | 组件按公开名称匹配 | 固定两项 |
|---|---:|---:|---:|---:|---:|
| GPT-OSS-120B | 5/10 | 5/10 | 0/10 | 6/10 | 1/10 |
| Qwen3.5-9B | 2/10 | 2/10 | 1/10 | 3/10 | 0/10 |
| Mistral Small 3.2 | 0/10 | 4/10 | 0/10 | 4/10 | 0/10 |
| Qwen3-Coder-30B | 4/10 | 4/10 | 1/10 | 2/10 | 1/10 |
| Gemma 3 12B | 1/10 | 1/10 | 0/10 | 0/10 | 0/10 |
| DeepSeek V4 Flash | 6/10 | 6/10 | 0/10 | 0/10 | 0/10 |

39 个模型－目标组合的两项组件都已交付。两项分别挂载都通过的 15 组均通过组合。至少一项独立失败的 24 组均未通过组合。其余 21 组缺组件。Duo 组合文件的 40 个用例均与建库时公开的单功能用例在归一标签名后重合。本结果检验这些已知功能的交付与组合。[逐项诊断](single-result.json) · [用例重合核对](../../../results/public-library-transfer-duo-public-admission-20261123.json)

## 核验

从仓库根目录运行下列命令。仅核对仓库内已发布的结果无需原始模型答复。使用本机历史收据重放时，将各入口的 `check` 换为 `register`、`score`，按下列顺序运行。重放需要原模型答复、官方 WebApp1K 测试与既有 npm 依赖。所有阶段均无 API 调用。

```bash
uv run python -m studies.public_library_transfer.self_refinement.duo_composition.run check
uv run python -m studies.public_library_transfer.self_refinement.duo_composition.direct check
uv run python -m studies.public_library_transfer.self_refinement.duo_composition.declaration check
uv run python -m studies.public_library_transfer.self_refinement.duo_composition.single check
```

[预登记与纳入范围](PROTOCOL.md) · [从零外层格式控制](DIRECT.md) · [默认导出敏感性](DECLARATION.md) · [单功能诊断](SINGLE.md)
