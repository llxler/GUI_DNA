# 计算器 · Calculator

[Table 1](../../README.md#按数据集模型和方法查-table-1) / A / `web-bench/calculator`

每个目标是一项 Web-Bench 任务。候选页面通过该任务文件的全部官方断言计 1。分母是该模型四种方法共用的目标数。

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | ---: | ---: | ---: | ---: |
| Gemma 3 12B | [8/20](../../studies/results/paper-performance-matrix.json#L1925) | [16/20](../../studies/results/paper-performance-matrix.json#L1926) | [7/20](../../studies/results/paper-performance-matrix.json#L2257) | [6/20](../../studies/results/paper-performance-matrix.json#L1971) |
| Qwen3.5-9B | [4/20](../../studies/results/paper-performance-matrix.json#L4187) | [20/20](../../studies/results/paper-performance-matrix.json#L4188) | [11/20](../../studies/results/paper-performance-matrix.json#L4497) | [2/20](../../studies/results/paper-performance-matrix.json#L4237) |
| GPT-OSS-120B | [10/20](../../studies/results/paper-performance-matrix.json#L9109) | [20/20](../../studies/results/paper-performance-matrix.json#L9110) | [11/20](../../studies/results/paper-performance-matrix.json#L9496) | [10/20](../../studies/results/paper-performance-matrix.json#L9154) |
| DeepSeek V4 Flash | [10/20](../../studies/results/paper-performance-matrix.json#L11093) | [16/20](../../studies/results/paper-performance-matrix.json#L11094) | [10/20](../../studies/results/paper-performance-matrix.json#L11358) | [11/20](../../studies/results/paper-performance-matrix.json#L11138) |

点击成绩可定位到主表 JSON 的对应行。建库失败对应论文空白格，无数据对应横线。

<details>
<summary>查看各模型、各方法的来源记录</summary>

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | --- | --- | --- | --- |
| Gemma 3 12B | [实验记录](../../studies/webbench/calculator/target_models/result.json) | [实验记录](../../studies/webbench/calculator/target_models/result.json) | [实验记录](../../studies/webbench/calculator/gpt5_profiles/mount_recovery/result.json) | [实验记录](../../studies/webbench/calculator/memory_recall/result.json) |
| Qwen3.5-9B | [实验记录](../../studies/webbench/calculator/key_groups/result.json) | [实验记录](../../studies/webbench/calculator/key_groups/result.json) | [实验记录](../../studies/webbench/calculator/gpt5_profiles/mount_recovery/result.json) | [实验记录](../../studies/webbench/calculator/key_programs/individual_keys/result.json) |
| GPT-OSS-120B | [实验记录](../../studies/webbench/calculator/target_models/result.json) | [实验记录](../../studies/webbench/calculator/target_models/result.json) | [实验记录](../../studies/webbench/calculator/gpt5_profiles/mount_recovery/result.json) | [实验记录](../../studies/webbench/calculator/key_programs/result.json) |
| DeepSeek V4 Flash | [实验记录](../../studies/webbench/calculator/key_groups/result.json) | [实验记录](../../studies/webbench/calculator/key_groups/result.json) | [实验记录](../../studies/webbench/calculator/gpt5_profiles/mount_recovery/result.json) | [实验记录](../../studies/webbench/calculator/key_programs/result.json) |

</details>

在仓库根目录可查询单格的矩阵键、来源文件及适用的筛选条件。例如

```bash
python -m studies.lookup web-bench/calculator "Gemma 3 12B" Self
```
