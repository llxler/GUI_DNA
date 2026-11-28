# 问卷 · Question form

[Table 1](../../README.md#按数据集模型和方法查-table-1) / A / `web-bench/form`

每个目标是一项 Web-Bench 任务。候选页面通过该任务文件的全部官方断言计 1。分母是该模型四种方法共用的目标数。

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | ---: | ---: | ---: | ---: |
| Gemma 3 12B | [2/20](../../studies/results/paper-performance-matrix.json#L1314) | [7/20](../../studies/results/paper-performance-matrix.json#L1315) | [9/20](../../studies/results/paper-performance-matrix.json#L1316) | [2/20](../../studies/results/paper-performance-matrix.json#L1317) |
| Qwen3.5-9B | [2/20](../../studies/results/paper-performance-matrix.json#L3754) | [10/20](../../studies/results/paper-performance-matrix.json#L3755) | [15/20](../../studies/results/paper-performance-matrix.json#L3756) | [3/20](../../studies/results/paper-performance-matrix.json#L3757) |
| Mistral Small 3.2 | [7/20](../../studies/results/paper-performance-matrix.json#L6329) | [13/20](../../studies/results/paper-performance-matrix.json#L6330) | [14/20](../../studies/results/paper-performance-matrix.json#L6331) | [4/20](../../studies/results/paper-performance-matrix.json#L6332) |
| Qwen3-Coder-30B | [9/20](../../studies/results/paper-performance-matrix.json#L7417) | [15/20](../../studies/results/paper-performance-matrix.json#L7418) | [15/20](../../studies/results/paper-performance-matrix.json#L7419) | [7/20](../../studies/results/paper-performance-matrix.json#L7420) |
| GPT-OSS-120B | [12/20](../../studies/results/paper-performance-matrix.json#L8947) | [9/20](../../studies/results/paper-performance-matrix.json#L8948) | [11/20](../../studies/results/paper-performance-matrix.json#L8949) | [3/20](../../studies/results/paper-performance-matrix.json#L8950) |
| DeepSeek V4 Flash | [10/20](../../studies/results/paper-performance-matrix.json#L10391) | [20/20](../../studies/results/paper-performance-matrix.json#L10392) | [12/20](../../studies/results/paper-performance-matrix.json#L10393) | [11/20](../../studies/results/paper-performance-matrix.json#L10394) |
| DeepSeek V4 Pro | [6/20](../../studies/results/paper-performance-matrix.json#L11691) | [20/20](../../studies/results/paper-performance-matrix.json#L11692) | [13/20](../../studies/results/paper-performance-matrix.json#L11693) | [10/20](../../studies/results/paper-performance-matrix.json#L11694) |

点击成绩可定位到主表 JSON 的对应行。建库失败对应论文空白格，无数据对应横线。

<details>
<summary>查看各模型、各方法的来源记录</summary>

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | --- | --- | --- | --- |
| Gemma 3 12B | [实验记录](../../studies/webbench/form/survey_workflow/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/module_links/result.json) |
| Qwen3.5-9B | [实验记录](../../studies/webbench/form/survey_workflow/qwen_comparison/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/qwen_comparison/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/qwen_comparison/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/qwen_comparison/result.json) |
| Mistral Small 3.2 | [实验记录](../../studies/webbench/form/survey_workflow/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/module_links/result.json) |
| Qwen3-Coder-30B | [补测](../../studies/webbench/transport_completion/extension-result.json) | [补测](../../studies/webbench/transport_completion/extension-result.json) | [补测](../../studies/webbench/transport_completion/extension-result.json) | [实验记录](../../studies/webbench/typed_components/result.json) · [补测](../../studies/webbench/transport_completion/extension-result.json) |
| GPT-OSS-120B | [实验记录](../../studies/webbench/form/survey_workflow/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/result.json) | [实验记录](../../studies/webbench/form/survey_workflow/module_links/result.json) |
| DeepSeek V4 Flash | [实验记录](../../studies/webbench/form/flash_self_build/visible_targets/result.json) | [实验记录](../../studies/webbench/form/flash_self_build/visible_targets/result.json) | [实验记录](../../studies/webbench/form/flash_self_build/visible_targets/schema-transfer-result.json) | [实验记录](../../studies/webbench/form/flash_self_build/visible_targets/result.json) |
| DeepSeek V4 Pro | 见上表矩阵 | 见上表矩阵 | 见上表矩阵 | 见上表矩阵 |

</details>

在仓库根目录可查询单格的矩阵键、来源文件及适用的筛选条件。例如

```bash
python -m studies.lookup web-bench/form "Gemma 3 12B" Self
```
