# 第二轮全部实验记录

| 模型 | 方法 | 首次通过 | 最终通过 | 状态合规 | 基础保留 | 可运行 | 修复 | 已结算 USD | 未确认预留 USD | 输入 tokens | 输出 tokens | 平均生成秒 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-pro-0813 | checks | 8/12 | 9/12 | 9/12 | 47/54 | 11/12 | 7 | 0.055373 | 0.024600 | 48169 | 14933 | 23.3 |
| deepseek/deepseek-v4-pro-0813 | compact_js | 10/12 | 10/12 | 10/12 | 52/54 | 12/12 | 4 | 0.047640 | 0.195976 | 46029 | 7949 | 29.9 |
| deepseek/deepseek-v4-pro-0813 | compact_plan | 2/12 | 4/12 | 4/12 | 24/54 | 4/12 | 20 | 0.044206 | 0.196800 | 92094 | 3679 | 23.3 |
| deepseek/deepseek-v4-pro-0813 | compiled | 7/12 | 10/12 | 10/12 | 45/54 | 10/12 | 8 | 0.047890 | 0.067700 | 84027 | 3105 | 14.3 |
| deepseek/deepseek-v4-pro-0813 | constrained | 11/12 | 11/12 | 11/12 | 53/54 | 12/12 | 2 | 0.046913 | 0.000000 | 59913 | 13133 | 19.8 |
| deepseek/deepseek-v4-pro-0813 | deterministic | 12/12 | 12/12 | 12/12 | 54/54 | 12/12 | 0 | 0.000000 | 0.000000 | 0 | 0 | 4.2 |
| deepseek/deepseek-v4-pro-0813 | direct | 10/12 | 12/12 | 12/12 | 54/54 | 12/12 | 2 | 0.051505 | 0.121373 | 16652 | 14908 | 33.2 |
| deepseek/deepseek-v4-pro-0813 | dna | 11/12 | 11/12 | 11/12 | 50/54 | 11/12 | 2 | 0.051329 | 0.075062 | 31585 | 12100 | 22.7 |
| deepseek/deepseek-v4-pro-0813 | linked_dna | 11/12 | 12/12 | 12/12 | 54/54 | 12/12 | 2 | 0.034149 | 0.081129 | 32235 | 5639 | 23.1 |
| deepseek/deepseek-v4-pro-0813 | metadata | 11/12 | 11/12 | 11/12 | 53/54 | 12/12 | 2 | 0.079816 | 0.000000 | 59052 | 14757 | 17.7 |
| deepseek/deepseek-v4-pro-0813 | retrieval | 10/12 | 12/12 | 12/12 | 54/54 | 12/12 | 3 | 0.061451 | 0.125977 | 40195 | 14169 | 30.3 |
| qwen/qwen3-coder-plus | checks | 11/12 | 11/12 | 11/12 | 53/54 | 12/12 | 2 | 0.060991 | 0.000000 | 33325 | 15786 | 16.2 |
| qwen/qwen3-coder-plus | compact_js | 12/12 | 12/12 | 12/12 | 54/54 | 12/12 | 0 | 0.037834 | 0.000000 | 29964 | 8145 | 14.1 |
| qwen/qwen3-coder-plus | compact_plan | 2/12 | 4/12 | 4/12 | 22/54 | 4/12 | 20 | 0.052837 | 0.000000 | 91310 | 8026 | 10.8 |
| qwen/qwen3-coder-plus | compiled | 4/12 | 5/12 | 5/12 | 23/54 | 5/12 | 15 | 0.076434 | 0.000000 | 111744 | 10546 | 11.8 |
| qwen/qwen3-coder-plus | constrained | 12/12 | 12/12 | 12/12 | 54/54 | 12/12 | 0 | 0.053766 | 0.000000 | 44784 | 13954 | 14.6 |
| qwen/qwen3-coder-plus | deterministic | 12/12 | 12/12 | 12/12 | 54/54 | 12/12 | 0 | 0.000000 | 0.000000 | 0 | 0 | 4.1 |
| qwen/qwen3-coder-plus | direct | 5/12 | 9/12 | 9/12 | 53/54 | 12/12 | 11 | 0.116259 | 0.000000 | 43813 | 29279 | 25.2 |
| qwen/qwen3-coder-plus | dna | 10/12 | 12/12 | 12/12 | 54/54 | 12/12 | 2 | 0.070625 | 0.000000 | 32846 | 16122 | 15.6 |
| qwen/qwen3-coder-plus | linked_dna | 12/12 | 12/12 | 12/12 | 54/54 | 12/12 | 0 | 0.036314 | 0.000000 | 25116 | 7808 | 10.6 |
| qwen/qwen3-coder-plus | metadata | 12/12 | 12/12 | 12/12 | 54/54 | 12/12 | 0 | 0.068572 | 0.000000 | 44784 | 13205 | 13.7 |
| qwen/qwen3-coder-plus | retrieval | 10/12 | 11/12 | 11/12 | 54/54 | 12/12 | 1 | 0.059766 | 0.000000 | 30647 | 13385 | 13.9 |

