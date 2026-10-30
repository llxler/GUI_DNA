# 第二轮：原子函数与可检查组合计划

这是依据第一轮发现设计的新探索实验；第一轮指标与结果保持独立。所有隐藏检查均在全部生成结束后运行。

| 模型 | 方法 | 首次行为通过 | 最终行为通过 | 内部状态合规 | 基础保留 | 费用 USD | 修复轮数 | 输出 tokens | 平均生成秒 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-pro-0813 | direct | 10/12 | 12/12 | 12/12 | 100.0% | 0.051505 | 2 | 14908 | 33.2 |
| deepseek/deepseek-v4-pro-0813 | retrieval | 10/12 | 12/12 | 12/12 | 100.0% | 0.061451 | 3 | 14169 | 30.3 |
| deepseek/deepseek-v4-pro-0813 | dna | 11/12 | 11/12 | 11/12 | 92.6% | 0.051329 | 2 | 12100 | 22.7 |
| deepseek/deepseek-v4-pro-0813 | metadata | 11/12 | 11/12 | 11/12 | 98.1% | 0.079816 | 2 | 14757 | 17.7 |
| deepseek/deepseek-v4-pro-0813 | checks | 8/12 | 9/12 | 9/12 | 87.0% | 0.055373 | 7 | 14933 | 23.3 |
| deepseek/deepseek-v4-pro-0813 | constrained | 11/12 | 11/12 | 11/12 | 98.1% | 0.046913 | 2 | 13133 | 19.8 |
| deepseek/deepseek-v4-pro-0813 | deterministic | 12/12 | 12/12 | 12/12 | 100.0% | 0.000000 | 0 | 0 | 4.2 |
| deepseek/deepseek-v4-pro-0813 | compiled | 7/12 | 10/12 | 10/12 | 83.3% | 0.047890 | 8 | 3105 | 14.3 |
| qwen/qwen3-coder-plus | direct | 5/12 | 9/12 | 9/12 | 98.1% | 0.116259 | 11 | 29279 | 25.2 |
| qwen/qwen3-coder-plus | retrieval | 10/12 | 11/12 | 11/12 | 100.0% | 0.059766 | 1 | 13385 | 13.9 |
| qwen/qwen3-coder-plus | dna | 10/12 | 12/12 | 12/12 | 100.0% | 0.070625 | 2 | 16122 | 15.6 |
| qwen/qwen3-coder-plus | metadata | 12/12 | 12/12 | 12/12 | 100.0% | 0.068572 | 0 | 13205 | 13.7 |
| qwen/qwen3-coder-plus | checks | 11/12 | 11/12 | 11/12 | 98.1% | 0.060991 | 2 | 15786 | 16.2 |
| qwen/qwen3-coder-plus | constrained | 12/12 | 12/12 | 12/12 | 100.0% | 0.053766 | 0 | 13954 | 14.6 |
| qwen/qwen3-coder-plus | deterministic | 12/12 | 12/12 | 12/12 | 100.0% | 0.000000 | 0 | 0 | 4.1 |
| qwen/qwen3-coder-plus | compiled | 4/12 | 5/12 | 5/12 | 42.6% | 0.076434 | 15 | 10546 | 11.8 |

完整八方法组 24，未完成组 0。仅完整组进入表格。

首次/最终行为通过要求所有隐藏操作序列的可见行、控件、草稿、计数与按钮状态正确；内部状态合规另外比较完整规范状态，不用于主行为指标。基础保留按独立功能场景计算。费用和时间含公开检查与修复，不含共用库来源成本及最终隐藏评价。

direct=直接生成；retrieval=开发实现检索；dna=原子函数＋分解；metadata=仅加状态约束说明；checks=仅加运行约束检查；constrained=说明＋检查；compiled=说明＋检查＋模型组合计划编译；deterministic=不调用模型，按已知功能直接构造同一编译计划。全部库方法共享相同函数代码。compiled 的编译器是被测机制，不是所有方法共用的渲染框架。确定性参照按组重复展示，不是独立模型采样。

配对比较（compiled 相对基线）：

- deepseek/deepseek-v4-pro-0813 / direct / first_hidden：胜 1、负 4、平 7。
- deepseek/deepseek-v4-pro-0813 / direct / hidden：胜 0、负 2、平 10。
- deepseek/deepseek-v4-pro-0813 / retrieval / first_hidden：胜 0、负 3、平 9。
- deepseek/deepseek-v4-pro-0813 / retrieval / hidden：胜 0、负 2、平 10。
- deepseek/deepseek-v4-pro-0813 / dna / first_hidden：胜 0、负 4、平 8。
- deepseek/deepseek-v4-pro-0813 / dna / hidden：胜 0、负 1、平 11。
- deepseek/deepseek-v4-pro-0813 / metadata / first_hidden：胜 1、负 5、平 6。
- deepseek/deepseek-v4-pro-0813 / metadata / hidden：胜 1、负 2、平 9。
- deepseek/deepseek-v4-pro-0813 / checks / first_hidden：胜 3、负 4、平 5。
- deepseek/deepseek-v4-pro-0813 / checks / hidden：胜 3、负 2、平 7。
- deepseek/deepseek-v4-pro-0813 / constrained / first_hidden：胜 1、负 5、平 6。
- deepseek/deepseek-v4-pro-0813 / constrained / hidden：胜 1、负 2、平 9。
- deepseek/deepseek-v4-pro-0813 / deterministic / first_hidden：胜 0、负 5、平 7。
- deepseek/deepseek-v4-pro-0813 / deterministic / hidden：胜 0、负 2、平 10。
- qwen/qwen3-coder-plus / direct / first_hidden：胜 4、负 5、平 3。
- qwen/qwen3-coder-plus / direct / hidden：胜 2、负 6、平 4。
- qwen/qwen3-coder-plus / retrieval / first_hidden：胜 1、负 7、平 4。
- qwen/qwen3-coder-plus / retrieval / hidden：胜 1、负 7、平 4。
- qwen/qwen3-coder-plus / dna / first_hidden：胜 1、负 7、平 4。
- qwen/qwen3-coder-plus / dna / hidden：胜 0、负 7、平 5。
- qwen/qwen3-coder-plus / metadata / first_hidden：胜 0、负 8、平 4。
- qwen/qwen3-coder-plus / metadata / hidden：胜 0、负 7、平 5。
- qwen/qwen3-coder-plus / checks / first_hidden：胜 0、负 7、平 5。
- qwen/qwen3-coder-plus / checks / hidden：胜 0、负 6、平 6。
- qwen/qwen3-coder-plus / constrained / first_hidden：胜 0、负 8、平 4。
- qwen/qwen3-coder-plus / constrained / hidden：胜 0、负 7、平 5。
- qwen/qwen3-coder-plus / deterministic / first_hidden：胜 0、负 8、平 4。
- qwen/qwen3-coder-plus / deterministic / hidden：胜 0、负 7、平 5。

累计项目已结算 $1.578579；含全部未结算预留的记账敞口 $3.300928。共用第一轮库构建费 $0.060082 已包含在项目总额中，新原子化库为人工重构，未额外调用模型构建。

小样本不构成稳定收益或统计显著性结论。编译方法表达空间更窄，依赖人工定义的接口与合法组合规则；不能将编译保证外推到任意 GUI。
