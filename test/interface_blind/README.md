# 公开需求驱动的接口建库（P2b＋P3）

这是独立新阶段，不修改原 GUI-DNA 库、第三轮或旧主表。最终结果写入根目录 `实验结果.md`；原始数据只保存在 `artifacts/`。

## 正式比较

- 固定 Web-Bench `dom1`、`form` 两项目，各20项任务，上游提交 `7b31ca2b786eef120dd49ce63dd03d0c0006046d`。
- 建库者 GPT-5（medium reasoning）、Claude Sonnet 4.5 只收到 `tasks.jsonl` 的公开描述与通用文件输入输出约束。模型自己提出组件边界、状态、JSON 方案语言、冻结文件和纯函数编译器；不提供人工槽位、原子、外壳、官方测试或参考源码。
- 最多构建一次、修复两次；只反馈 JSON、编译、两个自带示例的确定性和加载错误。采用首个观察到的公开有效版本，四套库均保留；无人工改库、无隐藏分数挑库。
- 两规划者为 GPT-OSS-120B（low reasoning）和 Mistral Small 3.2（最终整组使用DeepInfra FP8，128000上下文）。每任务一个采样。比较自由代码、预加载同库的自由代码、方案。自由代码基线跨两个建库者复用，共400个不同候选；同项目的任务仍然相关。
- 三种做法独立从累计需求生成整个页面，没有前一任务代码或人工页面外壳。两种同库做法的 user 消息逐字相同，均含完整冻结库、编译器和示例。自由代码可直接导入预置文件，也可覆盖任意文件，只输出新增或修改文件；方案由模型提出的编译器生成页面。
- 每次最多12,000输出tokens、temperature 0.6、seed 20261112（支持时传入），最多两次公开修复。公共页面加载反馈相同；方案另有其编译器的结构诊断，因此仍是含诊断的系统比较。
- 所有建库结束才规划，全部生成结束才隐藏评分；开始评分后生成入口锁定。所有供应商请求有独立费用预留，断连不当作模型失败。
- 官方测试逐字复制；30秒测试/5秒断言超时、Chromium、单worker、无重试。首次失败后可停，只报告准确的候选全过/不过。`EVAL_PROJECT_ROOT` 始终指向实际候选；参考初始化/最终实现和空白负例均已校准。

库见过完整公开需求分布，同库方法因而间接获得未来需求信息；这不是未知需求迁移。`form` 的公开需求本身指定了类和继承关系，因此模型没有从完全无结构的描述中发明所有抽象。公开任务也可能存在预训练记忆。库仅通过加载检查，不能称行为已验证；两项目不支持广泛泛化推断。

## 预跑与传输沿革

所有以下调整均发生在候选隐藏评分之前，预跑记录和费用全部保留。

1. `interface-blind-build` 冻结三套库，GPT-5 的 form 请求断连；`interface-blind-build-2` 用原输入补跑，保留其余三套，四套全部冻结。传输客户端 read timeout 延到900秒；初次是上游 `RemoteProtocolError`，不能声称延长超时必然修复了故障。
2. 最初拟用 Qwen；其唯一支持 JSON 参数的端点持续中断历史修复，故在任何新规划调用前改为 GPT-OSS-120B。
3. `interface-blind-run` 中 Mistral 官方端点的32K上下文拒绝长修复，且限流。关闭该账本新请求后，`interface-blind-run-2` 整组改走同模型 Parasail；完成的 GPT-OSS 候选复用，不按公开成功或隐藏分数选择。
4. 公共预跑暴露同库自由代码被要求反复输出整套冻结库的问题。两轮预跑均关闭新请求，正式 `interface-blind-preloaded` 改为预加载文件，整组重做自由＋库；自由代码与方案协议未变，复用已完整生成的候选，包括公开检查未通过的候选。没有用隐藏成绩决定保留谁。
5. 正式生成使用 SSE，保存全部事件，只接受带终止标志和账单的完整响应。预算与采样参数不因流式传输放宽。原第三轮仍暂停。
6. `interface-blind-preloaded` 完成400个记录，其中61个传输缺失。关闭其新请求后，`interface-blind-final` 原样复制339个完整候选（包括公开失败），用相同提示词、模型、供应商、seed、token上限与修复次数补齐缺失；全部旧尝试保留。隐藏评分前允许用 `--archive-transport` 归档并重试仍缺失的记录，不重做有效模型失败。
7. 该续跑中的Parasail流多次在约6,500输出tokens处以 `finish_reason=error` 结束；当时端点目录报告近期可用率0%，不能当模型失败。关闭其账本新请求后，最终 `interface-blind-final-2` 将**整个200候选Mistral组**改为DeepInfra FP8重做，无论旧输出公开检查通过与否；GPT-OSS完整记录原样复用。供应商与BF16→FP8变化明确单列，原阶段保留，不混合两种Mistral供应商作为最终一组。此时尚无候选隐藏评分。`streaming_provider_v2.py` 另拒绝带DONE的provider-error终止；原传输文件保持冻结。

