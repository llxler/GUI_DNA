# 当前任务报告的本地复验包

从仓库根目录运行 `uv run python -m studies.current_bundle.export artifacts/<新文件名>.zip`。包内含报告视图的直接数据源、冻结协议、逐目标和诊断用浏览器报告的断言状态、两项交互的原始测量，以及两项目真实浏览器抽样所需的页面。原始报告和精简版分别登记哈希。

解包后，在目录内运行 `python verify.py`，核对清单、从正式与兼容包名重算视图、复算配对与账单，并核对浏览器判定。真实浏览器复验需要 Node、与 Playwright 1.57 对应的 Chromium 及系统库。在 smoke 子目录运行 `npm ci`（已缓存时可加 `--offline`），再回到顶层运行 `python verify.py --browser`。可通过 PLAYWRIGHT_BROWSERS_PATH 指定 Chromium 缓存。在已有成绩后确定固定抽查位置。canvas 取首批无库组的第一个重复、首个里程碑；flex 取第一个重复、最后里程碑的无库页和 GUI-DNA 页。每项目另跑官方参考页和空白页，共七次浏览器评分。

## 来源与交付范围

官方 canvas task-4 和 flex task-20 测试、参考页、PNG 资源及测试工具来自 [ByteDance Web-Bench](https://github.com/bytedance/web-bench/tree/7b31ca2b786eef120dd49ce63dd03d0c0006046d)，对应许可证随包保存为 `smoke/Web-Bench-LICENSE.md`。候选页面为本研究 GPT-5 的实际输出，空白页与运行配置由研究代码生成，Playwright 安装依赖按随附锁文件获取。许可审核、跨机器验证和公开下载由作者另行确认。本包覆盖报告复算及本地浏览器抽样；完整模型回复、原始账本、全部候选页面和论文源文件保存在原工作目录中。
