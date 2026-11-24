# 自建行为库：交付、组装与固定页对照

在同一建库者、同一生成模型、同一项目的二十个公开需求上，比较历史从零生成、历史自建库、当前自建库组装，以及当前库的固定首例。每个建库者只读公开需求、起始工程和公开资源，自行决定可配置的行为。运行器先冻结代码和逐任务配置，再按原始 Web-Bench 当前任务文件评分。收到无效实现计失败，未收到的请求单列。不同阶段单独报告。

表格和问卷的 Qwen3.5-9B 新从零组各只生成一次，供同一协议内的独立库共用。逐题选择和固定首例逐库报告，历史分数见[原始三项目诊断](../diagnostics/self_failures/PROTOCOL.md)。

| 研究问题 | 协议与逐题证据 |
| --- | --- |
| 原生结构化输出能否交付配置和源代码？ | [表格与问卷，两个独立种子](native/PROTOCOL.md) · [配对结果](../../results/self-native-20261124.json) |
| 保持原设计，集中生成共享实现能否解决模块冲突？ | [整段 JavaScript 与适配器](coherent/PROTOCOL.md) · [两项目结果](../../results/self-coherent-20261124.json) |
| 模型自己标注的文件边界能否恢复可运行的模块？ | [确定性模块链接](coherent/linker/PROTOCOL.md) |
| 更强建库者写出的库能否让同一 Qwen 部署成功？ | [GPT-6 Astra 两次独立建库](../strong_builder/PROTOCOL.md) · [逐题配置与固定首例](../strong_builder/result.json) · [原生解码复查](../strong_builder/native/result.json) |
| 单入口场景是否得到同样结果？ | [TodoMVC 的两个独立控制器](todomvc/PROTOCOL.md) · [全部八个功能子集](../../results/self-controller-todomvc-20261124.json) |

表格中从源码提取可验证开关的逐题选择及穷举见[可执行选项](coherent/linker/README.md)。同一做法在单入口 TodoMVC 的两个独立控制器上另行验证。[TodoMVC 源码选项](todomvc/executable_options/README.md) · [只在没有合法配置时交付固定页](../../results/self-fixed-delivery-20261124.json)

代码模型按真实依赖顺序写入模块的两次独立建库，同一批 20 题分别通过 5/20、1/20，共用从零为 3/20。[依赖顺序与传输恢复](dependency_order/README.md) · [逐题回执](../../results/self-dependency-resume-20261124.json)

### 表格早期开发批次

| 阶段 | 建库方法 | 表格项目的结果文件 |
| --- | --- | --- |
| 分文件生成 | 先提交含选项、首例和模块接口的 JSON 清单，再分文件实现 | [self-refinement-20261124.json](../../results/self-refinement-20261124.json) |
| 行式契约 | 用两种固定字符串值表示模型自选开关，从公开需求提取必须提供的文件路径 | [self-line-contract-20261124.json](../../results/self-line-contract-20261124.json) |
| 首次设计归一化 | 复用行式阶段各模型的首份可见设计，将 Unicode Pd 标点映射为 ASCII 连字符后执行同一生成流程 | [self-normalized-table-20261124.json](../../results/self-normalized-table-20261124.json) |

三份协议分别见 [分文件生成](PROTOCOL.md)、[行式契约](line_contract/PROTOCOL.md)、[首份设计归一化](line_contract/normalized/PROTOCOL.md)。归一化阶段的新增账本只包含后续实现与组装费用；原设计成本留在行式契约账本中。

本地原始收据齐备时，从仓库根目录重算并校验已发表的逐目标记录：

```bash
uv run python -m studies.public_library_transfer.self_refinement.report --check
uv run python -m studies.public_library_transfer.self_refinement.report --root artifacts/self-line-contract-20261124 --output studies/results/self-line-contract-20261124.json --check
uv run python -m studies.public_library_transfer.self_refinement.report --root artifacts/self-normalized-table-20261124 --output studies/results/self-normalized-table-20261124.json --check
```

本地重算会检验公开输入和官方测试与历史对照的哈希、冻结页面文件、逐任务报告判定以及请求和账本的对应关系。发布版 JSON 中保留逐项的原始响应、页面与报告哈希，原始请求及完整实现保存在本地独立阶段目录。

[部署位置诊断](line_contract/normalized/BINDING.md)只检验已生成的 GPT-OSS-120B 表格补丁。它把同一回答与两个独立路径线索核对后写回匹配文件，沿用已封存的二十份配置和首例，不产生额外生成费用。该诊断的[逐题证据](../../results/self-binding-table-20261124.json)独立于上表，校验命令如下。

```bash
uv run python -m studies.public_library_transfer.self_refinement.line_contract.normalized.binding check
```

[按依赖顺序建库的代码模型复验](dependency_order/README.md)采用 Qwen3-Coder-30B-A3B-Instruct，独立建两份库，重新生成相同路由和解码设置下的从零对照。两份重复与各自的固定首例分别报告。

### 按公开宿主与组件改进

- [TodoMVC 源码绑定](todomvc/source_binding/README.md)与 [Duo 组件装配](duo_composition/README.md)从六个模型原始输出检验哪些实现能直接使用。两项都核对从零回复，Duo 还独立核验默认导出声明和每个单功能组件。
- [问卷题型](form_registry/README.md)逐模型核对已有类能否导出、挂载及呈现所要求控件，单位是九种公开类型。[表格与 SVG 行为选择](target_selection/README.md)分别测原模型方案、确定性选择和固定页。

- [Duo 逐组件独立建库](duo_components/README.md)分别运行真实模型规划、按名装配、固定组件、从零首稿和公开反馈后的从零。[TodoMVC 独立控制器](todomvc/verified_controller/README.md)先实测哪些配置会改变动作结果，再运行八项逐题规划与固定默认。两套研究均保留两次独立建库。
- [Web-Bench 问卷](form_components/README.md)与 [SVG](svg_renderers/README.md)将逐组件交付、全页公开操作及相同从零源代码接收分别核验。[SVG 前瞻确认](svg_renderers/confirmation/README.md)在新模型回复生成前固定两个接口修复，两库 6/20、6/20，共用从零 5/20。
