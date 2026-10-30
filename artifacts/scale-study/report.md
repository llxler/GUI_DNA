# 第三轮扩大实验：全部结果

| 模型 | 方法 | 完整配对 n | 首次通过 | 最终通过 | 状态合规 | 基础保留 | 可运行 | 修复 | 已结算 USD | 未确认预留 USD | 输出 tokens |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen/qwen3-coder-plus | dna | 20 | 12 | 13 | 13 | 80/82 | 20 | 15 | 0.172522 | 0.000000 | 35433 |
| qwen/qwen3-coder-plus | linked_js | 20 | 10 | 14 | 14 | 80/82 | 20 | 12 | 0.152516 | 0.000000 | 34710 |
| qwen/qwen3-coder-plus | plan_unchecked | 20 | 18 | 20 | 20 | 82/82 | 20 | 2 | 0.034363 | 0.000000 | 4082 |
| qwen/qwen3-coder-plus | plan_checked | 20 | 18 | 20 | 20 | 82/82 | 20 | 2 | 0.026497 | 0.000000 | 4211 |
| deepseek/deepseek-v4-pro-0813 | dna | 27 | 24 | 26 | 26 | 112/112 | 27 | 4 | 0.178010 | 0.000000 | 37802 |
| deepseek/deepseek-v4-pro-0813 | linked_js | 27 | 7 | 13 | 13 | 76/112 | 21 | 35 | 0.148922 | 0.000000 | 21882 |
| deepseek/deepseek-v4-pro-0813 | plan_unchecked | 27 | 17 | 20 | 20 | 105/112 | 27 | 17 | 0.074221 | 0.000000 | 6453 |
| deepseek/deepseek-v4-pro-0813 | plan_checked | 27 | 15 | 27 | 27 | 112/112 | 27 | 12 | 0.046767 | 0.000000 | 5704 |

完整四方法组 47；不完整组 2；全部状态 {'generated': 190, 'budget_stopped': 2}。

正确率只使用预先规定的完整配对组；费用、token、修复及耗时包含所有已尝试记录（包括不完整组）。精确分母、输入tokens、耗时与逐任务结果见 analysis.json。

相对 plan_checked 的固定配对比较（差值为 plan_checked − baseline）：

- qwen/qwen3-coder-plus / linked_js / first_hidden：胜9、负1、平10；差值 0.4，8 类功能家族聚类 bootstrap 95% 区间 [-0.0625, 0.7272727272727273]。
- qwen/qwen3-coder-plus / linked_js / hidden：胜6、负0、平14；差值 0.3，8 类功能家族聚类 bootstrap 95% 区间 [0.0625, 0.5]。
- qwen/qwen3-coder-plus / dna / first_hidden：胜7、负1、平12；差值 0.3，8 类功能家族聚类 bootstrap 95% 区间 [0.0625, 0.46153846153846156]。
- qwen/qwen3-coder-plus / dna / hidden：胜7、负0、平13；差值 0.35，8 类功能家族聚类 bootstrap 95% 区间 [0.15, 0.5555555555555556]。
- qwen/qwen3-coder-plus / plan_unchecked / first_hidden：胜0、负0、平20；差值 0.0，8 类功能家族聚类 bootstrap 95% 区间 [0.0, 0.0]。
- qwen/qwen3-coder-plus / plan_unchecked / hidden：胜0、负0、平20；差值 0.0，8 类功能家族聚类 bootstrap 95% 区间 [0.0, 0.0]。
- deepseek/deepseek-v4-pro-0813 / linked_js / first_hidden：胜13、负5、平9；差值 0.2962962962962963，8 类功能家族聚类 bootstrap 95% 区间 [-0.041666666666666664, 0.5806451612903226]。
- deepseek/deepseek-v4-pro-0813 / linked_js / hidden：胜14、负0、平13；差值 0.5185185185185185，8 类功能家族聚类 bootstrap 95% 区间 [0.3333333333333333, 0.7307692307692307]。
- deepseek/deepseek-v4-pro-0813 / dna / first_hidden：胜1、负10、平16；差值 -0.3333333333333333，8 类功能家族聚类 bootstrap 95% 区间 [-0.5, -0.16666666666666666]。
- deepseek/deepseek-v4-pro-0813 / dna / hidden：胜1、负0、平26；差值 0.037037037037037035，8 类功能家族聚类 bootstrap 95% 区间 [0.0, 0.1111111111111111]。
- deepseek/deepseek-v4-pro-0813 / plan_unchecked / first_hidden：胜4、负6、平17；差值 -0.07407407407407407，8 类功能家族聚类 bootstrap 95% 区间 [-0.2916666666666667, 0.12]。
- deepseek/deepseek-v4-pro-0813 / plan_unchecked / hidden：胜7、负0、平20；差值 0.25925925925925924，8 类功能家族聚类 bootstrap 95% 区间 [0.07142857142857142, 0.5]。

区间按实际存在的功能家族聚类重采样，保留组内任务变体和全部重复采样；不把80个候选看作80类独立任务。家族数至多8，区间仍是小样本探索估计，退化为[0,0]不代表统计等价证明。主要比较为最终 plan_checked 对 linked_js，两个模型分别报告，其余为次要比较。

累计项目已结算 $2.412397；含未知预留敞口 $4.134746；未结算请求 45。未知费用未释放。

预先固定的源文件、需求、配置、分析规则和协议见 manifest.json 与 protocol.md；原始隐藏证据在 results.json 和 runs/。未以隐藏结果选择候选、修复或删减失败。
