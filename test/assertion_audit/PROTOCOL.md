# 2026-11-17：官方断言空过路径诊断（R14，无模型调用）

这是看到 BOM/task-20 的缺陷后进行的事后诊断，不修改任何官方成绩。静态登记当前六个 Web-Bench 项目 dom1/form/calculator/table/bom/draw 的全部 `.spec.js` 文件，报告 `toBeDefined` 和无值提前 return 的位置；字符串/正则检索不是完整控制流证明，未命中不意味着不存在其他空过路径。

本次静态检查识别 BOM 的 task-9/13/14/15/16/20 中 `page.frame('content')`、`expect(contentFrame).toBeDefined()` 后 `if (!contentFrame) return` 的模式。浏览器比较在开始前固定为六文件 × 三页面 × 两套断言 = 36 个报告：原最终官方参考、仅删除其 `<iframe name="content" class="content"></iframe>` 的参考副本、空白 HTML。复制页面后按哈希冻结；不继续修补删框副本的其他 JS，也不按结果选择页面。

原断言版本逐字复制。独立诊断版本只将上述六文件所有 `expect(contentFrame).toBeDefined()` 改为 `expect(contentFrame).not.toBeNull()`，其余字节不变。Playwright 的 `page.frame` 缺失值为 null；不将此诊断版本叫官方修订。整个文件的每个测试均执行，workers=1、retries=0、max-failures=0，BOM 全程串行；使用原静态服务和固定 Playwright 1.57.0。原参考在两版本的结果也保留，失败不重跑择优。

分别报告逐测试和整文件判定，明确缺少必需 iframe 的页面是否仍通过。未涉及其他类型缺陷，不能据此否定整个基准；原基准分数不回写。运行源码、协议、输入页、原/诊断断言、依赖和清单在评分前冻结。API 费用 $0；分析与 README 可维护。
