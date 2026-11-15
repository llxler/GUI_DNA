# 独立用户空间的固定页面复验

选择规则和限制见[PROTOCOL.md](PROTOCOL.md)。19张旧页面：四个table机制页及参考、三个Web-Bench项目的两建库者/GPT-OSS/两做法最终页、另两个官方参考。不是方法准确率或跨机器复现。

```bash
docker pull mcr.microsoft.com/playwright:v1.57.0-noble
uv run python -m test.container_replay.run prepare
uv run python -m test.container_replay.run build
# 等历史复验全部完成，避免两个BOM浏览器队列同时运行
uv run python -m test.container_replay.run run
uv run python -m test.container_replay.run analyze
```

首次prepare后，run.py、runner.cjs、协议、README和选定源码/测试/构建上下文全部冻结，不得原地修改。容器镜像、源码、测试、Chromium文件哈希和原始JSON均保存。prepare/build/run不覆盖已有产物。原始观察有差异也不择优重跑。
