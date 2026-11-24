# Web-Bench 表格库的增量编辑

GPT-OSS-120B 先从公开资料自行确定接口，再分五批实现每批四条需求。各批从同一公共起始工程累积代码。两种编辑方式使用相同的六个控制项与固定示例，建库者和部署者均为 GPT-OSS-120B。原从零生成在相同 20 项通过 7 项，原单次 Self 为 0/20。

| 编辑方式 | 建库进度 | 新版逐题 | 新版固定示例 | 新调用 | 已结算 / 总敞口（美元） |
| --- | --- | ---: | ---: | ---: | ---: |
| 文本文件写入与精确替换 | 第一批可加载，第二批的修复补丁找不到目标代码，整库按登记判无效 | 0/20 | 0/20 | 5 | 0.001823 / 0.001823 |
| 原生逐文件工具 | 第一批可加载，第二批更新入口文件时传输中断 | 20 项缺测 | 20 项缺测 | 11 | 0.010832 / 0.026570 |
| 原生工具的同请求恢复 | 复用 10 个原始响应，剩余同一请求两次传输均返回 HTTP 502 | 20 项缺测 | 20 项缺测 | 2 | 0 / 0.031476 |

最后一行是中断运行的续作。该行费用只计新增传输，三行已结算总额为 0.012655 美元，最大账本敞口为 0.059869 美元。有 3 个未结算预留。两种方法均未取得可用于比较最终库行为的浏览器成绩；文本协议的零分来自整库交付失败。此前通过的中间文件只提供工程实现进度。[文本协议与结果](PROTOCOL.md) · [原始结果](../../../results/incremental-self-table-20261124.json) · [逐文件协议](native/PROTOCOL.md) · [原生工具结果](../../../results/native-incremental-self-table-20261124.json) · [传输恢复约定](native/RECOVERY.md) · [恢复记录](../../../results/native-incremental-self-table-resume-20261124.json)

## 离线复核

公开 JSON 可直接在仓库根目录复核，逐项对照原 Self 和 Direct 行、故障或缺测、费用和新增预留。

```bash
python -m studies.public_library_transfer.self_refinement.incremental.audit
python -m studies.public_library_transfer.self_refinement.incremental.audit --native
python -m studies.public_library_transfer.self_refinement.incremental.audit --recovery
```

保留完整本地封存目录时，可另外运行 `incremental.run check`、`incremental.native.run check` 和 `incremental.native.recover check`（均以 `uv run python -m studies.public_library_transfer.self_refinement.` 为前缀），核对原始请求、账本和 SHA-256。
