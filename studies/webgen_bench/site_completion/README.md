# WebGen-Bench 网站操作

表 1 的 C 区比较三个模型在同一批九个网站上的四种方法。发布的数据表提供站点需求和操作期望；Human 使用百度 amis 6.13.0 的通用控件。每个模型为每站写一份从零页面和一份行为配置。三种库共用该模型的同一份配置。浏览器执行每个网站的全部官方操作，只有 YES 计作完整通过。

| 要查看的材料 | 入口 |
| --- | --- |
| 某个模型、某种方法的主表成绩 | 在仓库根目录运行 `python -m studies.lookup webgen-bench "DeepSeek V4 Flash" Human`，查看 `score`、`denominator`、`method_record` 和 `candidates`。 |
| 站点、模型、输出限制和来源 | [生成协议](PROTOCOL.md) · [首份候选](candidates.json) · [原回复与共享配置指纹](page-lineage.json) |
| 主表的 Human 及其余三组 | Human 使用[统一的纵向 SDK 标签](SDK_NAVIGATION.md)，见[逐项判决](vertical-primary.json)。其他三组使用[封存页面的判决](judgments.json)。同文件也保留原横向 Human。缺判的补测见[协议与回执](MISSING_VERDICTS.md)，涉及的格子会返回 `supplemental_records`。 |
| 谁负责通过判定 | [主评运行器](evaluate.py) · [独立判官的选样与校准](SECOND_JUDGE.md) · [修正布局的独立判决](vertical-secondary.json) · [初次缺判的独立补测](RATER_COMPLETION.md) |
| 升级、排名和输入控件能否真的工作 | [升级前后资源](sdk-audit.json) · [排名页的浏览器重放](navigation-audit.json) · [标签可见性诊断](TAB_LAYOUT.md) · [模型状态程序及惰性对照](state_updates/PROGRAM_REPLAY.md) |
| 整数统计、逐站差异、原布局和分项费用 | [可复算汇总](../../results/webgen-site-completion-20261128.json) · [口径与汇总代码](report.py) |

离线复算用 `python -m studies.webgen_bench.site_completion.report`。在保存了原始产物的本机，加 `--ledgers` 复核金额。用 `python -m studies.webgen_bench.site_completion.verify_pages` 可重编三种冻结库，并核对原始模型回复与页面字节。历史样本仍可通过 `webgen-bench/development` 和 `webgen-bench/heldout` 查询，二者使用早期的半分口径。
