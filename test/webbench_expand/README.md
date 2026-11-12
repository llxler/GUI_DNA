# Web-Bench 三项目扩展（2026-11-12，新阶段）

回应 TODO P3b 和 P2c 中的严格格式部分。`calculator/table/bom` 在上一阶段仅按公开需求预选，依据与哈希见 `test/results/next-projects-plan.json`。不按隐藏成绩换项目。**全部公开需求仍给建库者，因此不是未见需求组合实验**，也不以新增任务数代替独立项目数。

## 调用前固定的协议

- 上游仍固定 `7b31ca2b786eef120dd49ce63dd03d0c0006046d`。生成模块只读各项目 `tasks.jsonl` 的 id/description。不给测试、参考实现、人工组件/槽位或外壳。
- GPT-5（medium）与 Claude Sonnet 4.5 各为三个项目建库，共六次建库过程；每次首次输出加最多两次格式/确定性/通用加载反馈修复。选首次通过公开检查的包，所有失败保留。建库失败的项目/建库者仍报告，不能用另一建库者替代。
- 模型决定组件、共享状态、接口和方案模式。模式必须使用 `schema.py` 的封闭有限类型方言：显式属性、无未知键；字符串只能是标识符枚举，整数有界，数组有界。通用验证先于模型编译器执行。没有自动语义正确性保证，也不声称形式化沙箱安全。
- GPT-OSS-120B（low，Near AI）和 Mistral Small 3.2 24B（DeepInfra）各生成20项累计需求的独立候选。固定供应商、温度0.6、seed 20261112（接口支持时）、每次输出上限12000、最多两次公开格式/加载修复。保留真实供应商和精度元数据；不静默切换。
- 三种做法：整页自由代码；自由代码＋同库（文件物理预载，可任意覆盖，不必重抄未改库）；受严格格式验证的方案。后两种做法的用户输入逐字相同。每项目40个无库候选只生成一次，供两个建库者比较；六套库均可用时共600个不同候选。
- 所有库冻结后才生成；所有候选生成完成后才统一隐藏评分。传输不完整不算模型输出，整条记录保留在 discarded-transport 后按原参数补齐；已完成的模型失败不重抽。所有未知费用保留预留敞口。达到预算则报告缺失，不放宽账本。
- 测试逐字复制。正校准：官方 init 页与对应 init 测试、最终参考页与 task-20；负校准：空页与 task-1。Chromium，30秒用例/5秒断言，一worker、无重试；task-k候选只评分对应官方文件，首次决定性失败停止。不是完整前缀通过率，不统计不完整执行的用例平均分。
- 调用前校准发现 BOM 上游初始 CSS 是空文件，默认 body margin 使 `.browser` 比1280px视口窄16px，官方初始页自身只过2/3项。保留原失败；另用未改动的最终参考页校准 init 和 task-1，再加 task-20 正例与空页负例。没有修改源码/断言。测试运行目录保留上游 BOM 的 `type:module`；官方 `isExisted` 工具通过 `EVAL_PROJECT_ROOT` 检查候选文件，不检查参考文件。
- **预先固定的配置对照**：每套库的两个文档示例分别在全部20项测试上运行，均报告、不择优；每个规划者 task-20 的最后可执行页固定重用全部20项，选取不依赖任何分数。若无可执行最终页，固定控制记失败。这是固定决策对照，不是库可达上界或均匀随机方案。
- 严格接口是新方法条件，不把这批与上批无严格检查的 dom1/form 直接合成同一成功率，也不把跨项目差当检查器因果效果。无行为反馈、无浏览器工具代理；P2c迁移/可达性、P6b仍独立待做。

## 预算和入口

当天原敞口 $3.259005，新建库 cap $4.5、规划 cap $5，总最坏敞口 $12.759005，低于用户授权的 $20。发调用前检查余额；账本独立，结束后关闭新请求。计划登记在 `artifacts/review-20261112/budget-plan.json`，只读重算 `uv run python -m test.review_daily_costs`。

```bash
uv run pytest tests/test_webbench_expand.py -q
uv run python -m test.webbench_expand.evaluate --calibrate
uv run python -m test.webbench_expand.run build --workers 3
uv run python -m test.webbench_expand.run generate --workers 6
# 有不完整传输时，在隐藏评分前按原阶段补齐：
uv run python -m test.webbench_expand.run generate --archive-transport --workers 3
uv run python -m test.webbench_expand.evaluate --workers 6
```

冻结清单覆盖生成器、严格验证器、传输/账本、公开需求和本文档。评分器单独记录哈希。旧阶段全部保持原字节。
