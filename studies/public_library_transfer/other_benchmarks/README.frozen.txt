# TodoMVC 与 WebApp1K-Duo 的公开需求建库复测

本研究复用 TodoMVC 历史实验的八个需求和 WebApp1K-Duo 的十份组合测试。每个目标只生成一份直接代码，分别与两次独立建库后的组装结果配对。每套库的固定首例也在各自所有目标上评分。Duo 为满足各测试的导入语句，将同一份固定入口代码放在该目标要求的模块文件名下。TodoMVC 使用固定页面外壳和按需求选择的官方浏览器测试。Duo 需求本身就是公开 Jest 文件，一个组合任务含四个顶层 Jest 用例，每个用例可包含多条断言。两类结果分别呈现。[预登记协议](PROTOCOL.md)

全部生成使用已有 ChatGPT 订阅。调用记录保存输入输出 token、会话号、提示及返回的哈希，订阅费用没有按调用分摊。原 OpenRouter 建库、规划模型与本次模型分别列入历史对照字段。规划器看到当前任务和库接口，直接生成器只看到当前任务及公共运行环境。

首次运行需要已认证 Codex CLI、原始公开输入和本地浏览器、Jest 依赖。登记命令要求新目录，生成命令只接续尚未开始的请求。中断且状态不明的请求需要核对原始日志。重算使用已封存的回复，不调用模型。

```sh
uv run python -m studies.public_library_transfer_extra.generate register
uv run python -m studies.public_library_transfer_extra.generate generate --workers 4
uv run python -m studies.public_library_transfer_extra.evaluate --workers 3
```

[汇总 JSON](../results/public-library-transfer-extra-20261123.json) 保存逐目标结果、双向不一致的目标、分项用量及历史首轮来源。底层原始返回和本机测评报告位于 `artifacts/public-library-transfer-extra-20261123/`。

TodoMVC 的规范摘录、事件接口、页面外壳和评分范围来自历史研究。旧盲建库由人工确定槽位，并由 GPT-5 或 Claude Sonnet 4.5 填充。旧报告有四个规划模型，每模型在八个目标各抽样两次。本轮让建库者定义选项，每个目标抽样一次。两次建库使用相同订阅模型的独立会话。[规范与范围](../todomvc_dna/domain.py) · [原盲建库程序](../blind_library.py) · [原分层数据](../results/blind-library.json)

