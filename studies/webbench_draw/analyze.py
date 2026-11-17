"""Verify frozen draw inputs and reports and reconstruct every reported count."""
from __future__ import annotations
from collections import Counter, defaultdict
import hashlib
import json
from gui_dna.provider import parse_json
from gui_dna.budget import micros
from test.ledger_read import calls
from test.history_replay.run import read, sha, cases_by_file, dump, source_files, digest
from test.authorized_costs import summarize as costs
from .core import ROOT, BUILD, BUILDERS, STAGES, slug, compile_plan, output_files
from .browser import OUT


def analyze():
    manifest = read(OUT / 'inputs.json')
    complete = read(OUT / 'evaluation-complete.json')
    assert complete['inputs_sha256'] == sha(OUT / 'inputs.json')
    for name, checksum in manifest['sha256'].items():
        assert sha(ROOT / name) == checksum, name
    scores = {}
    for key, job in manifest['jobs'].items():
        folder = OUT / 'scores' / key
        score = read(folder / 'score.json')
        assert score['job'] == job
        assert sha(folder / 'report.json') == score['report_sha256']
        raw = read(folder / 'report.json')
        cases = cases_by_file(raw)
        assert cases == score['cases']
        passed = score['returncode'] == 0 and set(cases) == set(job['specs']) and all(c['passed'] for tests in cases.values() for c in tests)
        assert score['passed'] == passed
        scores[key] = passed
    rows = [{**r, 'passed':scores[r['score_key']] if r['score_key'] else False} for r in manifest['rows']]
    grouped = defaultdict(list)
    for row in rows:
        key = tuple(row[k] for k in ('model','builder','method','label','endpoint','status'))
        grouped[key].append(row)
    groups = [dict(zip(('model','builder','method','label','endpoint','status'), key),
        passed=sum(r['passed'] for r in values),total=len(values)) for key,values in grouped.items()]
    records = []
    library_rows, packages, usage = [], {}, defaultdict(Counter)
    def hashes(files):
        return {name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()}
    for builder in BUILDERS:
        folder = BUILD / 'libraries' / slug(builder)
        record = read(folder / 'record.json')
        entry = {'builder':builder,'status':record['status'],'attempts':len(record['attempts'])}
        if record['status'] == 'frozen':
            package = read(folder / 'package.json')
            assert digest(package) == record['package_sha256']
            assert parse_json(read(folder / f"output-{record['selected_attempt']}.json")['text']) == package
            packages[builder] = package
            for i,example in enumerate(package['examples']):
                page = folder / f"validation-{record['selected_attempt']}/example-{i}"
                assert hashes(compile_plan(package,example['plan'])) == source_files(page)
            entry.update(files=len(package['files']),source_bytes=sum(len(s.encode()) for s in package['files'].values()),
                compiler_bytes=len(package['compiler'].encode()),schema=package['plan_schema'],package_sha256=digest(package))
        library_rows.append(entry)
    for model,out in STAGES.items():
        assert read(out / 'generation-complete.json')['finished_utc'] <= manifest['created_utc']
        for path in (out / 'runs').rglob('record.json'):
            record = read(path)
            records.append(record)
            package = packages.get(record['builder'])
            if package:
                assert record['package_sha256'] == digest(package)
            for attempt in record['attempts']:
                if attempt['version']:
                    raw = read(path.parent / f"output-{attempt['attempt']}.json")['text']
                    files = output_files(record['method'],package,parse_json(raw))
                    assert hashes(files) == source_files(path.parent / attempt['version']), str(path)
            if record['method'] == 'plan':
                code = path.parent.parent.parent / 'free_lib' / record['task'] / 'messages.json'
                assert read(path.parent / 'messages.json')[1] == read(code)[1]
    for out in [BUILD,*STAGES.values()]:
        ledger_calls = {row['id']:row for row in calls(out / 'budget.sqlite3')}
        verified_calls = set()
        for path in out.rglob('response.json'):
            if 'node_modules' in path.parts:
                continue
            response = read(path)
            request = read(path.with_name('request.json'))
            category = 'build' if out == BUILD else path.parents[2].name
            group = usage[request['body']['model'] + '/' + category]
            value = response['usage']
            assert ledger_calls[request['call_id']]['actual'] == micros(value['cost'])
            verified_calls.add(request['call_id'])
            group['calls'] += 1
            group['cost_usd'] += value['cost']
            group['ledger_microusd'] += micros(value['cost'])
            group['finish/' + str(response['choices'][0].get('finish_reason'))] += 1
            group['provider/' + str(response.get('provider','unknown'))] += 1
            for key in ('prompt_tokens','completion_tokens'):
                group[key] += value.get(key,0)
            group['reasoning_tokens'] += (value.get('completion_tokens_details') or {}).get('reasoning_tokens',0)
            group['cached_tokens'] += (value.get('prompt_tokens_details') or {}).get('cached_tokens',0)
        assert verified_calls == {ident for ident,row in ledger_calls.items() if row['actual'] is not None}
    pairing = []
    for model in STAGES:
        for endpoint in ('current','history'):
            selected = [r for r in rows if r['model']==model and r['endpoint']==endpoint and r['label']=='final'
                and r['method'] in ('plan','free_lib') and r['status']=='complete']
            pairs = defaultdict(dict)
            for row in selected:
                pairs[(row['builder'],row['task'])][row['method']] = row['passed']
            values = [p for p in pairs.values() if len(p)==2]
            pairing.append({'model':model,'endpoint':endpoint,'pairs':len(values),
                'plan':sum(p['plan'] for p in values),'code':sum(p['free_lib'] for p in values),
                'plan_only':sum(p['plan'] and not p['free_lib'] for p in values),
                'code_only':sum(p['free_lib'] and not p['plan'] for p in values)})
    result = {'project':'draw','planned_candidates':50,'observed_candidates':len(records),
        'statuses':dict(Counter(r['status'] for r in records)), 'reports':len(scores),'comparisons':len(rows),
        'groups':groups,'pairs':pairing,'costs':costs('20261117'),'rows':rows,
        'libraries':library_rows,'usage':dict(usage),'source_recompilation':True,
        'scope':'Independent convenience-selected public project; Vite protocol. Do not merge with earlier static-server cohorts. Current and full-history endpoints differ.'}
    result['method_totals'] = {label:{endpoint:{method:{
        'passed':sum(r['passed'] for r in rows if r['label']==label and r['endpoint']==endpoint and r['method']==method and r['status']=='complete'),
        'total':sum(r['label']==label and r['endpoint']==endpoint and r['method']==method and r['status']=='complete' for r in rows)
        } for method in ('free','free_lib','plan')} for endpoint in ('current','history')} for label in ('first','final')}
    final_lookup = {(r['model'],r['builder'],r['method'],r['task'],r['endpoint']):r for r in rows if r['label']=='final'}
    fixed_pairs = [(r['passed'],final_lookup[r['model'],r['builder'],'control/final-plan',r['task'],r['endpoint']]['passed'])
        for r in rows if r['label']=='final' and r['method']=='plan']
    result['fixed_final_agreement'] = {'same':sum(a==b for a,b in fixed_pairs),'total':len(fixed_pairs)}
    assert sum(u['ledger_microusd'] for u in usage.values()) == round(result['costs']['settled_usd']*1_000_000)
    result['provider_billed_usd'] = round(sum(u['cost_usd'] for u in usage.values()),8)
    result['ledger_rounding_policy'] = 'Each settled request is rounded upward to integer micro-USD by the unchanged budget ledger.'
    dump(ROOT / 'test/results/webbench-draw-20261117.json', result)
    lines = ['# Web-Bench draw：2026-11-17独立实验', '',
        '| 模型 | 建库者 | 方法 | 输出 | 端点 | 状态 | 通过 |', '|---|---|---|---|---|---|---|']
    for group in groups:
        lines.append('| ' + ' | '.join(str(group[k]) for k in ('model','builder','method','label','endpoint','status')) + f" | {group['passed']}/{group['total']} |")
    lines += ['',f"{len(records)}/50个预定候选，{len(rows)}项比较，{len(scores)}份去重报告。",'',
        f"新增API已结算 ${result['costs']['settled_usd']:.6f}，含未知预留敞口 ${result['costs']['exposure_usd']:.6f}。",'',result['scope']]
    (ROOT / 'test/results/webbench-draw-20261117.md').write_text('\n'.join(lines)+'\n')
    return result


if __name__ == '__main__':
    result = analyze()
    print(json.dumps({k:result[k] for k in ('observed_candidates','statuses','reports','comparisons','pairs','costs')},indent=2))
