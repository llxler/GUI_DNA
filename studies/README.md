# GUI-DNA Research Studies

本目录保存公开基准上的实验实现、冻结协议和可复算分析。工程回归测试在 [`tests/`](../tests/README.md)，本目录不再称作测试目录。历史 `test/...` 清单通过根目录兼容链接解析；冻结文件中的旧路径和方法名保持原样。

## 当前论文入口

- [研究设计与主比较](../docs/method.md)：AI 建库＋GUI-DNA 对无库代码。
- [主比较 JSON](results/end_to_end.json)：按建库者分列，项目/目标生成模型另分层；共用唯一基线，每组目标和分母一致，当前/历史端点与建库费用分别报告；`free_lib` 只在历史记录中。
- [重算与复现](../docs/reproducibility.md)、[下一阶段协议](../docs/end_to_end_protocol.md)、[任务清单](../docs/roadmap.md)。

```bash
uv run python -m studies.end_to_end --check
uv run python -m studies.paper_end_to_end       # 需要本地论文源
```

## 实验索引

| 路径 | 作用 | 当前报告范围 |
|---|---|---|
| `interface_blind/` | Web-Bench dom1/form 的模型建库和整页生成 | `free` 与 `plan` |
| `webbench_expand/` | calculator/table/bom 的模型建库和生成 | `free` 与 `plan`；无无库组的小试不补造比较 |
| `webbench_draw/` | draw 的五里程碑实验 | `free` 与 `plan` |
| `history_replay/` | 保存页面的完整历史复验 | 对应上述真实候选 |
| `matched_feedback*/` | 公开反馈的完整目标压力检查 | 主比较 27 候选，其他记录归档 |
| `assertion_audit/`, `finite_schema_audit/` | 判据覆盖与库充分性诊断 | 明确有限范围与事后性质 |
| `todomvc_dna/`, `webbench_dna/` | 人工提供库的历史机制实验 | 单列背景，不称模型建库 |
| `webapp1k_dna/` | WebApp1K-Duo 独立功能实验 | 历史公开基准证据 |
| `heldout_composition/`, `interaction_*`, `development_feedback/` | 旧合成诊断 | 不进入当前公开基准论文 |
| `results/` | 派生 JSON、历史审计快照 | 原快照不覆盖，主视图为 `end_to_end.json` |

其他目录的 README/PROTOCOL/manifest 记录原实验条件，不随论文删列改写。旧全量入口索引 [REVIEW.md](REVIEW.md) 用于查证历史；新的运行说明以 `docs/reproducibility.md` 为准。源码可公开不等于所有大型原始产物已公开，发布状态见根 README。