## 入口

```bash
uv run pytest tests/test_interface_blind.py tests/test_streaming_provider.py tests/test_preloaded_library.py -q
uv run python -m test.interface_blind.evaluate --calibrate
uv run python -m test.interface_blind.run build --workers 2
uv run python -m test.interface_blind_resume_build
# 最终传输补齐阶段；之前的生成账本已关闭，不应重启
uv run python -m test.interface_blind_route --workers 6
uv run python -m test.interface_blind.evaluate --workers 4
uv run python -m test.interface_blind_controls --workers 4
uv run python -m test.interface_blind.analyze
```

控制脚本将建库者的两个文档示例各自不加修改地用于20项任务，作为不读取当前需求的零API对照。四套库及全部构建尝试在 `artifacts/interface-blind-build-2/`（原尝试仍在 `interface-blind-build/`）。需先安装既有 `test/webbench_dna/harness/` 的 npm 依赖；临时测试副本、上游哈希和校准在 `artifacts/interface-blind-harness/`。

## P6 公开行为反馈小试

`test/behavior_feedback.py` 在任何候选隐藏评分前固定公开/隐藏划分：两个项目的 task-4/8/12/16/20，以测试元数据的SHA256排序，前一半公开、其余隐藏。两组互斥，文件和原断言哈希保存在 `test/results/behavior-feedback-split.json`。

从正式阶段的最终候选出发，同库自由代码与方案各最多再修复两次，输出上限相同。仅公开子集的断言错误进入修复消息，不发送源码片段、堆栈或隐藏测试标题。全部80个候选修复完成后，用未公开子集同时评测修复前/后版本。该协议重新划分了官方测试，必须单列；不能把它拼入原全隐藏主表，也不等于完整浏览器工具代理。

```bash
uv run python -m test.behavior_feedback prepare
uv run python -m test.behavior_feedback calibrate
uv run python -m test.behavior_feedback repair --workers 3
uv run python -m test.behavior_feedback grade --workers 4
uv run python -m test.behavior_feedback_analyze
```

2026-11-12 用户预算上限 $20，开始前当天支出为0，余额 $55.402837775。预算计划 `artifacts/review-20261112/budget-plan.json` 保留各阶段上限、已关闭阶段敞口和未分配余额；传输补齐 cap/stop $2/$1.8，P6 为 $3/$2.8。关闭的账本 stop=0，不放宽。`uv run python -m test.review_daily_costs` 只读重算当天费用、未确认预留与仍开放的最大上限。人工时间和本地计算没有折算为API费用。

## 零API的固定方案控制

`uv run python -m test.interface_blind_controls --workers 6` 原样运行建库者预先给出的两个文档例子；都报告，不按分数挑选。`uv run python -m test.interface_blind_final_plan --workers 2` 则是看过主结果后新增的诊断：固定取各组最后执行的task-20方案，页面不变地重放20个前缀。它包含一次模型决策和完整最终需求，不能称零模型或预注册主对照。输出分别为 `test/results/interface-blind-controls.json`、`interface-blind-final-plan.json`，解释见结果第17.5节。

评分单位是对应任务文件：每个 `task-k` 候选只运行 `task-k.spec.js`，不是全部前缀文件。即使输入为累积需求，一个任务全过也不证明全部历史需求正确；前缀完整性仍是后续独立对照。

### 行为反馈的断点恢复

原冻结运行器将里程碑以Python元组传给清单检查，JSON落盘后为列表，第二次调用会误报输入变化。`test.behavior_feedback_resume` 只将协议规范化为已有JSON表示，再执行原始全部哈希/配置/协议校验；源码清单不改写，适配器与原清单的哈希另存 `resume-serialization.json`。已有阶段的修复续跑使用 `uv run python -m test.behavior_feedback_resume repair --workers 3 --archive-transport`；隐藏评分开始后仍禁止续跑。实质性的任务、参数或源文件变化仍必须另立阶段。

正式阶段现已完成并关闭新请求：`interface-blind-final-2` 400/400、`behavior-feedback` 80/80有效，无传输缺失。方案86/160对同库代码67/160，GPT-OSS没有方案优势；独立反馈子集代码12→14/40、方案17→17/40。全部当日账本已结算$1.797186、含预留$3.259005；完整解释、逐组数字与固定方案对照见 `实验结果.md` 第17节。不要在已有隐藏评分的阶段继续生成。
