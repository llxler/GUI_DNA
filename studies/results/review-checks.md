# 审稿问题复核（包含 R2–R5）（零 API，`uv run python -m test.review_checks`）

## 1. TodoMVC：编译器冻结之后才生成的采样（s2–s4，无重放）

| 模型 | 自由代码 | GUI-DNA | 配对 | 仅 DNA 过 | 仅自由过 |
|---|---:|---:|---:|---:|---:|
| deepseek-v4-pro-0813 | 24/24 | 24/24 | 24 | 0 | 0 |
| qwen3-coder-30b-a3b-instruct | 24/24 | 24/24 | 24 | 0 | 0 |
| mistral-small-3.2-24b-instruct | 20/24 | 24/24 | 24 | 4 | 0 |
| gemma-3-12b-it | 8/19 | 21/21 | 18 | 10 | 0 |
| gpt-5-mini | 24/24 | 24/24 | 24 | 0 | 0 |
| gpt-oss-120b | 24/24 | 24/24 | 24 | 0 | 0 |
| gemini-2.5-flash | 24/24 | 24/24 | 24 | 0 | 0 |
| claude-haiku-4.5 | 24/24 | 24/24 | 24 | 0 | 0 |
| **合计** | 172/187 | 189/189 | 186 | 14 | 0 |

## 2. 各做法已结算费用（8 模型合计，USD）

| 数据集 | free | rule | dna | free_lib | dna_unchecked |
|---|---:|---:|---:|---:|---:|
| webbench | 1.874 | 0.000 | 0.225 | 1.766 | 0.213 |
| todomvc | 0.672 | 0.000 | 0.464 | 0.278 | 0.181 |

## 3. 自建任务：修复后才对的候选，首个版本是否被编译器拒绝（47 个完整组）

| 做法 | 修复后才对 | 其中首个版本被编译器拒绝 | 其中首个版本只是公开检查失败 | 静态拒绝总数 |
|---|---:|---:|---:|---:|
| Free | 10 | 0 | 10 | 1 |
| Free+Lib | 3 | 2 | 1 | 2 |
| Plan- | 5 | 1 | 4 | 2 |
| GUI-DNA | 14 | 13 | 1 | 13 |

## 4. Web-Bench 顺序协议下的错误继承

逐任务通过的模型数（/8，任务 1–20）：

- `free`: 7 7 7 0 2 1 2 0 0 0 3 2 2 1 2 4 6 7 1 0（合计 54）
- `free_lib`: 7 7 7 5 6 5 5 4 0 4 6 6 6 5 6 6 5 5 4 0（合计 99）
- `dna`: 8 8 7 6 8 8 7 3 1 6 8 7 7 7 7 8 7 7 7 5（合计 132）

首个失败任务：

- `free`: qwen3-coder-30b-a3b-instruct 2，mistral-small-3.2-24b-instruct 4，gemma-3-12b-it 1，deepseek-v4-flash 4，gpt-oss-120b 4，gemini-2.5-flash 4，gpt-5-mini 4，claude-haiku-4.5 4
- `free_lib`: qwen3-coder-30b-a3b-instruct 6，mistral-small-3.2-24b-instruct 4，gemma-3-12b-it 1，deepseek-v4-flash 9，gpt-oss-120b 9，gemini-2.5-flash 9，gpt-5-mini 4，claude-haiku-4.5 9
- `dna`: qwen3-coder-30b-a3b-instruct 8，mistral-small-3.2-24b-instruct 8，gemma-3-12b-it 3，deepseek-v4-flash 9，gpt-oss-120b 8，gemini-2.5-flash 无，gpt-5-mini 8，claude-haiku-4.5 4

| 做法 | 上一任务通过时本任务通过 | 上一任务失败时本任务通过 |
|---|---:|---:|
| free | 29/54 | 18/98 |
| free_lib | 82/99 | 10/53 |

GUI-DNA 对自由代码的 79 个配对胜出里，23 个出现在首个任务或自由代码上一任务仍通过之后，56 个出现在自由代码上一任务已失败之后（可能含继承的错误）。

