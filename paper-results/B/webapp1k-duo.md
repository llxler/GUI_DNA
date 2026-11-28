# WebApp1K-Duo

[Table 1](../../README.md#按数据集模型和方法查-table-1) / B / `webapp1k-duo`

每个目标是一对业务功能。该组合的四个测试用例全部通过计 1。分母是该模型四种方法共用的目标数。

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | ---: | ---: | ---: | ---: |
| Gemma 3 12B | [1/5](../../studies/results/paper-performance-matrix.json#L2183) | [1/5](../../studies/results/paper-performance-matrix.json#L2184) | [4/5](../../studies/results/paper-performance-matrix.json#L2185) | [3/5](../../studies/results/paper-performance-matrix.json#L2186) |
| Qwen3.5-9B | [2/5](../../studies/results/paper-performance-matrix.json#L4476) | [2/5](../../studies/results/paper-performance-matrix.json#L4477) | [4/5](../../studies/results/paper-performance-matrix.json#L4478) | [4/5](../../studies/results/paper-performance-matrix.json#L4479) |
| Mistral Small 3.2 | [0/10](../../studies/results/paper-performance-matrix.json#L6698) | [8/10](../../studies/results/paper-performance-matrix.json#L6699) | [9/10](../../studies/results/paper-performance-matrix.json#L6700) | [8/10](../../studies/results/paper-performance-matrix.json#L6701) |
| Qwen3-Coder-30B | [4/10](../../studies/results/paper-performance-matrix.json#L7885) | [4/10](../../studies/results/paper-performance-matrix.json#L7886) | [9/10](../../studies/results/paper-performance-matrix.json#L7887) | [8/10](../../studies/results/paper-performance-matrix.json#L7888) |
| GPT-OSS-120B | [5/10](../../studies/results/paper-performance-matrix.json#L9634) | [8/10](../../studies/results/paper-performance-matrix.json#L9635) | [9/10](../../studies/results/paper-performance-matrix.json#L9636) | [9/10](../../studies/results/paper-performance-matrix.json#L9637) |
| DeepSeek V4 Flash | [9/10](../../studies/results/paper-performance-matrix.json#L11550) | [7/10](../../studies/results/paper-performance-matrix.json#L11551) | [9/10](../../studies/results/paper-performance-matrix.json#L11552) | [9/10](../../studies/results/paper-performance-matrix.json#L11553) |

点击成绩可定位到主表 JSON 的对应行。建库失败对应论文空白格，无数据对应横线。

<details>
<summary>查看各模型、各方法的来源记录</summary>

| 目标生成模型 | Direct | Human | GPT-5 | Self |
| --- | --- | --- | --- | --- |
| Gemma 3 12B | [实验记录](../../studies/results/backbone-suites-20261124.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/form_sdk/declared_config/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) |
| Qwen3.5-9B | [实验记录](../../studies/results/backbone-suites-20261124.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/form_sdk/declared_config/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) |
| Mistral Small 3.2 | [实验记录](../../studies/results/backbone-suites-20261124.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/form_sdk/declared_config/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) |
| Qwen3-Coder-30B | [实验记录](../../studies/results/backbone-suites-20261124.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/form_sdk/declared_config/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) |
| GPT-OSS-120B | [实验记录](../../studies/results/backbone-suites-20261124.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/form_sdk/declared_config/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) |
| DeepSeek V4 Flash | [实验记录](../../studies/public_library_transfer/duo_react_callbacks/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/form_sdk/declared_config/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) | [实验记录](../../studies/public_library_transfer/duo_verified_features/field_bindings/result.json) |

</details>

在仓库根目录可查询单格的矩阵键、来源文件及适用的筛选条件。例如

```bash
python -m studies.lookup webapp1k-duo "Gemma 3 12B" Self
```
