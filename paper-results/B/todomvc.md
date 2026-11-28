# TodoMVC

[Table 1](../../README.md#按数据集模型和方法查-table-1) / B / `todomvc`

每个目标是一组待办功能。候选实现通过该组测试计 1。分母是该模型四种方法共用的目标数。

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | ---: | ---: | ---: | ---: |
| Gemma 3 4B | [2/8](../../studies/results/paper-performance-matrix.json#L12822) | [2/8](../../studies/results/paper-performance-matrix.json#L12823) | [6/8](../../studies/results/paper-performance-matrix.json#L12824) | [3/8](../../studies/results/paper-performance-matrix.json#L12825) |
| Llama 3.2 3B | [0/8](../../studies/results/paper-performance-matrix.json#L12890) | [1/8](../../studies/results/paper-performance-matrix.json#L12891) | [8/8](../../studies/results/paper-performance-matrix.json#L12892) | [1/8](../../studies/results/paper-performance-matrix.json#L12893) |
| Ministral 3B | [2/8](../../studies/results/paper-performance-matrix.json#L13057) | [1/8](../../studies/results/paper-performance-matrix.json#L13058) | [7/8](../../studies/results/paper-performance-matrix.json#L13059) | [6/8](../../studies/results/paper-performance-matrix.json#L13060) |
| Gemma 3 12B | [4/8](../../studies/results/paper-performance-matrix.json#L1202) | [8/8](../../studies/results/paper-performance-matrix.json#L1203) | [7/8](../../studies/results/paper-performance-matrix.json#L1205) | [5/8](../../studies/results/paper-performance-matrix.json#L1204) |
| Qwen3.5-9B | [1/8](../../studies/results/paper-performance-matrix.json#L3709) | [8/8](../../studies/results/paper-performance-matrix.json#L3710) | [5/8](../../studies/results/paper-performance-matrix.json#L3711) | [5/8](../../studies/results/paper-performance-matrix.json#L3712) |
| DeepSeek V4 Flash | [8/8](../../studies/results/paper-performance-matrix.json#L10670) | [4/8](../../studies/results/paper-performance-matrix.json#L10671) | [5/8](../../studies/results/paper-performance-matrix.json#L10672) | [8/8](../../studies/results/paper-performance-matrix.json#L10673) |

点击成绩可定位到主表 JSON 的对应行。建库失败对应论文空白格，无数据对应横线。

<details>
<summary>查看各模型、各方法的来源记录</summary>

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | --- | --- | --- | --- |
| Gemma 3 4B | [实验记录](../../studies/public_library_transfer/compact_todomvc/state_examples/result.json) | [实验记录](../../studies/public_library_transfer/compact_todomvc/state_examples/result.json) | [实验记录](../../studies/public_library_transfer/compact_todomvc/state_examples/result.json) | [实验记录](../../studies/public_library_transfer/compact_todomvc/route_preservation/result.json) |
| Llama 3.2 3B | [实验记录](../../studies/public_library_transfer/compact_todomvc/numbered_plans/result.json) | [实验记录](../../studies/public_library_transfer/compact_todomvc/slot_choices/last-result.json) | [实验记录](../../studies/public_library_transfer/compact_todomvc/slot_choices/last-result.json) | [实验记录](../../studies/public_library_transfer/compact_todomvc/slot_choices/last-result.json) |
| Ministral 3B | [实验记录](../../studies/public_library_transfer/compact_todomvc/state_examples/result.json) | [实验记录](../../studies/public_library_transfer/compact_todomvc/state_examples/result.json) | [实验记录](../../studies/public_library_transfer/compact_todomvc/state_examples/result.json) | [实验记录](../../studies/public_library_transfer/compact_todomvc/route_preservation/result.json) |
| Gemma 3 12B | 见上表矩阵 | 见上表矩阵 | 见上表矩阵 | 见上表矩阵 |
| Qwen3.5-9B | [实验记录](../../studies/public_library_transfer/source_diagnosis/visible_choices/result.json) | [实验记录](../../studies/public_library_transfer/source_diagnosis/visible_choices/result.json) | [实验记录](../../studies/public_library_transfer/source_diagnosis/visible_choices/result.json) | [实验记录](../../studies/public_library_transfer/source_diagnosis/visible_choices/core_profiles/result.json) |
| DeepSeek V4 Flash | [实验记录](../../studies/public_library_transfer/source_diagnosis/visible_choices/result.json) | [实验记录](../../studies/public_library_transfer/source_diagnosis/visible_choices/result.json) | [实验记录](../../studies/public_library_transfer/source_diagnosis/visible_choices/result.json) | [实验记录](../../studies/public_library_transfer/source_diagnosis/visible_choices/core_profiles/result.json) |

</details>

在仓库根目录可查询单格的矩阵键、来源文件及适用的筛选条件。例如

```bash
python -m studies.lookup todomvc "Gemma 3 4B" Self
```