槽位指标是与参考方案的逐字选择一致率，不等于行为正确率；等价变体可能同样过测试，缺失/无可执行方案仍计入分母。

## 5a. 槽位参考一致率：Web-Bench dom1（slot_first_attempt，一致数 / 启用槽位数）

| 模型 | select | fileClick | insert | delete | drag | menuLabel | 合计 |
|---|---:|---:|---:|---:|---:|---:|---:|
| qwen3-coder-30b-a3b-instruct | 18/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 92/93 |
| mistral-small-3.2-24b-instruct | 8/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 82/93 |
| gemma-3-12b-it | 0/19 | 2/19 | 9/17 | 13/16 | 8/15 | 2/7 | 34/93 |
| deepseek-v4-flash | 18/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 92/93 |
| gpt-oss-120b | 17/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 91/93 |
| gemini-2.5-flash | 17/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 91/93 |
| gpt-5-mini | 19/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 93/93 |
| claude-haiku-4.5 | 1/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 75/93 |
| **合计** | 98/152 | 135/152 | 128/136 | 125/128 | 113/120 | 51/56 | **650/744** |

## 5b. 槽位参考一致率：TodoMVC（slot_first_attempt，一致数 / 启用槽位数）

| 模型 | init | add | visible | countText | toggle | save | cancel | toggleAll | clearCompleted | 合计 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek-v4-pro-0813 | 16/16 | 16/16 | 10/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 82/88 |
| qwen3-coder-30b-a3b-instruct | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| mistral-small-3.2-24b-instruct | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| gemma-3-12b-it | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| gpt-5-mini | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| gpt-oss-120b | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| gemini-2.5-flash | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| claude-haiku-4.5 | 8/16 | 8/16 | 8/16 | 6/6 | 6/12 | 4/6 | 4/6 | 2/4 | 6/6 | 52/88 |
| **合计** | 120/128 | 120/128 | 114/128 | 48/48 | 90/96 | 46/48 | 46/48 | 30/32 | 48/48 | **662/704** |

## 5a. 槽位参考一致率：Web-Bench dom1（slot_accuracy，一致数 / 启用槽位数）

| 模型 | select | fileClick | insert | delete | drag | menuLabel | 合计 |
|---|---:|---:|---:|---:|---:|---:|---:|
| qwen3-coder-30b-a3b-instruct | 18/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 92/93 |
| mistral-small-3.2-24b-instruct | 8/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 82/93 |
| gemma-3-12b-it | 0/19 | 2/19 | 6/17 | 8/16 | 5/15 | 1/7 | 22/93 |
| deepseek-v4-flash | 18/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 92/93 |
| gpt-oss-120b | 17/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 91/93 |
| gemini-2.5-flash | 18/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 92/93 |
| gpt-5-mini | 19/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 93/93 |
| claude-haiku-4.5 | 1/19 | 19/19 | 17/17 | 16/16 | 15/15 | 7/7 | 75/93 |
| **合计** | 99/152 | 135/152 | 125/136 | 120/128 | 110/120 | 50/56 | **639/744** |

## 5b. 槽位参考一致率：TodoMVC（slot_accuracy，一致数 / 启用槽位数）

| 模型 | init | add | visible | countText | toggle | save | cancel | toggleAll | clearCompleted | 合计 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek-v4-pro-0813 | 16/16 | 16/16 | 10/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 82/88 |
| qwen3-coder-30b-a3b-instruct | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| mistral-small-3.2-24b-instruct | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| gemma-3-12b-it | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| gpt-5-mini | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| gpt-oss-120b | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| gemini-2.5-flash | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| claude-haiku-4.5 | 16/16 | 16/16 | 16/16 | 6/6 | 12/12 | 6/6 | 6/6 | 4/4 | 6/6 | 88/88 |
| **合计** | 128/128 | 128/128 | 122/128 | 48/48 | 96/96 | 48/48 | 48/48 | 32/32 | 48/48 | **698/704** |

## 6. Web-Bench 上 GUI-DNA 剩余的 28 个失败任务

| 原因 | 任务数（可多选） | 按固定顺序分组（非因果） |
|---|---:|---:|
| 没有可执行版本 | 10 | 10 |
| 变体不同于参考（不必然导致失败） | 8 | 8 |
| 菜单多接了命令 | 17 | 10 |

