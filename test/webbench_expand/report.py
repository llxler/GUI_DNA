"""Render the new results section from saved summaries; never calls a model."""
from __future__ import annotations
import json
import re
from .core import ROOT

NAMES = {'openai/gpt-5': 'GPT-5', 'anthropic/claude-sonnet-4.5': 'Sonnet 4.5',
         'openai/gpt-oss-120b': 'GPT-OSS', 'mistralai/mistral-small-3.2-24b-instruct': 'Mistral'}


def main():
    main = json.loads((ROOT / 'test/results/webbench-expand.json').read_text())
    frontier = json.loads((ROOT / 'test/results/webbench-expand-frontier.json').read_text())
    audit = json.loads((ROOT / 'test/results/webbench-expand-audit.json').read_text())
    scores = json.loads((ROOT / 'test/results/webbench-expand-score-audit.json').read_text())
    assert scores['all_passed'] and not frontier['audit']['regeneration_differences']
    assert audit['all_passed'] and not audit['regeneration_differences']
    diagnostic = json.loads((ROOT / 'test/results/webbench-expand-diagnostics.json').read_text())
    costs = json.loads((ROOT / 'test/results/webbench-expand-cost-checkpoint.json').read_text())
    total = main['method_totals']
    p, c = total['plan']['final'], total['free_lib']['final']
    fp, fc = sum(g['plan'] for g in frontier['groups']), sum(g['free_lib'] for g in frontier['groups'])
    fixed = sum(g['fixed_final'] for g in main['groups'])
    new_stages = ('webbench-expand-build', 'webbench-expand-run', 'webbench-expand-frontier', 'webbench-expand-frontier-2')
    previous = {key: sum(value[key] for name, value in costs['stages'].items() if name not in new_stages)
                for key in ('settled_usd', 'exposure_usd')}
    lines = [
        '## 18. Web-Bench 三项目扩展、封闭方案模式与 GPT-5 medium 对照（2026-11-12）', '',
        f'**结论先行**：在新增的 calculator/table/bom 上，方案 {p}/240、同库代码 {c}/240；无库代码 {total["free"]["final"]}/120（跨建库者只计一次）。独立的 GPT-5 medium 小试为方案 {fp}/30、同库代码 {fc}/30。下表保留各项目、建库者和规划者，不能把这些相关任务当成240个独立应用，也不能与第17节不同协议直接合并。', '',
        f'预先固定的最终方案重用控制为 {fixed}/240。三个项目的**上游最终参考页固定不变即可通过各自20/20任务文件**；因此高任务通过率本身不足以证明逐任务规划有用。固定控制不依赖候选成绩选择，也不是库可达上界或均匀随机方案。', '',
        '### 18.1 新阶段、输入边界与更强同库对照', '',
        '- 项目在上一阶段只按公开需求预选（`test/results/next-projects-plan.json`），固定上游commit `7b31ca2b786eef120dd49ce63dd03d0c0006046d`。三个项目分别覆盖运算/历史、二维表格编辑和iframe浏览器；这是便利选择，不是随机抽样。',
        '- GPT-5 medium与Sonnet 4.5各建三套库；只看公开init＋20项需求和通用运行环境，不给参考源码、测试、人工槽位或页面外壳。六套库首次通过公开格式/确定性/加载检查后冻结；11次有效模型输出、2次未确认中断，最多两次公开修复。**全部目标需求仍对建库者可见，不是未见组合迁移，库也未获行为正确性保证。**',
        '- 模型提出机器可读模式。通用检查只允许封闭对象、有界数组/整数、布尔和标识符枚举；编译前拒绝未知字段、任意源码字符串与动态文件映射。模型仍决定属性、组件、状态和语义；这不是原人工库的逐任务覆盖保证。',
        '- 建库输出显示，GPT-5 calculator主要实现藏在编译器中，而文件映射只有77字节。因此**在任何规划调用前**统一加强同库代码：既可覆盖预载文件，也可输出不受方案模式限制的 `build(files, compile)` JavaScript，直接调用冻结编译器、修改产物或重写页面。不必重抄编译器，也不必实现浏览器文件加载器。两种同库做法的用户内容逐字相同。',
        '- 主实验：GPT-OSS-120B low/Near AI和Mistral Small 3.2/DeepInfra，三个项目×20项累计需求，各自从头生成；无库120个、同库代码240个、方案240个，共600个不同候选。单次12,000输出tokens、最多两次公开格式/加载修复；没有行为测试反馈。该同库基线强于第17节，因此跨阶段差值不能归因于严格检查本身。',
        '- 独立强模型对照：GPT-5 medium/OpenAI，每项目task-4/8/12/16/20、两库×两种做法，共60个候选。任务在任何候选隐藏评分前固定；输入、库、上限与修复次数相同，12,000上限含推理。它不是旧GPT-5最低推理实验的纯推理因子对照，也没有多种子结论。',
        '- 所有660个候选补齐后才评分。传输失败只补缺失请求，保留有效输出和原反馈，不重新抽样完整模型失败；预算断点另立账本，不放宽旧账本。全部候选请求、响应、公开输出和页面在评分前另存完整SHA-256快照。', '',
        '完整冻结协议与正式入口见 `test/webbench_expand/{PRELOAD,EVALUATION,FRONTIER,FRONTIER_CONTINUATION}.md`。早期README是建库时的冻结记录，后续评分以EVALUATION为准。', '',
        '### 18.2 官方评分环境与参考页校准', '',
        '官方断言逐字保留，评分使用上游钉住的Playwright1.57.0及Chromium build1200；每候选一个worker、30秒用例/5秒断言、无重试、首次决定性失败停止。calculator/table最多六候选并发，BOM串行。task-k只评分对应文件，不等于完整历史前缀正确，也不是视觉质量评测。', '',
        'BOM初始CSS为空，官方初始页比1280px视口窄16px，只通过2/3初始断言；最终参考页能通过同一检查。1.63并发下最终参考页为20/20、20/20、18/20，BOM窗口关闭/全屏出现时序问题；1.57六并发为20/20、20/20、19/20，BOM计时断言立即要求0却读到0.1。改为1.57串行，BOM最终参考页20/20通过。所有这些是参考页诊断，不进入模型消息。结果与来源哈希在 `test/results/webbench-expand-calibration.json`。', '',
        '在读取任何候选隐藏成绩前固定敏感性子集：仅去掉BOM task-7/14/19，剩17项；主表仍保留全部20项，不能看模型分数再修改排除集合。', '',
        '### 18.3 三项目主结果', '',
        '| 项目 | 建库者 | 规划者 | 自由代码 | 同库代码 | 方案 | 方案对同库 W/L/T |',
        '|---|---|---|---:|---:|---:|---|']
    for g in main['groups']:
        q = g['vs_free_lib']
        lines.append(f"| {g['project']} | {NAMES[g['builder']]} | {NAMES[g['model']]} | {g['free']}/20 | {g['free_lib']}/20 | {g['plan']}/20 | {q['wins']}/{q['losses']}/{q['ties']} |")
    lines += ['', '无库列在两个建库者行中复用，不重复计数。以下按规划者合计仍只是相关任务的描述统计：', '']
    for model in ('openai/gpt-oss-120b', 'mistralai/mistral-small-3.2-24b-instruct'):
        rows = [g for g in main['groups'] if g['model'] == model]
        lines.append(f"- {NAMES[model]}：方案 {sum(g['plan'] for g in rows)}/120，同库代码 {sum(g['free_lib'] for g in rows)}/120。")
    lines += ['', '| 做法 | 不同候选 | 首个可执行版本通过 | 最后可执行版本通过 | 已采用响应输入tokens | 已采用响应输出tokens | 已采用响应USD |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for method, name in (('free', '无库代码'), ('free_lib', '同库代码'), ('plan', '方案')):
        t = total[method]
        usage = main['used_response_tokens']
        lines.append(f'| {name} | {t["n"]} | {t["first"]} | {t["final"]} | {usage[method + "/prompt"]} | {usage[method + "/completion"]} | {main["used_response_cost_usd"][method]:.6f} |')
    lines += ['', '没有可执行版本的完整模型失败计为不通过；首个可执行版本不一定是首次响应。已采用响应费用不包含全部传输失败/预留，阶段总费用以后文账本为准。', '',
              '同库代码的最终可执行输出形式（只有成功构建页面的候选进入该形式统计，不代表行为通过）：']
    for model in ('openai/gpt-oss-120b', 'mistralai/mistral-small-3.2-24b-instruct'):
        forms = main['final_executable_free_lib_forms']
        lines.append(f'- {NAMES[model]}：build程序 {forms.get(model + "/program", 0)}，文件覆盖 {forms.get(model + "/files", 0)}。')
    lines += ['', '| 预定敏感性口径 | 配对数 | 同库代码 | 方案 | 方案 W/L |', '|---|---:|---:|---:|---|']
    for project in main['projects']:
        rows = [g['predefined_sensitivity'] for g in main['groups'] if g['project'] == project]
        lines.append(f"| {project} | {sum(g['n'] for g in rows)} | {sum(g['free_lib'] for g in rows)} | {sum(g['plan'] for g in rows)} | {sum(g['plan_wins_vs_free_lib'] for g in rows)}/{sum(g['plan_losses_vs_free_lib'] for g in rows)} |")
    lines += ['', '### 18.4 固定配置、库规模与有效决策', '',
        '| 项目 | 建库者 | 文件数 | 文件字节 | 编译器字节 | 有效建库尝试 | 示例0 | 示例1 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for lib in main['libraries']:
        g = next(g for g in main['groups'] if g['project'] == lib['project'] and g['builder'] == lib['builder'])
        lines.append(f"| {lib['project']} | {NAMES[lib['builder']]} | {lib['files']} | {lib['source_bytes']} | {lib['compiler_bytes']} | {lib['attempts']} | {g['example-0']}/20 | {g['example-1']}/20 |")
    lines += ['', '两个文档示例各自在全部任务上不变地执行，均报告，不选高分者。编译器可包含主要实现，因此文件映射大小不能单独当作库大小。另一个固定对照使用每个规划者task-20最后可执行页，没有可执行页则记失败：', '',
        '| 项目 | 建库者 | 规划者 | 固定最终页 | 逐任务方案 | 逐任务对固定 W/L |', '|---|---|---|---:|---:|---|']
    for g in main['groups']:
        q = g['vs_fixed_final']
        lines.append(f"| {g['project']} | {NAMES[g['builder']]} | {NAMES[g['model']]} | {g['fixed_final']}/20 | {g['plan']}/20 | {q['wins']}/{q['losses']} |")
    disagreements = diagnostic['identical_page_score_disagreements']
    lines += ['', f'相同已保存文件映射的重复评分诊断发现 {len(disagreements)} 条对照不一致；逐项记录在 `test/results/webbench-expand-diagnostics.json`，未据此择优重跑或改动预定子集。不同文件哈希不证明行为不同，固定配置也不是库的可达上界。', '',
        '### 18.5 GPT-5 medium 独立小试', '',
        '| 项目 | 建库者 | 同库代码 | 方案 | 固定最终页 | 方案对代码 W/L |', '|---|---|---:|---:|---:|---|']
    for g in frontier['groups']:
        lines.append(f"| {g['project']} | {NAMES[g['builder']]} | {g['free_lib']}/5 | {g['plan']}/5 | {g['fixed_final']}/5 | {g['plan_wins_vs_code']}/{g['plan_losses_vs_code']} |")
    lines += ['', '| GPT-5做法 | 输入tokens | 输出tokens（含推理） | 其中推理tokens | 已采用响应USD |', '|---|---:|---:|---:|---:|']
    for method, name in (('free_lib', '同库代码'), ('plan', '方案')):
        u = frontier['usage']
        lines.append(f'| {name} | {u[method + "/prompt_tokens"]} | {u[method + "/completion_tokens"]} | {u[method + "/reasoning_tokens"]} | {u[method + "/cost"]:.6f} |')
    lines += ['', '任务是每四项一个里程碑，不能当作完整20项或独立新项目。实际输出/推理tokens、费用与所有逐候选结果见 `test/results/webbench-expand-frontier.json`；不将这60个记录混进600个主实验。', '',
        '### 18.6 费用、边界核对与剩余工作', '',
        '| 当天阶段 | 已结算 USD | 含未知预留 USD |', '|---|---:|---:|',
        f'| 本次续作前的{len(costs["stages"]) - len(new_stages)}个阶段 | {previous["settled_usd"]:.6f} | {previous["exposure_usd"]:.6f} |']
    for name in new_stages:
        c = costs['stages'][name]
        lines.append(f"| {name} | {c['settled_usd']:.6f} | {c['exposure_usd']:.6f} |")
    lines += [f"| **本批结束时当天累计** | **{costs['settled_usd']:.6f}** | **{costs['exposure_usd']:.6f}** |", '',
        '截至本批结束时，全部当天账本均已关闭新请求，低于用户$20授权；不把未确认的收费当作零。GPT-5初始账本因预留触及stop阈值，关闭后用独立$2账本复制全部记录并续补，未放宽原账本。上述只计API，人工时间和本机计算未计价。原第三轮继续暂停。', '',
        f'主实验审计核对{audit["frozen_hash_entries"]}个冻结哈希、{audit["records"]}条记录、{audit["checked_executable_versions"]}个可执行版本、{audit["matched_library_user_inputs"]}对逐字相同的同库用户输入；{len(audit["rejected_plan_attempts"])}次不合格式的方案提案被拒。采用响应终止原因为{audit["used_response_finishes"]}，达到长度上限的完整响应保留为模型结果。所有保存文件映射重建一致。GPT-5阶段另核对30对输入及60条记录，详见其JSON审计字段。', '',
        f'另从{scores["distinct_raw_reports"]}份不同原始Playwright报告核对全部660个候选及510个固定控制的已存分数，哈希与任务级判定一致；没有页面的完整失败单独核对为不通过。范围与逐报告哈希见 `test/results/webbench-expand-score-audit.json`，这是保存结果的独立复算，不是额外浏览器重复实验。', '',
        '**目前明确的是**：模型可以从公开需求提出符合封闭模式的接口，但这既不保证库行为正确，也不保证方案需要随任务改变；最终参考页和固定配置控制是解释这些分数的必要证据。**还不能确认的是**：建库时未见的需求组合能否迁移、接口是否充分表达目标行为，以及在多种子和成熟浏览器代理下是否仍有收益。P2c的下一阶段必须预先隔离开发需求与测试组合；直接把前10项/后10项分开通常同时引入新功能，不能冒充已知原语的新组合。', '',
        '代码、汇总和方法说明入Git；论文与原始请求/页面/账本仍仅本地保存。第17节的匿名包是此前的时间点快照，尚未包含本次新阶段，匿名发布与扩展复验仍属TODO R11b。', '']
    target = ROOT / '实验结果.md'
    old = target.read_text()
    marker = '\n## 18. Web-Bench 三项目扩展'
    suffix = ''
    if marker in old:
        old, tail = old.split(marker, 1)
        following = re.search(r'\n## (\d+)\.', tail)
        if following and int(following.group(1)) > 18:
            suffix = tail[following.start():]
    target.write_text(old.rstrip() + '\n\n' + '\n'.join(lines) + suffix)
    print('Rendered results section18 from saved summaries.')


if __name__ == '__main__':
    main()
