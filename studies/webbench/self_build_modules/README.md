# Web-Bench 自建库复验

本研究比较表格编辑器、SVG 图表与问卷的 17 个“项目 × 生成模型”组合，覆盖主表 A 区原先建库失败或实测零通过的全部格子。每格预先登记 A、B 两次建库。模型使用公开需求及原起始工程，对照复用同批目标的真实从零、人工库及 GPT-5 库成绩。

| 阶段 | 交付与准入 |
| --- | --- |
| [分模块准备](PROTOCOL.md) | 模型自定配置并分批提供实现。初版解析器错误地保留了文件名标记，已停止该版本。失败和费用保留在审计记录。 |
| [修正源码接收](source_delivery/PROTOCOL.md) | 正确解析模型提供的文件名与接口说明，完全相同的已付请求复用原回执。默认配置和首例都必须能在公开应用中完成指定操作。 |
| [单入口恢复](entry_recovery/PROTOCOL.md) | 仅当该重复在分模块阶段明确未通过准备时触发。模型独立编写入口文件和实际读取的布尔开关。编译器通过配置绑定这些开关；采用默认方案时执行模型原来的字面量。每次重复按公开准入决定部署路径。 |

单入口的初版准入还会拒绝含有未用选项或选项数超过四个的源码。下一阶段只读取同一重复的第一份已交付程序，最多公开六个实际读取的布尔键，必要时按声明顺序翻转一个键进行公开校准。程序的其余行为和未公开配置值保留。[可用配置提取协议](observed_options/PROTOCOL.md)

仍未准入时回到该重复的首份模块包。仅连接库内已有声明，若仍失败，让同模型按真实导入或浏览器堆栈定点修复，原配置接口不变。[依赖修复](module_links/PROTOCOL.md)

正式评分前封存每份逐题方案与固定首例。原评分器对同一官方文件逐项判定。A 区取预定第一份库，B 重复与各自固定首例可逐项查核。[最终逐目标结果](module_links/result.json) · [选项提取](observed_options/result.json) · [单入口阶段](entry_recovery/result.json) · [分模块阶段结果](source_delivery/result.json) · [25 格统一审计](audit.json) · [套件协议](../../public_library_transfer/self_refinement/suite_recovery/PROTOCOL.md)

有本地原始回执的工作区可用以下命令重算。只读核验无需 API。

```sh
uv run --offline python -m studies.webbench.self_build_modules.source_delivery.score check
uv run --offline python -m studies.webbench.self_build_modules.entry_recovery.score check
uv run --offline python -m studies.webbench.self_build_modules.observed_options.score check
uv run --offline python -m studies.webbench.self_build_modules.module_links.score check
uv run --offline python -m studies.public_library_transfer.self_refinement.suite_recovery.score check
uv run --offline python -m studies.webbench.self_build_modules.audit
```
