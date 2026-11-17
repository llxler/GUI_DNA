# GPT-5 正常推理匹配对照（独立小试）

响应 TODO P4b，在三项目主实验生成期间、**任何候选隐藏评分之前**固定：GPT-5、medium reasoning、OpenAI供应商，三个项目各task-4/8/12/16/20（每四项取一个里程碑），两套原样冻结库，同库自由代码与严格方案，共60个候选。不是新增600候选主表的一个模型列，不与旧低推理GPT-5分数直接合并。尚无多种子或多frontier模型结论。

用户输入逐字复用主实验；同库代码可任意覆盖文件，也可运行 `build(files,compile)` JavaScript，不必复制编译器。方案模式与编译器不改。每次12,000输出token上限含推理，最多两次公开格式/加载修复；不提供行为测试或隐藏反馈。温度/seed对GPT-5省略，记录实际推理token与费用。传输中断只补缺失请求，保留先前有效尝试、反馈与预留。

固定对照：在这五项中复用两个建库文档示例的评分；另外无条件取本规划者task-20最后可执行页，原样重用五项。没有可执行页记失败。两者均不依赖隐藏成绩选择。评分采用EVALUATION.md固定的Playwright1.57，BOM串行。其不稳定任务7/14/19均不在本次每四项抽样中；抽样规则并非按这三个任务制定，规则与此前P6里程碑一致。

新账本 `artifacts/webbench-expand-frontier/budget.sqlite3` cap $4.50、stop $4.30。加原阶段保守敞口、已关闭建库以及主实验cap，最坏合计 $15.494820，小于当日$20授权。旧第三轮保持暂停。

```bash
uv run python -m test.webbench_expand.frontier --workers 3
uv run python -m test.webbench_expand.frontier --resume-transport --workers 2
uv run python -m test.webbench_expand.evaluate_pinned --stage artifacts/webbench-expand-frontier --workers 6
```
