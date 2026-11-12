"""Write section 19 from audited observations, keeping later results sections."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMES = {'openai/gpt-5': 'GPT-5', 'anthropic/claude-sonnet-4.5': 'Sonnet 4.5',
         'openai/gpt-oss-120b': 'GPT-OSS', 'mistralai/mistral-small-3.2-24b-instruct': 'Mistral'}


def main():
    s = json.loads((ROOT / 'test/results/heldout-composition.json').read_text())
    d = json.loads((ROOT / 'test/results/heldout-composition-diagnostics.json').read_text())
    daily = json.loads((ROOT / 'test/results/review-20261112-costs.json').read_text())
    assert s['audit']['all_saved_hashes_verified'] and not s['audit']['regeneration_differences']
    main, strong = s['cohorts']['main'], s['cohorts']['strong']
    totals = main['method_totals']
    lines = [
        '## 19. 模型自建库与未见行为组合（独立合成诊断，2026-11-12）', '',
        f'**结论先行**：建库模型只看开发需求，四套库首次提交均通过5/5开发检查。其余组合上，方案{totals["plan"]["final"]}/{totals["plan"]["n"]}、同库代码{totals["free_lib"]["final"]}/{totals["free_lib"]["n"]}，无库代码{totals["free"]["final"]}/{totals["free"]["n"]}。独立GPT-5 medium小试两种同库做法均12/12。模型接口能够承载本次未见组合，但**不调用模型的开发示例差分合成也为44/44**；这批结果支持库复用，没有显示LLM规划的额外正确性收益。', '',
        '**不是官方Web-Bench成绩**：calculator/table仅提供应用灵感；本节需求、四个二元行为维度、DOM观测契约和测试都是本研究新写。模型选择组件、状态、模式属性与编译器。两个人工合成应用不能算成新增两个独立Web-Bench项目，也不是自动发现语义维度或一般自然语言泛化。', '',
        '### 19.1 开发与未见组合隔离', '',
        '- 每应用16种配置：基础配置0000及四个单项变化是5个开发需求；至少两项同时变化的11种配置留作测试。开发集覆盖全部原语及单项语义，没有把新功能混入组合迁移。需求以自然语言给出，结构化策略字段不进入模型消息。',
        '- calculator变化为运算后清空/保留输入、内存回忆替换/累加、清空时保留/重置内存、历史项替换/累加；table变化为升/降排序、选中对象随身份/位置移动、删除后清空/相邻重选、剪贴板快照/实时引用。人预先选择这些维度，模型未收到人工方案属性或外壳。',
        '- GPT-5 medium和Sonnet 4.5只看5条开发需求及每条两段公开交互观察，不看测试需求列表、隐藏动作、参考页或官方源码。首次通过全部开发行为检查的包冻结；最多两次修复、保留失败，未根据测试分数重建库。本次四库均首次通过。',
        '- 主组：GPT-OSS-120B low/Near AI、Mistral Small 3.2/DeepInfra，每应用11个测试组合；无库44个、同库代码88个、方案88个，共220个不同候选。无库记录跨建库者复用，只计一次。另固定1100、1110、1111三个组合给GPT-5 medium/OpenAI，两应用×两库×两做法，共24个候选，单独报告。',
        '- 三种做法均见开发公开信息及当前需求；两种同库做法还见完全相同的库用户消息。同库代码可直接调用完整冻结编译器并任意修改产物。建库输出上限20,000，候选6,000（含推理）；最多两次格式/加载修复，规划者不接收当前任务行为反馈。',
        '- 两批244个候选全部生成并保存文件哈希后才评分。中断只补缺失请求，保留原有效响应及修复反馈；完整模型失败不重新抽样。全部阶段独立记账，未恢复原第三轮。协议与输入边界见 `test/heldout_composition/PROTOCOL.md`。', '',
        '### 19.2 评分可辨识性与预定控制', '',
        '独立Python状态机和手写JS参考实现先在全部32种配置上校准通过，错误策略负控制失败。每应用各配置使用完全相同的隐藏动作（calculator四条、table五条），页面地址不含配置ID；每步直接观察DOM。每应用16种期望轨迹各不相同，固定页不能靠测试动作序列推断目标配置。Python Playwright1.63.0、Chromium153.0.8010.12，最多四候选并发；全部候选沿用参考校准环境，不择优重跑。', '',
        '调用前保留了三次参考校准草稿：脚本启动早于DOM、表格行中心点击落在单元格间隙、初始轨迹仅区分14/16种表格策略。最终在调用前统一修复启动/点击并补第五条区分轨迹，通过32/32后冻结；没有根据候选分数改断言。', '',
        '固定控制在调用前规定：五个开发示例各不变地用于全部11项；每个规划者四项全变化的最终方案不变地用于其他项；从基础与单项开发方案提取JSON差分，按需求中逐字出现的公开语义句选取并合并。差分修改同一位置会判冲突，不读取隐藏策略、不借评分选答案。该规则利用模板文本，不是通用语言求解器或库可达上界。', '',
        '### 19.3 逐库、逐规划者结果', '',
        '| 应用 | 建库者 | 规划者 | 无库代码 | 同库代码 | 方案 | 差分规则 | 固定最终页 |',
        '|---|---|---|---:|---:|---:|---:|---:|']
    for g in main['groups']:
        lines.append(f"| {g['project']} | {NAMES[g['builder']]} | {NAMES[g['model']]} | {g['free']}/{g['n']} | {g['free_lib']}/{g['n']} | {g['plan']}/{g['n']} | {g['delta']}/{g['n']} | {g['fixed_final']}/{g['n']} |")
    controls = s['fixed_control_rows']
    lines += ['', '无库列和差分规则列跨规划者/建库者的复用如上，不将复用评分计为独立样本。全部88对方案与同库代码为0胜/0负/88平；两应用和相关配置不足以支持跨项目显著性推断。', '',
              '| 固定控制 | 不同库×任务评分数 | 通过 |', '|---|---:|---:|']
    for name in [f'dev-{i}' for i in range(5)] + ['delta']:
        rows = [r for r in controls if r['control'] == name]
        lines.append(f'| {name} | {len(rows)} | {sum(r["passed"] for r in rows)} |')
    lines += ['', '五个开发示例各为0/44，未挑最好者。差分规则44/44在主组两规划者间复用，所以其不同评分数是44而不是88；每个库均找到全部11种组合的可达见证。主组固定最终页8/88、GPT-5固定最终页4/12，均仅通过与该配置匹配的任务。逐任务选择确有必要，但这一模板任务不需要LLM来做选择。', '',
              '| GPT-5 medium小试 | 建库者 | 同库代码 | 方案 | 固定最终页 |', '|---|---|---:|---:|---:|']
    for g in strong['groups']:
        lines.append(f"| {g['project']} | {NAMES[g['builder']]} | {g['free_lib']}/{g['n']} | {g['plan']}/{g['n']} | {g['fixed_final']}/{g['n']} |")
    lines += ['', '小试只有三个预选组合、一个种子，不与主组混合，也不作为推理强度因果对照。所有做法的首个可执行版本与最终版本隐藏成绩相同；首个可执行版本不一定是首次模型响应。', '',
              '### 19.4 失败、修复与库规模', '',
              f'无库代码的12个最终失败均在table。按每候选首个失败观察分类：实时剪贴板{d["first_failure_counts"]["clipboard_live_reference"]}个、排序后选中对象{d["first_failure_counts"]["selection_after_sort"]}个、删除后重选{d["first_failure_counts"]["selection_after_delete"]}个；这些是实际状态差异，没有页面错误或选择器缺失。只统计首个失败，不能当作穷尽因果诊断。逐项观察见 `test/results/heldout-composition-diagnostics.json`。', '',
              '| 批次 | 做法 | 候选数 | 发生格式/加载修复的候选 | 额外有效响应 | 无可执行版本 |', '|---|---|---:|---:|---:|---:|']
    for label in ('main', 'strong'):
        c = d['cohorts'][label]['attempts']
        for method in ('free', 'free_lib', 'plan'):
            if method + '/candidates' in c:
                lines.append(f"| {label} | {method} | {c[method+'/candidates']} | {c[method+'/repaired_candidates']} | {c[method+'/extra_attempts']} | {c[method+'/without_executable']} |")
    lines += ['', '首次响应（不将后续首个可执行版本当首次响应）主组方案72/88、同库代码88/88。16次方案格式失败中，10次多包了一层`plan`，6次提交了代码组的`program`形式；通用模式检查拒绝后修复，不涉及行为反馈。同一用户材料同时说明两种输出形式，由system消息选择做法，可能增加方案格式混淆；本批不事后改提示词。主组88个同库代码均直接提交build程序；GPT-5小试11个build程序、1个文件覆盖。', '',
              '| 应用 | 建库者 | 文件数 | 文件字节 | 编译器字节 | 开发通过 |', '|---|---|---:|---:|---:|---:|']
    for lib in s['libraries']:
        lines.append(f"| {lib['project']} | {NAMES[lib['builder']]} | {lib['files']} | {lib['file_bytes']} | {lib['compiler_bytes']} | {lib['development_passes']}/{lib['development_total']} |")
    lines += ['', '四库最终都暴露四个语义选项。这说明模型能给已知行为变化建立可组合接口，仍可能只是配置化实现；没有学习压缩、跨应用共享抽象或自动发现功能边界。人时没有可靠计时，源码/编译器字节和代理执行经过时间均不能冒充人工建库成本。', '',
              '### 19.5 成本、审计与研究主线', '',
              '| 用途 | 输入tokens | 输出tokens（含推理） | 推理tokens | 已采用响应USD |', '|---|---:|---:|---:|---:|']
    for prefix in ('build', 'main/free', 'main/free_lib', 'main/plan', 'strong/free_lib', 'strong/plan'):
        u = s['usage']
        lines.append(f"| {prefix} | {u[prefix+'/prompt_tokens']} | {u[prefix+'/completion_tokens']} | {u[prefix+'/reasoning_tokens']} | {u[prefix+'/cost']:.6f} |")
    lines += ['', '主组方案输出较短，但含格式修复的输入和采用响应费用高于同库代码；不能笼统宣称方案总是更省钱。GPT-5小试方案的输出及推理费用较低，但不折算成普遍成本结论。阶段账本还包含未知传输收费：', '',
              '| 本阶段账本 | 已结算USD | 含未确认预留USD | 未结算请求 |', '|---|---:|---:|---:|']
    for group in s['costs'].values():
        for path, c in group.items():
            lines.append(f"| {Path(path).parent.name} | {c['settled_usd']:.6f} | {c['exposure_usd']:.6f} | {c['unsettled_calls']} |")
    lines += [f"| **本节增量** | **{s['total_cost']['settled_usd']:.6f}** | **{s['total_cost']['exposure_usd']:.6f}** | |",
              f"| **2026-11-12全日累计** | **{daily['settled_usd']:.6f}** | **{daily['exposure_usd']:.6f}** | |", '',
              '全部当天账本stop=0，低于用户累计$20授权；未知费用仍按完整预留保留。只计API，未计价本地计算或人工成本。采用的有效响应均正常stop；供应商原始记录和中断尝试保留，不静默替换模型。', '',
              f"审计核对{s['audit']['candidate_records']}个候选、{s['audit']['fixed_control_scores']}个固定控制、{s['audit']['matched_library_inputs']}对相同同库用户输入、开发包与采用响应、冻结源码及评分前候选快照；保存版本重新编译无差异。另由 `test.replay_new_tables` 独立从原始记录复算第18–19节四批共904个不同候选、874个固定控制及七个阶段账本。", '',
              '**目前明确的是**：保留旧人工/参考库实验作为机制对照，用模型自建库与冻结后复用作为新的研究主线是可行的，无需丢弃历史结果；本合成划分提供了有限的未见组合见证。**还不能确认的是**：自动学习可迁移抽象、应对非模板或隐含需求、跨项目库复用，以及LLM规划相对同库代码/确定性组合的必要收益。不能把本节全过包装成解决了这些问题。后续应优先设计需要接口选择或跨功能约束推理的独立任务，并同时保留确定性组合强基线；不是继续增加当前模板的采样数。', '']
    target = ROOT / '实验结果.md'
    old = target.read_text()
    marker = '\n## 19. 模型自建库'
    suffix = ''
    if marker in old:
        old, tail = old.split(marker, 1)
        following = re.search(r'\n## (\d+)\.', tail)
        if following and int(following.group(1)) > 19:
            suffix = tail[following.start():]
    target.write_text(old.rstrip() + '\n\n' + '\n'.join(lines) + suffix)
    print('Updated 实验结果.md section 19 from audited summaries')


if __name__ == '__main__':
    main()
