# 本地 Qwen 的 Web-Bench 计算器实验

从公开需求抽取按键，将显示状态、界面模块和逐题排序选择分开。每个条件保留两个库及所有当前目标。生成和官方评分分进程运行，先冻结源码、输入和种子，再保存每个页面的文件散列。使用 Qwen2.5-0.5B-Instruct，全部推理在本机完成。

| 条件 | 研究者提供什么 | 模型需要完成什么 |
|---|---|---|
| [开放代码](PROTOCOL.md) | 通用按钮绑定和共享显示对象 | 从文字列按键、写运算及界面代码，提出并实现一个二值选项 |
| [受限计算器语法](typed_keys/PROTOCOL.md) | 公开说明中的按键与顺序解析、标准 Math 同名链接与算术语法 | 给未解析的按键选择运算，编写附加面板并选择顺序 |
| [全部运算由模型选择](typed_keys/MODEL.md) | 同一目录、同一候选语法及两份既有界面面板 | 在完整运算空间内重新选出每个按键的程序，再使用与上一条件相同的逐题设置。另用[联合分词](typed_keys/TOKEN_BOUNDARY.md)复核同一提示和随机种子 |

[固定组件诊断](PROBE.md) 在开放代码阶段省略二值设置，检查组件本身。受限语法另有仅使用确定性链接的固定页和从[公开顺序文字](typed_keys/ORDER.md)得到的选择。没有端点、缺少组件、固定配置和逐题选择分别记录。早期归档的 JSON 封装基线未参与这三组比较。本轮从零页直接输出原始 HTML，首组要求完整结束标记；其他两组也将带有 html 与 body 起始标记的截断响应交给浏览器。

每列分母均为相同的 20 个官方当前任务。早期开放代码组 Direct 获得 10 份完整 HTML；把截断文档也交给浏览器，后续三组共用 16 份可装入的页面，均通过 0 项。

| 实际评分 | 自建库 A | 自建库 B | 固定逆序 A/B |
|---|---:|---:|---:|
| [开放代码与二值说明](result.json) | 0/20 | 0/20 | 两库未交付设置 |
| [标准运算直接链接，模型补余项](typed_keys/result.json) | 5/20 | 7/20 | 5/20、7/20 |
| [模型选择所有运算，分开分词](typed_keys/model-result.json) | 1/20 | 2/20 | 1/20、2/20 |
| [模型选择所有运算，联合分词](typed_keys/token-boundary-result.json) | 1/20 | 1/20 | 1/20、1/20 |

标准运算直接链接时，固定初始顺序且省去模型生成内容的页面通过 6/20。两个模型方案都在全部 20 题选择逆序。让模型选全部算子并采用联合分词后，两份库都只通过第 6 题的按键换位。既有校准的参考实现为 20/20，空白为 0/20。[校准报告](../../../results/public-library-transfer-calibration-20261123.json)

仓库内已发布报告可用以下命令复核。复原浏览器报告需要本地保存的原始产物，分别用对应模块的 `rebuild` 指令核对。完整新采样需要本机缓存的固定模型和协议指定的软硬件。

```bash
python -m studies.public_library_transfer.self_refinement.local_domain.report check
python -m studies.public_library_transfer.self_refinement.local_domain.typed_keys.report check
python -m studies.public_library_transfer.self_refinement.local_domain.typed_keys.model_report check
python -m studies.public_library_transfer.self_refinement.local_domain.typed_keys.boundary_report check
```
