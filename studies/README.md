# GUI-DNA 论文研究

`studies/` 保存论文的实验协议、生成与评分代码，以及可核验的结果。在仓库根目录运行 `python -m studies.lookup` 可列出 Table 1 项目，依次追加项目、模型和方法可定位单格成绩、矩阵键和来源。下表按研究问题定位代码。[命令示例及字段说明](../README.md#按数据集模型和方法查-table-1)

| 研究入口 | 可以查到什么 |
| --- | --- |
| [公开需求建库与迁移](public_library_transfer/README.md) | 独立建库、无库生成、逐题配置与固定首例的配对结果。涵盖 Web-Bench、TodoMVC、WebApp1K-Duo，以及已登记的补充实验。 |
| [Web-Bench 项目研究](webbench/README.md) | 按项目查找组件来源、库接口、可表达行为、配置穷举、官方断言与控制页诊断。 |
| [WebGen-Bench 网站功能](webgen_bench/README.md) | 九个新网站、四种方法。主表按同题完整通过数计分；每个站点都可追溯到生成页面、判决和校准。 |

公开汇总位于 [results/](results)。Web-Bench 的通过数表示候选通过当前任务文件中的全部官方断言。比较时按项目、目标范围、建库者及部署模型读取同一组配对。完整二十项和五个里程碑的结果分别报告。[评分与数据边界](../docs/method.md)

11 月 26 日的表格、文件管理器、问卷、TodoMVC 和 Duo 可从[同题结果与建库记录](results/library-capabilities-20261126.json)进入。逐轮代码与协议按项目保存；[当前任务](../docs/roadmap.md)列出仍缺的来源与实验。

```bash
uv run python -m studies.public_library_transfer --check
```

## 既有研究与协议

| 查阅主题 | 入口 |
| --- | --- |
| 人工行为库的来源与使用 | [TodoMVC](todomvc_dna/README.md)、[Web-Bench 文件管理器](webbench_dna/README.md)、[WebApp1K-Duo](webapp1k_dna/README.md) |
| 早期 AI 建库与无库比较 | [端到端比较协议](../docs/end_to_end_protocol.md)、[各建库者的配对汇总](results/end_to_end.json) |
| 同一目标上的人工库、AI 库与无库对照 | [三组配对结果及来源](results/library-sources-20261121.json) |
| 按原版本复验 | [复现说明](../docs/reproducibility.md)、[历史实验索引](REVIEW.md)、[退役研究说明](../docs/archive/full-history-retirement.md) |

工程回归测试的入口是仓库根目录的 [tests/](../tests/README.md)。旧清单中的 `test/` 通过兼容链接定位到本目录。

## 冻结路径复验

日常查阅与 `python -m studies.public_library_transfer --check` 使用上面的正式目录。34 个新公开阶段在开始运行时已经记录了当时的模块路径。使用 `python -m studies.layout check` 可直接核对 170 个原文件的字节。复验需要按旧清单直接读取文件时，先运行 `python -m studies.layout prepare`。旧模块名也会在首次导入时恢复这些本地兼容文件；工程测试放在 `tests/`。

例如，`uv run python -m studies.layout run public_library_transfer/diagnostics/table_configurations report` 会用该研究注册时的模块名核对原始浏览器收据。完成复验后，`python -m studies.layout tidy` 可将字节一致的兼容目录移入本地备份，保留正式目录作为浏览入口。[Web-Bench 路径映射](webbench/layout.json) · [跨项目路径映射](public_library_transfer/layout.json)
