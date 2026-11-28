# 文件管理器 · File explorer

[Table 1](../../README.md#按数据集模型和方法查-table-1) / A / `web-bench/dom1`

每个目标是一项 Web-Bench 任务。候选页面通过该任务文件的全部官方断言计 1。分母是该模型四种方法共用的目标数。

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | ---: | ---: | ---: | ---: |
| Gemma 3 12B | [3/20](../../studies/results/paper-performance-matrix.json#L1865) | [13/20](../../studies/results/paper-performance-matrix.json#L1866) | [9/20](../../studies/results/paper-performance-matrix.json#L1867) | [1/20](../../studies/results/paper-performance-matrix.json#L1868) |
| Qwen3.5-9B | [3/20](../../studies/results/paper-performance-matrix.json#L4129) | [5/20](../../studies/results/paper-performance-matrix.json#L4130) | [10/20](../../studies/results/paper-performance-matrix.json#L4131) | [1/20](../../studies/results/paper-performance-matrix.json#L4132) |
| GPT-OSS-120B | [6/20](../../studies/results/paper-performance-matrix.json#L9049) | [17/20](../../studies/results/paper-performance-matrix.json#L9050) | [10/20](../../studies/results/paper-performance-matrix.json#L9051) | [6/20](../../studies/results/paper-performance-matrix.json#L9052) |
| DeepSeek V4 Flash | [7/20](../../studies/results/paper-performance-matrix.json#L11035) | [10/20](../../studies/results/paper-performance-matrix.json#L11036) | [10/20](../../studies/results/paper-performance-matrix.json#L11037) | [2/20](../../studies/results/paper-performance-matrix.json#L11038) |

点击成绩可定位到主表 JSON 的对应行。建库失败对应论文空白格，无数据对应横线。

<details>
<summary>查看各模型、各方法的来源记录</summary>

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | --- | --- | --- | --- |
| Gemma 3 12B | [实验记录](../../studies/webbench/file_explorer/target_models/direct_reception/result.json) | [实验记录](../../studies/webbench/file_explorer/target_models/result.json) | [实验记录](../../studies/webbench/file_explorer/target_models/result.json) | [实验记录](../../studies/webbench/file_explorer/target_models/result.json) |
| Qwen3.5-9B | [实验记录](../../studies/webbench/file_explorer/target_models/direct_reception/result.json) | [实验记录](../../studies/webbench/file_explorer/interaction_contracts/entry_identity/result.json) | [实验记录](../../studies/webbench/file_explorer/interaction_contracts/entry_identity/result.json) | [实验记录](../../studies/webbench/file_explorer/interaction_contracts/entry_identity/result.json) |
| GPT-OSS-120B | [实验记录](../../studies/webbench/file_explorer/target_models/direct_reception/result.json) | [实验记录](../../studies/webbench/file_explorer/target_models/result.json) | [实验记录](../../studies/webbench/file_explorer/target_models/result.json) | [实验记录](../../studies/webbench/file_explorer/target_models/result.json) |
| DeepSeek V4 Flash | [实验记录](../../studies/webbench/file_explorer/target_models/direct_reception/result.json) | [实验记录](../../studies/webbench/file_explorer/interaction_contracts/entry_identity/result.json) | [实验记录](../../studies/webbench/file_explorer/interaction_contracts/entry_identity/result.json) | [实验记录](../../studies/webbench/file_explorer/interaction_contracts/entry_identity/result.json) |

</details>

在仓库根目录可查询单格的矩阵键、来源文件及适用的筛选条件。例如

```bash
python -m studies.lookup web-bench/dom1 "Gemma 3 12B" Self
```
