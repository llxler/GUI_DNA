# SVG 图表 · SVG charts

[Table 1](../../README.md#按数据集模型和方法查-table-1) / A / `web-bench/svg-chart`

每个目标是一项 Web-Bench 任务。候选页面通过该任务文件的全部官方断言计 1。分母是该模型四种方法共用的目标数。

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | ---: | ---: | ---: | ---: |
| Gemma 3 12B | [2/20](../../studies/results/paper-performance-matrix.json#L984) | [2/20](../../studies/results/paper-performance-matrix.json#L985) | [15/20](../../studies/results/paper-performance-matrix.json#L986) | [3/20](../../studies/results/paper-performance-matrix.json#L987) |
| Qwen3.5-9B | [0/20](../../studies/results/paper-performance-matrix.json#L3733) | [5/20](../../studies/results/paper-performance-matrix.json#L3734) | [15/20](../../studies/results/paper-performance-matrix.json#L3735) | [3/20](../../studies/results/paper-performance-matrix.json#L3736) |
| Mistral Small 3.2 | [3/19](../../studies/results/paper-performance-matrix.json#L6537) | [12/19](../../studies/results/paper-performance-matrix.json#L6538) | [7/19](../../studies/results/paper-performance-matrix.json#L6539) | [3/19](../../studies/results/paper-performance-matrix.json#L6540) |
| Qwen3-Coder-30B | [0/20](../../studies/results/paper-performance-matrix.json#L7512) | [12/20](../../studies/results/paper-performance-matrix.json#L7513) | [17/20](../../studies/results/paper-performance-matrix.json#L7514) | [6/20](../../studies/results/paper-performance-matrix.json#L7515) |
| GPT-OSS-120B | [2/20](../../studies/results/paper-performance-matrix.json#L9111) | [20/20](../../studies/results/paper-performance-matrix.json#L9112) | [16/20](../../studies/results/paper-performance-matrix.json#L9113) | [7/20](../../studies/results/paper-performance-matrix.json#L9114) |
| DeepSeek V4 Flash | [1/20](../../studies/results/paper-performance-matrix.json#L10502) | [20/20](../../studies/results/paper-performance-matrix.json#L10503) | [16/20](../../studies/results/paper-performance-matrix.json#L10504) | [7/20](../../studies/results/paper-performance-matrix.json#L10505) |
| DeepSeek V4 Pro | [3/20](../../studies/results/paper-performance-matrix.json#L12681) | [20/20](../../studies/results/paper-performance-matrix.json#L12682) | [17/20](../../studies/results/paper-performance-matrix.json#L12683) | [10/20](../../studies/results/paper-performance-matrix.json#L12684) |

点击成绩可定位到主表 JSON 的对应行。建库失败对应论文空白格，无数据对应横线。

<details>
<summary>查看各模型、各方法的来源记录</summary>

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | --- | --- | --- | --- |
| Gemma 3 12B | 见上表矩阵 | 见上表矩阵 | 见上表矩阵 | [实验记录](../../studies/webbench/typed_components/result.json) |
| Qwen3.5-9B | [该行汇总](../../studies/results/library-source-diagnosis-20261126.json) | [该行汇总](../../studies/results/library-source-diagnosis-20261126.json) | [实验记录](../../studies/public_library_transfer/source_diagnosis/result.json) | [实验记录](../../studies/webbench/typed_components/svg_public_geometry/attribute_contracts/result.json) |
| Mistral Small 3.2 | [该行汇总](../../studies/results/library-source-diagnosis-20261126.json) | [该行汇总](../../studies/results/library-source-diagnosis-20261126.json) | [该行汇总](../../studies/results/library-source-diagnosis-20261126.json) | [实验记录](../../studies/webbench/typed_components/svg_public_geometry/attribute_contracts/result.json) |
| Qwen3-Coder-30B | [补测](../../studies/webbench/transport_completion/extension-result.json) | [补测](../../studies/webbench/transport_completion/extension-result.json) | [补测](../../studies/webbench/transport_completion/extension-result.json) | [实验记录](../../studies/webbench/typed_components/result.json) · [补测](../../studies/webbench/transport_completion/extension-result.json) |
| GPT-OSS-120B | 见上表矩阵 | 见上表矩阵 | 见上表矩阵 | [实验记录](../../studies/webbench/typed_components/svg_public_geometry/decoration/helpers-result.json) |
| DeepSeek V4 Flash | 见上表矩阵 | 见上表矩阵 | 见上表矩阵 | [实验记录](../../studies/webbench/typed_components/result.json) |
| DeepSeek V4 Pro | [补测](../../studies/webbench/transport_completion/extension-result.json) | [补测](../../studies/webbench/transport_completion/extension-result.json) | [补测](../../studies/webbench/transport_completion/extension-result.json) | [实验记录](../../studies/webbench/typed_components/result.json) · [补测](../../studies/webbench/transport_completion/extension-result.json) |

</details>

在仓库根目录可查询单格的矩阵键、来源文件及适用的筛选条件。例如

```bash
python -m studies.lookup web-bench/svg-chart "Gemma 3 12B" Self
```
