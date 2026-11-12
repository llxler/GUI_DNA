# 隐藏评分前固定的运行环境与敏感性分析

**制定时间：所有候选隐藏评分之前。** 生成协议与已冻结库/模型输入不变，没有将下列参考测试信息反馈给模型。保存1.63的原始校准，不覆盖历史项目成绩。

1. 正式评分用上游三个项目 `package.json` 钉住的 Playwright **1.57.0**、对应 Chromium build **1200**，原始官方测试与工具字节不变。Node v24.15.0。只改运行目录、服务端口和候选文件根目录；BOM保留 `type:module`。完整依赖锁在独立运行环境，安装入口 `test.webbench_expand.setup_runtime`。
2. 原1.63下，官方最终参考页分别通过 calculator20/20、table20/20、bom18/20。BOM task-14 关闭窗口在并发时失败、串行三次通过；task-19 全屏并发一次及串行三次均失败。
3. 改用上游1.57后，六并发参考页分别20/20、20/20、19/20；BOM task-7 立即读取计时器要求严格为0，观察到0.1而失败。task-14和task-19在1.57串行各三次通过。两套原始报告均保留。另追加BOM全部任务的串行参考页复验，结果记录为诊断，不用于选择模型候选。
4. 正式候选与固定对照都按项目依次评分；calculator/table最多六个候选并发，**BOM每次仅一个候选**。仍是每候选一个Playwright worker、30秒用例/5秒断言、无重试、第一次决定性失败停止。所有候选生成完成后才开始评分。
5. **主表保留全部20个官方任务**，不修改任何断言；另固定敏感性子集：BOM去掉在参考校准中出过问题的task-7、task-14、task-19（17项），其余项目仍20项。排除集合完全由参考页运行确定，在读取任何候选隐藏成绩前固定；不能因模型成绩再变更。主表/子集都报告，不能只挑有利口径。
6. 正式评分和固定对照完成后，如复验发现另有环境问题，另立有记录的复验，不覆盖已保存分数。串行或旧浏览器不能保证绝对无时序噪声。官方task-k文件通过不等于完整历史前缀正确，也不等于视觉质量合格。

```bash
uv run python -m test.webbench_expand.setup_runtime
uv run python -m test.webbench_expand.snapshot
uv run python -m test.webbench_expand.evaluate_pinned --workers 6
uv run python -m test.webbench_expand.controls --workers 6
uv run python -m test.webbench_expand.analyze
```

评分前的 `snapshot` 将两批已完成候选的请求、响应、公开输出和页面逐文件哈希，评分器校验该快照中的记录和源码清单。正式入口以本文为准；早期冻结协议中的1.63评分命令仅保留为历史校准记录。
