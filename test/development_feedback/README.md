# 公开开发反馈的无库整页代码

[PROTOCOL.md](PROTOCOL.md)明确这批在观察原实验之后提出，不是确认性反馈因子。两应用×GPT-5 medium/Sonnet4.5共4页，20000输出token×最多3次响应，反馈原三个局部开发检查；不给库、参考或隐藏结果。

```bash
uv run python -m test.development_feedback.analyze
```

生成已完成，8调用结算$0.622788，账本stop=0。4页首次/最终共8端点、5份不同源码的原始报告；首次1/4完整过，最终3/4。原36候选与8000-token基线不回写，模型和信息条件不同，不合并归因。

run.py、evaluate.py、analyze.py、__init__.py、PROTOCOL.md及清单依赖已冻结；本README在完成后添加。不得修改已列文件或重开账本。原生首次格式失败计失败，最终仅按公开反馈保留最后可执行页，不按隐藏成绩挑选。