不同阶段均保留；同一任务的首次及最终版本按固定规则评分，不择优。只有双方都完成的同模型、任务、重复编号进入配对统计。确定性参照不调用模型，重复展示不构成独立模型采样。

费用为已结算回执，未知费用另保留上界；不确定费用存在时，不能把已结算差额当作最终账单差额。Token统计来自成功返回的费用回执，路由错误没有可用token回执。

平均生成秒包括模型调用、公开检查与修复，不含最终隐藏评测。首个Qwen组重放时间不含原始API等待，恢复、服务排队和并行负载也影响时间；只作描述，不据此宣称速度提升。

累计已结算 $1.578579；包含全部未确认预留的记账敞口 $3.300928；未结算请求 45。

配对结果：

- deepseek/deepseek-v4-pro-0813，constrained 对 dna，first_hidden：胜1 / 负1 / 平10（n=12）。
- deepseek/deepseek-v4-pro-0813，constrained 对 dna，hidden：胜1 / 负1 / 平10（n=12）。
- deepseek/deepseek-v4-pro-0813，linked_dna 对 dna，first_hidden：胜1 / 负1 / 平10（n=12）。
- deepseek/deepseek-v4-pro-0813，linked_dna 对 dna，hidden：胜1 / 负0 / 平11（n=12）。
- deepseek/deepseek-v4-pro-0813，compiled 对 dna，first_hidden：胜0 / 负4 / 平8（n=12）。
- deepseek/deepseek-v4-pro-0813，compiled 对 dna，hidden：胜0 / 负1 / 平11（n=12）。
- deepseek/deepseek-v4-pro-0813，compiled 对 constrained，first_hidden：胜1 / 负5 / 平6（n=12）。
- deepseek/deepseek-v4-pro-0813，compiled 对 constrained，hidden：胜1 / 负2 / 平9（n=12）。
- deepseek/deepseek-v4-pro-0813，compiled 对 linked_dna，first_hidden：胜1 / 负5 / 平6（n=12）。
- deepseek/deepseek-v4-pro-0813，compiled 对 linked_dna，hidden：胜0 / 负2 / 平10（n=12）。
- deepseek/deepseek-v4-pro-0813，compact_plan 对 compact_js，first_hidden：胜0 / 负8 / 平4（n=12）。
- deepseek/deepseek-v4-pro-0813，compact_plan 对 compact_js，hidden：胜1 / 负7 / 平4（n=12）。
- deepseek/deepseek-v4-pro-0813，compact_plan 对 linked_dna，first_hidden：胜0 / 负9 / 平3（n=12）。
- deepseek/deepseek-v4-pro-0813，compact_plan 对 linked_dna，hidden：胜0 / 负8 / 平4（n=12）。
- deepseek/deepseek-v4-pro-0813，deterministic 对 dna，first_hidden：胜1 / 负0 / 平11（n=12）。
- deepseek/deepseek-v4-pro-0813，deterministic 对 dna，hidden：胜1 / 负0 / 平11（n=12）。
- qwen/qwen3-coder-plus，constrained 对 dna，first_hidden：胜2 / 负0 / 平10（n=12）。
- qwen/qwen3-coder-plus，constrained 对 dna，hidden：胜0 / 负0 / 平12（n=12）。
- qwen/qwen3-coder-plus，linked_dna 对 dna，first_hidden：胜2 / 负0 / 平10（n=12）。
- qwen/qwen3-coder-plus，linked_dna 对 dna，hidden：胜0 / 负0 / 平12（n=12）。
- qwen/qwen3-coder-plus，compiled 对 dna，first_hidden：胜1 / 负7 / 平4（n=12）。
- qwen/qwen3-coder-plus，compiled 对 dna，hidden：胜0 / 负7 / 平5（n=12）。
- qwen/qwen3-coder-plus，compiled 对 constrained，first_hidden：胜0 / 负8 / 平4（n=12）。
- qwen/qwen3-coder-plus，compiled 对 constrained，hidden：胜0 / 负7 / 平5（n=12）。
- qwen/qwen3-coder-plus，compiled 对 linked_dna，first_hidden：胜0 / 负8 / 平4（n=12）。
- qwen/qwen3-coder-plus，compiled 对 linked_dna，hidden：胜0 / 负7 / 平5（n=12）。
- qwen/qwen3-coder-plus，compact_plan 对 compact_js，first_hidden：胜0 / 负10 / 平2（n=12）。
- qwen/qwen3-coder-plus，compact_plan 对 compact_js，hidden：胜0 / 负8 / 平4（n=12）。
- qwen/qwen3-coder-plus，compact_plan 对 linked_dna，first_hidden：胜0 / 负10 / 平2（n=12）。
- qwen/qwen3-coder-plus，compact_plan 对 linked_dna，hidden：胜0 / 负8 / 平4（n=12）。
- qwen/qwen3-coder-plus，deterministic 对 dna，first_hidden：胜2 / 负0 / 平10（n=12）。
- qwen/qwen3-coder-plus，deterministic 对 dna，hidden：胜0 / 负0 / 平12（n=12）。
