# 表格编辑器 · Table editor

[Table 1](../../README.md#按数据集模型和方法查-table-1) / A / `web-bench/table`

每个目标是一项 Web-Bench 任务。候选页面通过该任务文件的全部官方断言计 1。分母是该模型四种方法共用的目标数。

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | ---: | ---: | ---: | ---: |
| Gemma 3 12B | [0/20](../../studies/results/paper-performance-matrix.json#L1537) | [1/20](../../studies/results/paper-performance-matrix.json#L1538) | [9/20](../../studies/results/paper-performance-matrix.json#L2125) | [2/20](../../studies/results/paper-performance-matrix.json#L1540) |
| Qwen3.5-9B | [0/20](../../studies/results/paper-performance-matrix.json#L3602) | [6/20](../../studies/results/paper-performance-matrix.json#L3603) | [8/20](../../studies/results/paper-performance-matrix.json#L4366) | [3/20](../../studies/results/paper-performance-matrix.json#L3605) |
| Mistral Small 3.2 | [5/20](../../studies/results/paper-performance-matrix.json#L5969) | [20/20](../../studies/results/paper-performance-matrix.json#L5970) | [8/20](../../studies/results/paper-performance-matrix.json#L6452) | [1/20](../../studies/results/paper-performance-matrix.json#L6453) |
| Qwen3-Coder-30B | [3/20](../../studies/results/paper-performance-matrix.json#L7483) | [10/20](../../studies/results/paper-performance-matrix.json#L7484) | [9/20](../../studies/results/paper-performance-matrix.json#L7586) | [建库失败](../../studies/results/paper-performance-matrix.json#L7588) |
| GPT-OSS-120B | [7/20](../../studies/results/paper-performance-matrix.json#L8806) | [20/20](../../studies/results/paper-performance-matrix.json#L8807) | [8/20](../../studies/results/paper-performance-matrix.json#L9247) | [建库失败](../../studies/results/paper-performance-matrix.json#L9249) |
| DeepSeek V4 Flash | [1/20](../../studies/results/paper-performance-matrix.json#L10299) | [19/20](../../studies/results/paper-performance-matrix.json#L10300) | [9/20](../../studies/results/paper-performance-matrix.json#L11222) | [4/20](../../studies/results/paper-performance-matrix.json#L10302) |
| DeepSeek V4 Pro | [2/20](../../studies/results/paper-performance-matrix.json#L12474) | [20/20](../../studies/results/paper-performance-matrix.json#L12475) | [6/20](../../studies/results/paper-performance-matrix.json#L12548) | [6/20](../../studies/results/paper-performance-matrix.json#L12477) |

点击成绩可定位到主表 JSON 的对应行。建库失败对应论文空白格，无数据对应横线。

<details>
<summary>查看各模型、各方法的来源记录</summary>

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | --- | --- | --- | --- |
| Gemma 3 12B | [该行汇总](../../studies/results/library-source-diagnosis-20261126.json) | [该行汇总](../../studies/results/library-source-diagnosis-20261126.json) | [实验记录](../../studies/webbench/table/author_modules/result.json) | [该行汇总](../../studies/results/library-source-diagnosis-20261126.json) |
| Qwen3.5-9B | 见上表矩阵 | 见上表矩阵 | [实验记录](../../studies/webbench/table/author_modules/result.json) | [实验记录](../../studies/webbench/table/selection_binding/interaction_repairs/result.json) |
| Mistral Small 3.2 | [补测](../../studies/webbench/transport_completion/extension-result.json) | [补测](../../studies/webbench/transport_completion/extension-result.json) | [实验记录](../../studies/webbench/table/author_modules/result.json) | [实验记录](../../studies/webbench/table/event_hooks/handler_selection/result.json) |
| Qwen3-Coder-30B | [补测](../../studies/webbench/transport_completion/extension-result.json) | [补测](../../studies/webbench/transport_completion/extension-result.json) | [实验记录](../../studies/webbench/table/author_modules/result.json) | [实验记录](../../studies/webbench/table/event_hooks/handler_selection/result.json) |
| GPT-OSS-120B | 见上表矩阵 | 见上表矩阵 | [实验记录](../../studies/webbench/table/author_modules/result.json) | [实验记录](../../studies/webbench/table/event_hooks/dom_contract/result.json) |
| DeepSeek V4 Flash | 见上表矩阵 | 见上表矩阵 | [实验记录](../../studies/webbench/table/author_modules/result.json) | 见上表矩阵 |
| DeepSeek V4 Pro | 见上表矩阵 | 见上表矩阵 | [实验记录](../../studies/webbench/table/author_modules/result.json) | 见上表矩阵 |

</details>

在仓库根目录可查询单格的矩阵键、来源文件及适用的筛选条件。例如

```bash
python -m studies.lookup web-bench/table "Gemma 3 12B" Self
```
