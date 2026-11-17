# GPT-5 medium匹配反馈补充组（2026-11-16）

沿用[基础对照](../matched_feedback/README.md)的六库、完整目标、公开五文件、20,000输出token上限与最多两次修复。GPT-5 medium经OpenAI，每条件一次请求链：6方案、6同库代码、3无库代码。内部标签2026111603不作为seed发送，temperature也省略。与GPT-OSS的30候选分别汇总，不能把15个候选视作独立项目。

在观察早期费用和公开生成进度后、任何新隐藏评分前冻结本补充组。独立账本cap 3.5/stop 3.2，生成结束后收紧为stop=0；不放宽旧账本。原始目录`artifacts/matched-feedback-frontier-20261116/`。详细边界见[PROTOCOL.md](PROTOCOL.md)。

`adapt.py/run.py/__init__.py/PROTOCOL.md`及`snapshot.json/shared-dependencies.json`列出的共享源码不可修改。adapter只在独立进程中临时替换明确列出的路径、模型和配置，并在退出上下文时恢复；不修改共享文件。`analyze.py`和README可维护。

```bash
uv run python -m test.matched_feedback_frontier.analyze
uv run python -m test.authorized_costs --date 20261116
uv run python -m test.replay_nov16
```

以上为只读重算，不调用API。首次/最终×三个端点加12固定示例共126项比较。两队列全部生成后才评分；基础对照评分先完成，再运行本组，最后才运行BOM配置搜索。不能重跑生成入口覆盖已冻结记录。

若初始账本的并发最坏预留阻止新调用，按[独立续补协议](../matched_feedback_continue/README.md)保留原目录、只补缺失请求。汇总自动选择有续补清单的最终副本，并合并原/新账本，不重复计费；初始阶段不得被伪装成完整生成。
