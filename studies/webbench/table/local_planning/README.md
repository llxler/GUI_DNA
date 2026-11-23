# 表格库的独立本地规划

Qwen2.5-0.5B-Instruct 从每个目标各自的公开需求前缀、起始工程、配置说明和两个示例生成一份新方案。原 GPT-5 库和四个独立重建的 Codex 库实现同一配置接口；每份方案交给五个后端。宿主机离线推理，不产生逐次 API 账单。模式与协议分开固定，生成回执记录完整输出、模型版本、token ID 和哈希。[输入与指标](PROTOCOL.md) · [解码设置](DECODING.md)

项目原解析器接受直接 JSON 或 Markdown 代码围栏中的 JSON，随后严格检查字段和类型。每个已返回但无效的方案在全部可用库上都记为该目标失败。官方浏览器每次只运行该任务文件。两个后端只有当前任务和完整文件集合哈希都相同时才可复用同一份报告。

本机有封存产物时，用 `uv run python -m studies.compatible_table_local_plans.evaluate check` 复算公开结果。初次运行依次使用 `prepare` 模块冻结输入、用 SVG 研究的 `local_planner.py` 离线生成，再运行 `evaluate score` 和 `evaluate report`。五个后端来自独立的[兼容重建实验](../compatible_rebuild/PROTOCOL.md)。