逐条：qwen3-coder-30b-a3b-instruct task-8（extra_command）；qwen3-coder-30b-a3b-instruct task-9（extra_command）；qwen3-coder-30b-a3b-instruct task-10（extra_command）；mistral-small-3.2-24b-instruct task-8（variant+extra_command）；mistral-small-3.2-24b-instruct task-9（variant+extra_command）；gemma-3-12b-it task-3（rejected）；gemma-3-12b-it task-4（rejected）；gemma-3-12b-it task-7（variant+extra_command）；gemma-3-12b-it task-8（variant+extra_command）；gemma-3-12b-it task-9（rejected）；gemma-3-12b-it task-10（variant+extra_command）；gemma-3-12b-it task-12（rejected）；gemma-3-12b-it task-13（rejected）；gemma-3-12b-it task-14（rejected）；gemma-3-12b-it task-15（rejected）；gemma-3-12b-it task-17（rejected）；gemma-3-12b-it task-18（rejected）；gemma-3-12b-it task-19（rejected）；gemma-3-12b-it task-20（variant+extra_command）；deepseek-v4-flash task-9（extra_command）；deepseek-v4-flash task-20（extra_command）；gpt-oss-120b task-8（extra_command）；gpt-oss-120b task-9（extra_command）；gpt-oss-120b task-20（extra_command）；gpt-5-mini task-8（extra_command）；gpt-5-mini task-9（extra_command）；claude-haiku-4.5 task-4（variant）；claude-haiku-4.5 task-9（variant+extra_command）

## 7. 覆盖检查重放：「方案不做覆盖检查」的最终方案会不会被检查拒绝

| 数据集 | 已编译的最终方案 | 会被覆盖检查拒绝 | 没有可编译方案 |
|---|---:|---:|---:|
| webbench | 155 | 8（mistral-small-3.2-24b-instruct 4，gemma-3-12b-it 4） | 5 |
| todomvc | 128 | 0（无） | 0 |

## 8. 探索性精确检验（双侧）

McNemar 的二项参考分布假定配对任务彼此独立；Web-Bench 顺序任务不满足此条件。下列 p 仅是该假设下的参考值，不是解决顺序依赖后的显著性结论；合并任务的 p 不作为证据。跨模型符号检验也依赖模型独立/可交换假设，不能替代项目级复现。

### webbench

| 模型 | 仅 DNA 过 | 仅自由过 | p |
|---|---:|---:|---:|
| qwen3-coder-30b-a3b-instruct | 12 | 0 | 0.0005 |
| mistral-small-3.2-24b-instruct | 13 | 0 | 0.0002 |
| gemma-3-12b-it | 5 | 1 | 0.2188 |
| deepseek-v4-flash | 6 | 0 | 0.0312 |
| gpt-oss-120b | 10 | 0 | 0.0020 |
| gemini-2.5-flash | 9 | 0 | 0.0039 |
| gpt-5-mini | 12 | 0 | 0.0005 |
| claude-haiku-4.5 | 12 | 0 | 0.0005 |

变好 8 个模型、变差 0 个、持平 0 个；符号检验双侧 p = 0.0078。合并不一致对 79 比 1（仅描述）。

### todomvc

| 模型 | 仅 DNA 过 | 仅自由过 | p |
|---|---:|---:|---:|
| deepseek-v4-pro-0813 | 0 | 0 | 1.0000 |
| qwen3-coder-30b-a3b-instruct | 1 | 0 | 1.0000 |
| mistral-small-3.2-24b-instruct | 4 | 0 | 0.1250 |
| gemma-3-12b-it | 7 | 0 | 0.0156 |
| gpt-5-mini | 0 | 0 | 1.0000 |
| gpt-oss-120b | 0 | 0 | 1.0000 |
| gemini-2.5-flash | 0 | 0 | 1.0000 |
| claude-haiku-4.5 | 0 | 0 | 1.0000 |

变好 3 个模型、变差 0 个、持平 5 个；符号检验双侧 p = 0.2500。合并不一致对 12 比 0（仅描述）。
