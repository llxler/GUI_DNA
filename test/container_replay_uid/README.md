# 容器UID/GID恢复入口

原容器在写environment.json时报EACCES，未评分任何页面；[协议](PROTOCOL.md)保留失败并固定恢复范围。使用原镜像、相同19页及输入/测试，只增加与输出目录所有者匹配的UID/GID。不是择优重跑。

```bash
uv run python -m test.container_replay_uid.run prepare
uv run python -m test.container_replay_uid.run run
uv run python -m test.container_replay_uid.analyze
```

前两步已经冻结/运行后不得覆盖。原父阶段snapshot及本阶段snapshot均需校验；run.py/__init__/PROTOCOL和清单依赖冻结。独立匿名汇总用`test.replay_nov15`和导出哈希映射，不以原字节哈希校验重写副本。容器测试使用原本地冻结输入，与匿名包的独立解包统计复算是两项不同验证；仍共享宿主内核。
