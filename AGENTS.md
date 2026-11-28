# GUI-DNA：代理操作指南

先读 [README](README.md)、[当前任务](todo.md)；方法见 [docs/method.md](docs/method.md)，历史结果见 [docs/results.md](docs/results.md)。详细旧指令仅供查证：[归档](docs/archive/agent-instructions-20261117.md)。不要默认加载整份历史。

## 当前工作范围

- 论文主线：**人工库＋GUI-DNA 组装**；**AI 从公开需求建库＋GUI-DNA** 为第二种来源。两种流程都测试，并保留同协议的无库生成对照。注明参考组件、公开起始工程和绑定胶水的来源；旧 dom1 无库组逐步编辑前页。
- `studies/results/end_to_end.json` 保留原有两流程报告视图；11 月 21 日三组配对另见 `studies/results/library-sources-20261121.json`。`free_lib` 是保留代码与数据的历史消融，不进入当前论文正文/附录或展示。原分数、方法标识和历史记录不改名冒充基线。
- 只用公开基准支持当前论文；旧合成任务仅归档。不同协议、建库模型分别呈现；每列与真实共用基线目标和分母一致。只报告当前任务文件，逐生成模型另分层；敏感性和费用也不混合建库者，建库费用与信息范围必须披露。
- 原第三轮仍暂停：190/640，`artifacts/budget.sqlite3` 的 `halted=1` 不动。新任务不自动授权续跑第三轮。
- 付费调用须有适用于本轮的预算和时间授权，先查余额；已有授权范围内不重复询问。按账本敞口控制新增调用；离线重算不产生 API 费用。

## 目录与冻结边界

- `studies/`：公开基准研究、分析、汇总；`tests/`：工程回归测试；`experiments/`：早期冻结原型与历史运行器。各目录 README 解释边界。
- `test -> studies` 是旧清单/导入的兼容链接，不能删除；新代码和文档使用 `studies`。旧中文文件名及 `experiments/TODO.md` 同样是文档兼容链接。
- 新公开的 34 个阶段统一位于 `studies/webbench/`、`studies/public_library_transfer/`。旧路径的原始磁盘清单用 `python -m studies.layout prepare` 恢复并核对；新引用使用两份 layout.json 中的正式目录。
- 保留 `/home/lxler/work/gui_test -> /home/lxler/work/GUI_DNA`：旧记录使用绝对路径。
- **不得修改** `src/gui_dna/**`、`experiments/scale_study/*.py`、`configs/scale-study.json`、历史连接器 `experiments/{plan_linker,replay_linked_plans}.py`，以及各研究 README、manifest/snapshot 指定的冻结源码、协议、输入、评分与记录。旧 `test/...` 路径的哈希仍按原字节验证。
- 用户已于 2026-11-17 移除完整历史测试：不新建或恢复累计前缀评分。旧版本源码与快照复验边界见 [退役说明](docs/archive/full-history-retirement.md)；原始成绩与账本不改，不能把当前任务通过写成整个应用正确。
- 已冻结研究要改方法时另建目录、协议、输出目录与账本；不得覆盖原候选、挑选较好重跑结果或将隐藏反馈传入生成器。
- 账本只读用 `studies/ledger_read.py`；不要为统计实例化 `Ledger`，不要放宽/重开旧账本。传输中断保留未知预留，不推定零费用。
- `artifacts/web-bench/` 为只读上游快照。官方断言不改；诊断另立阶段，历史分数不回填。

## 常用命令

```bash
uv sync --extra dev
uv run playwright install chromium
uv run pytest -q
uv run python -m studies.end_to_end --check      # 当前比较视图，只读
uv run python -m studies.paper_end_to_end       # 本地论文表格/范围核对
uv run python -m experiments.audit_scale        # 暂停的第三轮，只读
uv run python scripts/check_openrouter_credits.py --required-usd 1
```

更多复验入口见 [docs/reproducibility.md](docs/reproducibility.md)。不要用旧论文生成器将已移出的研究/消融重新写入当前稿件。

## 文档与交付

- 文档用中文，代码注释/标识符和 `DNA_latex/` 论文用英文。结果唯一追加到 `docs/results.md`；已完成待办移出根目录的 `todo.md`，历史保存在结果与 Git。
- 修改实验结论时同步 README、方法说明、论文及本地 `presentation/`。按 [presentation/TODO.md](presentation/TODO.md) 更新 `DNA.md`、12 页 `slides.pptx` 和对应 `script.md`；不增加篇幅，备注与讲稿一致，追加一行更新记录。
- `DNA_latex/`、`presentation/`、原始响应/账本/截图不入 Git，不强制添加。当前官方 ICML 2027 样式不改，正文不超过 8 页；引用与数字须有可核查来源。
- 新论文表格只由 `studies.paper_end_to_end --write` 生成；本地编译入口 `artifacts/paper-build/build.sh`。生成后仍须检查 PDF、来源、负结果和待作者审核项。
- 不宣称未执行的实验、完整匿名发布或跨机器复现已完成；新包使用独立文件名，不覆盖旧包，不自行上传。
