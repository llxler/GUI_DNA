# WebGen-Bench

[Table 1](../../README.md#按数据集模型和方法查-table-1) / C / `webgen-bench`

每个目标是一项网站操作。浏览器判定完整完成计 1，部分完成计 0。分母是该模型四种方法共用的目标数。

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | ---: | ---: | ---: | ---: |
| Gemma 3 12B | [29/59](../../studies/results/paper-performance-matrix.json#L1720) | [41/59](../../studies/results/paper-performance-matrix.json#L1721) | [35/59](../../studies/results/paper-performance-matrix.json#L1722) | [33/59](../../studies/results/paper-performance-matrix.json#L1723) |
| Qwen3.5-9B | [27/59](../../studies/results/paper-performance-matrix.json#L3973) | [37/59](../../studies/results/paper-performance-matrix.json#L3974) | [34/59](../../studies/results/paper-performance-matrix.json#L3975) | [28/59](../../studies/results/paper-performance-matrix.json#L3976) |
| DeepSeek V4 Flash | [37/59](../../studies/results/paper-performance-matrix.json#L10897) | [41/59](../../studies/results/paper-performance-matrix.json#L10898) | [45/59](../../studies/results/paper-performance-matrix.json#L10899) | [41/59](../../studies/results/paper-performance-matrix.json#L10900) |

点击成绩可定位到主表 JSON 的对应行。建库失败对应论文空白格，无数据对应横线。

<details>
<summary>查看各模型、各方法的来源记录</summary>

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | --- | --- | --- | --- |
| Gemma 3 12B | [实验记录](../../studies/webgen_bench/site_completion/judgments.json) · [补判](../../studies/webgen_bench/site_completion/completed-verdicts.json) | [实验记录](../../studies/webgen_bench/site_completion/vertical-primary.json) · [补判](../../studies/webgen_bench/site_completion/completed-verdicts.json) | [实验记录](../../studies/webgen_bench/site_completion/judgments.json) | [实验记录](../../studies/webgen_bench/site_completion/judgments.json) |
| Qwen3.5-9B | [实验记录](../../studies/webgen_bench/site_completion/judgments.json) · [补判](../../studies/webgen_bench/site_completion/completed-verdicts.json) | [实验记录](../../studies/webgen_bench/site_completion/vertical-primary.json) · [补判](../../studies/webgen_bench/site_completion/completed-verdicts.json) | [实验记录](../../studies/webgen_bench/site_completion/judgments.json) · [补判](../../studies/webgen_bench/site_completion/completed-verdicts.json) | [实验记录](../../studies/webgen_bench/site_completion/judgments.json) · [补判](../../studies/webgen_bench/site_completion/completed-verdicts.json) |
| DeepSeek V4 Flash | [实验记录](../../studies/webgen_bench/site_completion/judgments.json) · [补判](../../studies/webgen_bench/site_completion/completed-verdicts.json) | [实验记录](../../studies/webgen_bench/site_completion/vertical-primary.json) | [实验记录](../../studies/webgen_bench/site_completion/judgments.json) | [实验记录](../../studies/webgen_bench/site_completion/judgments.json) |

</details>

在仓库根目录可查询单格的矩阵键、来源文件及适用的筛选条件。例如

```bash
python -m studies.lookup webgen-bench "Gemma 3 12B" Self
```
