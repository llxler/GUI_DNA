# 强建库输出的配置空间诊断

两份主实验库通过公开加载后，查看接口发现其配置空间不同。在 Qwen 部署输出全部封存、读取任何新官方判分之前，登记这个独立的后续分析。主实验保留实测配置与固定首例的成绩。

在同批两份库中，只要完整布尔／枚举空间不超过 4 种配置，就将全部配置分别部署到 Table 的 20 个官方当前任务。更大的空间只报告大小。每个任务至少一种配置通过就计入该库的可达任务上界；这条只在离线分析时允许知道测试结果，不能作为方法成绩。原首例和相同页面的实测收据沿用同一内容哈希。报告逐配置通过题号、每题成功配置数，以及目标生成器实际选中的成绩；不付费、不修复，也不将结果传入生成器。

运行 `uv run python -m studies.public_library_transfer.strong_builder.capacity register` 在读取结果前冻结接口、全部枚举和官方合同；然后执行 `uv run python -m studies.public_library_transfer.strong_builder.capacity score`。结果在同目录 capacity.json。
