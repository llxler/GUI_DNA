# Table editor 自建库复测

从 [A 区项目页](../../../../paper-results/A/table-editor.md) 查七个模型的最终成绩。每格分母为 20。数字链接定位主表 JSON；项目页下方「来源记录」定位该模型最终采用的逐题判决。每个结果文件的 `models` 以模型 ID 为键，`self`、`fixed-self`、`binding-only` 分别对应逐题选择、固定全开和空宿主。使用菜单渲染回退的模型另有 `menu-shell` 对照。

| 阶段 | 进入条件与可复核内容 |
| --- | --- |
| [共享选区接口](PROTOCOL.md) · [结果](result.json) | 七款模型各自根据公开要求实现模块。记录首次准入、扩展的取舍和按公开观察选择的配置。 |
| [菜单与键盘路由](event_routing/PROTOCOL.md) · [结果](event_routing/result.json) | 对未准入的库拆分菜单动作；对已准入库检查键盘事件。记录新旧同作者源码和公开操作差异。 |
| [短命令交付](command_delivery/PROTOCOL.md) · [结果](command_delivery/result.json) | 先单独交付插行，按实际事件名接回短函数，保留通过的组件。分别记录已准入模型的逐题与固定页成绩。 |
| [选区与插行组合](core_recovery/PROTOCOL.md) · [结果](core_recovery/result.json) | 仅用于上一阶段仍未准入的模型。按登记顺序组合该模型自己交付的组件，随后复测 20 题。 |
| [键盘状态转移](keyboard_transitions/PROTOCOL.md) · [最终逐题结果](keyboard_transitions/result.json) | 七款模型沿用已准入的库。公开键盘操作有缺项时，原模型为移动、范围和编辑编写状态转移，宿主将坐标映射到页面。该阶段统一进入主表。相同配置下的旧实现记为 `old-same-choice`。 |

```bash
python -m studies.lookup web-bench/table "Qwen3-Coder-30B" Self
python -m studies.lookup web-bench/table "GPT-OSS-120B" Self
python -m studies.webbench.table.shared_selection.report
```

在验证摘要中按 `stages → transitions → 模型 ID` 查阅。该模型的 `passed` 列出各对照通过的任务号，`public_keyboard_checks` 记录模型答错的坐标例子，`official_failures` 给出正式失败用例及报告哈希。

有本地原始响应和浏览器报告时，`uv run python -m studies.webbench.table.shared_selection.verify` 逐题核对选择、页面哈希、Playwright 原始判决及分阶段费用。[验证摘要](verification.json) · [结果解释与逐模型费用](../../../../docs/results.md#table-self-shared-selection)