WebApp1K-Duo 的原始两组各含十个不同目标。旧报告包含首次和修复后的成绩，本轮只对首次作答评分。每个类别的七项或八项单功能测试是根据原研究样本选择的。库的准备材料与十项组合中的单功能需求有直接重叠。不能据此估计对未知单功能或整个一千项组合的迁移率。本轮固定首例由建库者选择，属于同一接口的一个具体配置。[旧首轮与修复结果](../webapp1k_dna/results/summary.json) · [公开基准固定版本 0089530](https://github.com/onekq/WebApp1k/tree/00895306c81d5329904827b65f4a933ce3cb8746)

TodoMVC 另按预先指定的公开功能超集，选择 `todo-08` 的页面，在八个独立特征需求上原样回放。这可区别“逐项规划优于某个有限首例”与“必须逐项规划才能满足这些需求”。首次跑时应在主研究评分前执行 `uv run python -m studies.public_library_transfer_extra.todo_reuse register`。主研究评分完成后用 `uv run python -m studies.public_library_transfer_extra.todo_reuse evaluate` 重算。[补充协议](TODOMVC_REUSE.md) · [复用结果](../results/public-library-transfer-todo-reuse-20261123.json)

已完成的订阅结果中，TodoMVC 两套库的组装、固定首例和共同无库基线分别都通过 8/8。单独回放 `todo-08` 的三个页面也分别通过 8/8。Duo 的两个独立建库结果如下，两个区块共用一次直接生成。

| 历史评测范围 | 无库（共同参照） | 库 A 组装 | 库 A 固定首例 |
|---|---:|---:|---:|
| 博客五项 | 4/5 | 0/5 | 0/5 |
| 任务管理五项 | 5/5 | 5/5 | 1/5 |
| 合计 | 9/10 | 5/10 | 1/10 |

| 历史评测范围 | 同一无库参照 | 库 B 组装 | 库 B 固定首例 |
|---|---:|---:|---:|
| 博客五项 | 4/5 | 4/5 | 0/5 |
| 任务管理五项 | 5/5 | 5/5 | 1/5 |
| 合计 | 9/10 | 9/10 | 1/10 |

库 A 相对无库失去的四个博客任务都复用了同一个 canonical URL 组件。其成功、失败两项断言均提示标签查询匹配多个元素。同一组件错误波及四个组合。库 B 和共同无库代码在这四项都通过。[逐目标结果](../results/public-library-transfer-extra-20261123.json)

历史部署模型复测单独登记，并使用独立的 OpenRouter 账本。[历史模型协议](HISTORICAL_MODELS.md)

历史部署组先校验余额，再登记与运行。在同一 2.00 美元账本内，网络续接只重新提交未取得返回的请求。收到模型内容后立即封存。重算仅依赖封存回复与本地评测环境。[续接协议](TRANSPORT.md)

```sh
uv run python -m studies.public_library_transfer_extra.remote register
uv run python -m studies.public_library_transfer_extra.remote run
uv run python -m studies.public_library_transfer_extra.transport register
uv run python -m studies.public_library_transfer_extra.transport run
uv run python -m studies.public_library_transfer_extra.remote_scores
uv run python -m studies.public_library_transfer_extra.remote_scores --transport
```

### 公开单功能准入与一次修复

在看到组合结果后，另立诊断检查单个组件。四个独立订阅会话将公开单功能与原库自定的组件匹配。任务管理的两套库均通过全部八份单功能文件。博客 A 初次通过四份、一次公开反馈修复后通过六份，博客 B 的两次均通过六份，共七份。两套库均仍未通过 `postPerformanceReport`。共六个订阅会话，未新增 API 费用。[方法与信息边界](DUO_ADMISSION.md)

| 10 个原组合目标 | 原方案与原库 | 原方案与修复后候选 | 严格准入并通过 |
|---|---:|---:|---:|
| 库 A | 5/10 | 9/10 | 5/10 |
| 库 B | 9/10 | 9/10 | 5/10 |

两套库在严格准入下各部署了五个任务管理目标，五项全部通过。未准入的博客候选只作离线诊断。共同无库仍为 9/10，固定首例各自仍为 1/10。只将被测组件 JSX 名统一并归一换行，组合中的 40/40 个 Jest 用例与建库器可见的单功能用例完整重合，共复用 30 个不同用例。这组修复结果衡量已知单功能在同页的兼容性。[逐项结果及来源核对](../results/public-library-transfer-duo-public-admission-20261123.json)

```sh
uv run python -m studies.public_library_transfer_extra.duo_admission register
uv run python -m studies.public_library_transfer_extra.duo_admission run
uv run python -m studies.public_library_transfer_extra.duo_admission_result
```

剩余报告组件的公开用例用带 `?postId=1` 的 URL 配置 mock，却按不带查询串的 URL 计数。在冻结的 fetch-mock 9.11.0 上，向配置的 URL 发送一次普通请求会收到 `performance: high`，总调用数和带查询串计数均为 1，去掉查询串的计数为 0。该最小检查解释了这一种实现路径下的失败。官方文件与成绩均依原样保留。以下命令在仓库根目录复验。

```sh
node - <<'JS'
const mock = require('./artifacts/benchmark-probe/WebApp1k/staging/node_modules/fetch-mock').sandbox();
const base = '/api/generatePostPerformanceReport';
const url = base + '?postId=1';
mock.get(url, { status: 200, body: { performance: 'high' } });
mock(url).then(async response => console.log(await response.json(),
  mock.calls().length, mock.calls(url).length, mock.calls(base).length));
JS
```

### 原建库与部署模型

Duo 原研究的两个组件代码来源为 DeepSeek V4 Pro 0813 与 Qwen3 Coder。新协议用这两种模型分别从七份博客单功能测试和八份任务管理单功能测试重建菜单。每个规划模型在两个建库来源分别选择目标组件，无库代码与同一规划模型的历史部署复测共用。每个来源的固定首例对不同部署模型共用，同模型的直接代码对不同来源共用。源阶段与上一组共用 2.00 美元最高敞口。[原模型协议](DUO_ORIGINAL_SOURCES.md)

```sh
uv run python -m studies.public_library_transfer_extra.duo_original_sources register
uv run python -m studies.public_library_transfer_extra.duo_original_sources run
uv run python -m studies.public_library_transfer_extra.duo_original_results
```

### 历史部署模型在两套订阅库上的成绩

TodoMVC 每个部署模型在八个目标上各采样两次，每列共 16 个目标－采样对。两次建库各自固定的首例均通过全部八个不同目标。

| TodoMVC 部署模型 | 无库 | 库 A 组装 | 库 B 组装 |
|---|---:|---:|---:|
| Mistral Small 3.2 24B | 7/16 | 16/16 | 16/16 |
| GPT-OSS 120B | 16/16 | 16/16 | 16/16 |
| Qwen3 Coder 30B A3B | 15/16 | 16/16 | 16/16 |
| DeepSeek V4 Pro 0813 | 8/16 | 11/16 | 10/16 |

Duo 每个部署模型在十个组合目标各采样一次。两个建库来源的固定首例均通过 1/10。DeepSeek 的十份直接回答均到达 4,000 token 上限，正文为空。库 A 与 B 的规划各有四份可执行，规划输出上限为 550 token。本表按已经返回的全部预登记目标计分。

| Duo 部署模型 | 是否为原研究部署模型 | 无库 | 库 A 组装 | 库 B 组装 |
|---|---|---:|---:|---:|
| DeepSeek V4 Pro 0813 | 是 | 0/10 | 1/10 | 4/10 |
| Qwen3 Coder | 是 | 7/10 | 5/10 | 9/10 |
| Mistral Small 3.2 24B | 新增迁移 | 1/10 | 5/10 | 9/10 |
| GPT-OSS 120B | 新增迁移 | 5/10 | 5/10 | 9/10 |

312/312 个位置有模型返回。328 次实际调用共结算 0.455346 美元，含 16 笔未知预留的敞口为 0.565072 美元。各模型、任务、采样的原共享基线与两个源列分别配对。[初次网络提交](../results/public-library-transfer-historical-models-initial-20261123.json) · [网络续接后完整成绩与截断审计](../results/public-library-transfer-historical-models-20261123.json)

原身份面板中，Qwen 的两个类别均给出有效库，固定首例在十个组合上通过一项。同名 Qwen 部署有六个目标未收到模型响应，另四个目标均收到可执行方案，实测通过 0/4。在对应的同四个目标上，共用无库代码通过 4/4。Qwen 库交给 DeepSeek 规划也有六个目标未收到响应，另外四个回复都未生成可用方案。DeepSeek 自建博客库到达 8,192 token 上限且无正文，任务管理库经登记允许的四次网络提交仍无返回，两种部署均没有该来源的候选可测。以上缺项保留在各自登记的十目标清单中。[逐原建库者与部署者成绩](../results/public-library-transfer-duo-original-sources-20261123.json)

该原身份面板另有 69 次调用，结算 0.048813 美元，含 58 笔未知预留的敞口为 0.899128 美元。两个付费阶段共用账本最终结算 0.504159 美元，397 次调用中含 74 笔未知预留，总敞口 1.464200 美元，授权上限为 2.00 美元。
