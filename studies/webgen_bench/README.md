# WebGen-Bench 网站功能实验

基准发布的测试集有 101 个网站、647 项功能检查。我们按预先登记的哈希规则从每个一级类别各取两站，对六站的全部 43 项操作评分。固定数据版本和六个站点 ID 见[抽样登记](protocol.json)。公开说明与评测项目分别交给生成器和判分器。[论文](https://proceedings.neurips.cc/paper_files/paper/2025/hash/6841eed8bb6a2ec49e49235c8115efee-Abstract-Datasets_and_Benchmarks_Track.html) · [发布数据](https://huggingface.co/datasets/luzimu/WebGen-Bench/tree/c061fe8326459846ac020ceb54d750c859cb059f) · [作者评测程序](https://github.com/mnluzimu/WebGen-Bench/tree/c89e0743438e458d617cebaf7a682e0e66e41049)

## 工作流与判分

三款目标模型各为六个网站生成 Direct 完整 HTML 和供库工作流共用的配置。人工库采用百度开源的 amis 6.13.0 SDK。自建库由目标模型实现，研究者提供组件接口与 DOM 绑定。通过独立阅读室样例的启动、换页、显示记录、查看详情和提交表单后才部署。每种判分方法按同一组操作计算完整 1 分、部分 0.5 分、失败 0 分。无效交付按网站启动失败逐项记零。建库失败和未取得判分的情况分别保留。作者的 32B 评判器未取得路由；本地研究使用独立校准后的 30B 视觉模型。原工作的官方分数仍缺测。每站经哈希预选一项操作，用独立 72B 评判器重复；41 个可运行页面中取得 32 个配对，只有 15 个给出同一等级。[原始生成与评测](functional_pilot/PROTOCOL.md) · [人工 SDK 发布版本](https://github.com/baidu/amis/releases/tag/6.13.0) · [空白页与第二评判器](functional_pilot/judge_controls/PROTOCOL.md)

短配置和模型实现的变化按先后保留。逐站 HTML、原始模型回执、评判截图与账本存于本地 artifacts；版本库内的 candidates.json 和 judgments.json 给出页面哈希与逐项结果。[短配置](functional_pilot/native_plans/PROTOCOL.md) · [挂载接口](functional_pilot/mounted_components/PROTOCOL.md) · [分组件函数](functional_pilot/component_functions/PROTOCOL.md) · [最终输出绑定](functional_pilot/function_binding/PROTOCOL.md)

## 离线复核

从仓库中的逐项记录核对 C 区、不同生成阶段及费用合计，运行 `uv run python -m studies.webgen_bench.report --portable`。具备本地原始账本时，去除 `--portable` 可独立复算费用明细。恢复对照的上游材料使用 `uv run python -m studies.webgen_bench.fetch_sources`，它验证数据摘要、上游 Git 版本及 SDK 包的 SHA-512。运行判分需独立预算和模型服务。[结果汇总](../results/webgen-functional-20261126.json)
