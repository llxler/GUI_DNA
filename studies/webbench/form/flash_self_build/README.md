# DeepSeek V4 Flash 的问卷自建库

Web-Bench 问卷共有 20 个当前任务。当前 Table 1 A 区问卷的 Flash Self 主格采用登记顺序中第一份库的 **8/20**。本目录的复验记录包含第二份独立库的 **14/20** 及两份库各自的固定首例。原协议下，Flash 从零、用人工库、用 GPT-5 库、用自己的库依次通过 **4、17、13、0** 项。Flash 的两次原建库响应均用满 16,000 token，可见内容为空。原自建库的二十项均停在准备阶段。以下各阶段只用原公开起始工程与需求重新建库，由 Flash 按原设置逐题配置。三个旧对照的候选及官方收据直接复用。[原同题对照](../../../results/backbone-form-20261124.json)

| 阶段 · 每套库 20 个当前任务 | 逐题配置 A、B | 固定首例 A、B | 两个重复的关系 |
|---|---|---|---|
| [整包交付](result.json) | 12、0 | 12、0 | 两次独立建库，仅建库关闭额外推理 |
| [公开错误诊断](contract_repair/README.md) | 12、14 | 12、14 | 沿用上行两份源码。B 收窄枚举，将已有入口接到 ES 模块 |
| [按文件生成](result.json) | 0、0 | 0、0 | 两份清单均未通过原格式检查 |
| [给清单字段提供类型示例](manifest_schema/result.json) | 9、0 | 9、0 | 使用载有示例的新提示，另做两次独立构建 |
| [公开加载检查，整包修复](confirmation/result.json) | 14、0 | 15、0 | 另建两库。B 的启动文件语法错误，整包修复仍未交付有效 JSON |

最后再从头建两份库。六个首次规划请求在本机进程中断时没有收到响应，提前登记后只补交这六个完全相同的请求。原始观测与补齐结果分列如下。两份库的默认页、首例和公开交互均通过准入。A 将已有的 3,316 字节入口移入原 ES 模块；B 第一次交付同时提供两个入口，经一次格式反馈重新交付。两库均未触发按文件修复。[首次观测](file_repair/result.json) · [完整同题逐项核对](transport_completion/result.json)

| 观测范围 | A 逐题 | A 固定 | B 逐题 | B 固定 |
|---|---:|---:|---:|---:|
| 首次取得规划响应的目标，每库各自的 17 项 | 7/17 | 10/17 | 11/17 | 13/17 |
| 原样补传后，两库共用原来的全部 20 项 | **8/20** | 11/20 | **14/20** | 16/20 |

只有 B 达到事先规定的 10/20。B 比 GPT-5 库多过第 9、11、16 题，少过第 6、10 题。A 和 B 相对各自固定首例分别少过三题和两题，五个首次规划回复均用满 8,192 token 且没有正文。这五题已有供应商响应，所以按原协议保留无效结果。四账本共 173 次请求，已结算 $0.264777，含原六笔未决预留的支出上界为 $0.331361。[按阶段费用和通过项](transport_completion/result.json)

固定首例是在接触官方结果前保存的第一个合格配置；库不可用时按原协议判为建库失败。论文中的“通过”均指通过目标对应的官方当前任务文件。20 个任务来自同一个问卷项目。

## 交付与核验

建库时让 Flash 把输出预算用于可见源码，按公开 starter 的真实入口装载模型交付的模块，验证默认和首例确实在表单中挂载控件。最后一轮同时检查每个 JS 文件以及一次公开表单交互。若错误定位到具体文件，可以把行号和相邻源码交回 Flash，只替换该文件。方案生成使用原 8,192 token 上限、温度、种子与逐题前缀。研究者负责格式和入口接线，未向模型传入参考库、官方断言或逐题成绩。[建库与诊断协议](PROTOCOL.md) · [全新库确认协议](file_repair/PROTOCOL.md) · [传输中断补交](transport_completion/PROTOCOL.md)

最终两库的首轮部署回执在本机 `artifacts/flash-form-file-repair-20261125/`，独立补传在 `artifacts/flash-form-transport-20261125/`。先导与上一轮整包确认分别见 `artifacts/flash-form-self-20261125/`、`artifacts/flash-form-confirmation-20261125/`。下列命令离线核验公开逐题结果；本机有原始收据可换用 `check`。分文件类型示例的本机核验命令为 `uv run python -m studies.webbench.form.flash_self_build.manifest_schema.report check`。

```bash
uv run python -m studies.webbench.form.flash_self_build.contract_repair.report check-public
uv run python -m studies.webbench.form.flash_self_build.confirmation.report check-public
uv run python -m studies.webbench.form.flash_self_build.file_repair.report check-public
uv run python -m studies.webbench.form.flash_self_build.transport_completion.report check-public
```
