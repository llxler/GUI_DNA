# Calculator 的 GPT-5 列

四款目标模型配置同一份由 GPT-5 从公开需求编写的计算器库。每行比较原来的 20 个当前任务。仓库根目录运行 `python -m studies.lookup web-bench/calculator "DeepSeek V4 Flash" GPT-5`，可取得逐题记录、分母和固定全开的成绩。

| 读者问题 | 证据 |
|---|---|
| 源码和配置分别来自谁？ | [建库与部署协议](PROTOCOL.md)。GPT-5 写科学键、外观、记忆和历史四组代码。Gemma、Qwen、GPT-OSS 和 Flash 分别从十个实际观察过的页面中选择配置。 |
| 首次加载为什么失败？ | [隔离测试与同作者修复](mount_recovery/PROTOCOL.md)。保留四份首次回复，原账本和修正阶段分别登记。 |
| 主表一个格子怎样复算？ | 在[逐题记录](mount_recovery/result.json)的 `models` 中取对应模型，`arm=gpt5-library` 是该模型选择的页面，`fixed-gpt5-library` 为固定全开页，`self-choice` 是将该模型在自己库上的旧选择应用到 GPT-5 库上。以每项 `passed` 计数。 |
| 如何检查来源和开销？ | [复核记录](verification.json)列出配置回复哈希、各对照的通过题号及两本账的支出。本机保留原模型回复及浏览器记录时，运行 `uv run --offline python -m studies.webbench.calculator.gpt5_profiles.verify`，可重算以上结果，无需新增 API 调用。 |

此前供应方的 403 和更早的 JSON 编译协议单独保留。[未交付收据](../behavior_modules/gpt5_delivery/result.json) · [早期接口的部署结果](../compiler_fallback/result.json)
