# 冻结接口下的实现修复诊断

本目录保留11月13日时间点的`实验结果.md`第21节：当时原计划六库的付费生成**未完成**，三套库在两条件下有完整响应，另立零API可用子集评分。11月14日已在[独立续作目录](../library_repair_resume/README.md)补齐缺失、完成六库重放，结果另列第22节；不回填旧阶段。不能把子集当作六库结果，也不能把旧输出重放当作重新生成或未见需求迁移。

- 初始设计：[PROTOCOL.md](PROTOCOL.md)。六库、每库两条件、单次有效响应；接口保持不变。
- 输出包装的事后检查：[FORMAT_DIAGNOSTIC.md](FORMAT_DIAGNOSTIC.md)。只提取唯一JSON块，单独报告。
- 最终实际评分范围：[AVAILABLE_PROTOCOL.md](AVAILABLE_PROTOCOL.md)。三库、两项目，主规划者与GPT-5分开汇总。
- 传输与费用：[TRANSPORT.md](TRANSPORT.md)。原始流、地区拒绝、未知预留及平台费用回执保留。

付费阶段位于`artifacts/library-repair-20261113/`，账本已经stop=0。原`run.py`、`evaluate.py`是冻结的六库协议源码；没有完整生成屏障，不能运行原全组评分，也不要重新执行生成命令。已完成配对的评分位于`artifacts/library-repair-available-20261113/`，它没有新API调用。

```bash
# 已有评分的只读审计/汇总；不创建或收紧账本。
uv run python -m test.library_repair.available analyze
uv run python -m test.replay_library_repair
uv run python -m test.library_repair.diagnostics
uv run python -m test.library_repair.mechanism analyze
uv run python -m test.library_repair.finite_space analyze
uv run python -m test.library_repair.report

# 原评分缺失时才补本地浏览器；不覆盖已有结果、不调用模型。
uv run python -m test.library_repair.available evaluate

# 单独的新匿名快照，不覆盖11月12日文件。
uv run python -m test.export_replay_bundle --expanded --library-repair --out artifacts/anonymous-replay-20261113-final.zip --report test/results/replay-bundle-20261113-final.json
uv run python -m test.validate_replay_bundle --expanded --library-repair --archive artifacts/anonymous-replay-20261113-final.zip --report test/results/replay-validation-20261113-final.json

# 在新解包目录重装npm依赖，实际重跑四张机制页面及官方参考页。
# 重复运行时另选不存在的browser-artifacts目录，保留已有观测。
uv run python -m test.validate_replay_bundle --expanded --library-repair --browser-smoke --browser-artifacts artifacts/replay-browser-20261113-final --archive artifacts/anonymous-replay-20261113-final.zip --report test/results/replay-validation-20261113-final.json
```

原工作区审计会校验冻结源码与评分前快照，**不要修改**`core.py/run.py/evaluator.py/evaluate.py/PROTOCOL.md`及`available.py/AVAILABLE_PROTOCOL.md/format_replay.py/FORMAT_DIAGNOSTIC.md/analyze.py`及`mechanism.py/finite_space.py`和快照列出的复用文件。`report.py`、`diagnostics.py`与独立重算入口可维护；它们不参与生成或评分。

匿名副本不运行原始哈希审计，改验`REPLAY-MANIFEST.json`并调用`test.replay_library_repair`。新包保留未完成请求，但不用于续发API。后续补缺失库必须另立阶段/账本并先明确预算，复制完整响应、只补缺失，不悄悄重抽完整格式失败；已观察子集分数这一时间顺序也须披露。

`--browser-smoke`从解包副本加载代码、测试和页面，通过离线`npm ci`重装锁定依赖，复用本机缓存的Chromium及系统库；仅覆盖table/task-20的五张页面，不是跨机器复现或全部历史浏览器重跑。原始新报告、依赖日志与环境哈希保存在指定目录，不替代实验原分数。

四页事件传播干预在观察子集成绩后单独冻结，不混进模型成绩：原页失败、只添加stopPropagation后全过、修复页全过、撤掉该行后失败。其4份原始报告也由独立入口复算。

随后固定原最终方案的四项样式字段，穷举全部7个布尔交互选项：原库0/128通过，单行修复32/128通过。两份精确相同页面复用机制报告，其余254份为新评分；不是整个schema的不可达证明，也不是128个独立任务。
