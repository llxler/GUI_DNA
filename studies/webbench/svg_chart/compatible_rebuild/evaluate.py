"""Replay the same offline plans through three frozen SVG backends, validating official reports."""
import argparse
import json
from pathlib import Path

from studies.library_refinement_chart import adapter
from studies.study_io import ROOT, digest, dump, now, read, sha, source_files
from studies.svg_chart_compact_local import run as qwen
from . import build

OUT, RUNTIME, NAMES = build.OUT, build.RUNTIME, build.NAMES
PUBLIC = ROOT / 'studies/results/compatible-chart-rebuild-20261123.json'


def hashes(paths):
    return {str(path.relative_to(ROOT)): sha(path) for path in paths}


def verify(evidence):
    for path, expected in evidence.items():
        assert sha(ROOT / path) == expected, path


def builds():
    registration = read(OUT/'registered.json')
    verify(registration['sha256'])
    seal = read(OUT/'sealed.json')
    assert seal['registered_sha256'] == sha(OUT/'registered.json')
    old = adapter.old_package()
    public = read(OUT/'public.json')
    requirements, starter, assets = adapter.public_inputs()
    assert public == {'requirements': requirements, 'starter': starter, 'assets': assets,
                      'plan_schema': old['plan_schema'], 'examples': old['examples']}
    assert (OUT/'prompt.txt').read_text() == build.PROMPT+'\n'+json.dumps(public, ensure_ascii=False)
    assert read(OUT/NAMES[0]/'package.json') == old
    packages = {NAMES[0]: old}
    for name, status in seal['states'].items():
        folder = OUT/name
        assert read(folder/'status.json') == status
        for file, value in status['evidence'].items():
            assert sha(folder/file) == value
        if status['status'] == 'accepted':
            events = [json.loads(line) for line in (folder/'events.jsonl').read_text().splitlines() if line.strip()]
            tools = [e['item']['type'] for e in events if isinstance(e.get('item'), dict) and e['item']['type'] not in ('reasoning','agent_message','plan')]
            assert not tools and [e['usage'] for e in events if e['type'] == 'turn.completed'] == status['usage']
            pkg = read(folder/'package.json')
            assert pkg == build.package(read(folder/'reply.json'), public) and sha(folder/'package.json') == status['package_sha256']
            packages[name] = pkg
    return packages


def frozen(path):
    value = read(path)
    verify(value['sha256'])
    return value


def plan_page(pkg, plan, folder):
    files = adapter.materialize_plan(pkg, plan, folder)
    return {'files': files, 'page': str(folder.relative_to(ROOT))}


def fixed_pages():
    packages = builds()
    marker = OUT/'fixed-pages.json'
    if marker.exists():
        return frozen(marker)
    rows = {}
    inputs = [Path(__file__), OUT/'registered.json', OUT/'sealed.json', qwen.CONTROL/'freeze.json']
    for name, pkg in packages.items():
        inputs.append(OUT/name/'package.json')
        example = pkg['examples'][0]['plan']
        assert qwen.read_plan(json.dumps(example)) == example
        fixed = plan_page(pkg, example, RUNTIME/'pages'/name/'fixed-first')
        rows[name] = [{'task': n, 'response': True, **fixed} for n in adapter.TASKS]
    reference = read(qwen.CONTROL/'freeze.json')['fixed']
    assert all(x['task']==y['task'] and x['files']==y['files'] for x,y in zip(rows[NAMES[0]], reference, strict=True))
    dump(marker, {'utc': now(), 'rows': rows, 'sha256': hashes(inputs)})
    return frozen(marker)


def fixed_scores(workers):
    fixed = fixed_pages()['rows']
    for name in NAMES[1:]:
        if name in fixed:
            adapter.score_run(RUNTIME/'fixed-scores'/name, fixed[name], workers)


def candidates():
    marker = OUT/'candidates.json'
    if marker.exists():
        return frozen(marker)
    packages = builds()
    fixed = fixed_pages()['rows']
    gen = read(qwen.OUT/'local-generation.json')
    inputs = [qwen.OUT/'local-generation.json', qwen.OUT/'local-inputs.json', qwen.OUT/'freeze.json', OUT/'fixed-pages.json', OUT/'sealed.json']
    records = {name: [] for name in packages}
    for n in adapter.TASKS:
        raw_path = qwen.OUT/'runs'/f'task-{n}'/'response.json'
        prompt = qwen.OUT/'prompts'/f'task-{n}.json'
        inputs.extend([raw_path,prompt])
        assert sha(raw_path) == gen['response_sha256'][str(n)]
        receipt = read(raw_path)
        assert receipt['task']==n and receipt['prompt_sha256']==sha(prompt)
        assert (receipt['model'], receipt['revision'], receipt['generation_config']) == (qwen.MODEL, qwen.REVISION, qwen.GENERATION)
        plan = None
        if receipt['complete']:
            try:
                plan = qwen.read_plan(receipt['text'])
            except (ValueError, TypeError, KeyError, OverflowError):
                pass
        for name, pkg in packages.items():
            row = {'task': n, 'response': receipt['complete'], 'response_sha256': sha(raw_path), 'valid_plan': plan is not None,
                   'fallback': False, 'files': None, 'fixed_same_page': False}
            if plan is not None:
                try:
                    row.update(plan_page(pkg, plan, RUNTIME/'pages'/name/f'task-{n}'))
                except (ValueError, TypeError, KeyError, OverflowError) as exc:
                    row['compile_error'] = str(exc)[:300]
            row['fallback'] = bool(row['response'] and not row['files'])
            row['fixed_same_page'] = bool(row['files'] and row['files'] == fixed[name][n-1]['files'])
            records[name].append(row)
    dump(marker, {'utc': now(), 'rows': records, 'sha256': hashes(inputs)})
    return frozen(marker)


def strict_scores(workers):
    rows = candidates()['rows']
    for name in NAMES[1:]:
        if name in rows:
            new = [r if not r['fixed_same_page'] else {'task':r['task'], 'response':True, 'files':None} for r in rows[name]]
            adapter.score_run(RUNTIME/'strict-scores'/name, new, workers)


def audited_cells(directory, matching):
    info = read(directory/'evaluation-inputs.json')
    adapter.verify_inputs(info)
    complete = read(directory/'evaluation-complete.json')
    assert complete['inputs_sha256'] == sha(directory/'evaluation-inputs.json')
    assert len(info['rows']) == len(complete['cells']) == len(matching) == 20
    checked = {}
    for row, expected in zip(info['rows'], matching, strict=True):
        n = row['task']
        assert expected['task'] == n and expected['response'] == row['response'] and (expected.get('files') or None) == row['files']
        v = complete['cells'][str(n)]
        if row['files']:
            assert source_files(ROOT/row['page']) == row['files'] == source_files(ROOT/expected['page'])
            folders = [p for p in directory.glob(f'scores/official-*/task-{n}') if (p/'score.json').exists() and sha(p/'report.json')==v['report_sha256']]
            assert len(folders)==1 and adapter.checked_score(folders[0], n)['passed'] == v['passed']
        else:
            assert v['report_sha256'] is None and v['passed']==(False if row['response'] else None)
        checked[n] = {'passed': v['passed'], 'report_sha256': v['report_sha256']}
    return checked


def condensed(rows, key):
    return {'passed': sum(r[key]['passed'] is True for r in rows), 'observed': sum(r[key]['passed'] is not None for r in rows), 'planned': len(rows)}


def paired(old, new, key):
    result = {'gained': [], 'lost': [], 'both_pass': [], 'both_fail': [], 'unknown': []}
    for a,b in zip(old,new,strict=True):
        assert a['task'] == b['task']
        x,y = a[key]['passed'],b[key]['passed']
        group = 'unknown' if x is None or y is None else {(True,True):'both_pass',(False,True):'gained',(True,False):'lost',(False,False):'both_fail'}[(x,y)]
        result[group].append(a['task'])
    return result


def result():
    builds_by_name = builds()
    selection = candidates()['rows']
    fixed = fixed_pages()['rows']
    summaries, details = {}, {}
    for name in builds_by_name:
        old = name == NAMES[0]
        rows = selection[name]
        fixed_dir = qwen.CONTROL/'fixed-evaluation' if old else RUNTIME/'fixed-scores'/name
        strict_dir = qwen.EVAL if old else RUNTIME/'strict-scores'/name
        fixed_cells = audited_cells(fixed_dir, fixed[name])
        for n,expected in enumerate(rows, 1):
            assert expected['task']==n
            if expected['files']:
                assert expected['files']==source_files(ROOT/expected['page'])
        nonredundant = [r if old or not r['fixed_same_page'] else {'task':r['task'], 'response':True,'files':None} for r in rows]
        strict_cells = audited_cells(strict_dir, nonredundant)
        items = []
        for r in rows:
            n = r['task']
            strict = fixed_cells[n] if not old and r['fixed_same_page'] else strict_cells[n]
            items.append({k:r[k] for k in ('task','response','response_sha256','valid_plan','fallback','fixed_same_page')} |
                         {'compiled': bool(r['files']), 'page_sha256': digest(r['files']) if r['files'] else None,
                          'strict': strict, 'fallback_deployment': fixed_cells[n] if r['fallback'] else strict, 'fixed_example_1': fixed_cells[n]})
        details[name] = items
        summaries[name] = {'received': sum(r['response'] for r in items), 'valid_plans': sum(r['valid_plan'] for r in items),
                           'compiled': sum(r['compiled'] for r in items), 'fallback_used': sum(r['fallback'] for r in items),
                           **{k:condensed(items,k) for k in ('strict','fallback_deployment','fixed_example_1')}}
    differences = {name:{k:paired(details[NAMES[0]],items,k) for k in ('strict','fallback_deployment','fixed_example_1')} for name,items in details.items() if name!=NAMES[0]}
    passed = len(differences)==2 and all(summaries[name]['received']==20 and all(len(diff[k]['gained'])>len(diff[k]['lost']) for k in ('strict','fixed_example_1')) for name,diff in differences.items())
    return {'study': 'compatible-chart-rebuild-20261123', 'project':'web-bench/svg-chart', 'model':build.MODEL,'planner':qwen.MODEL,
            'source': 'Prior GPT-5 text interface and examples. Independent, tool-free first Codex builds from the same project requirements, starter, assets and contract instructions.',
            'conditions': 'Identical Qwen first responses per target, 20 current task files. On a received invalid/uncompilable response, deployed condition uses that backend’s first example. Missing responses remain missing.',
            'independent_builds':read(OUT/'sealed.json')['states'],'additional_openrouter_requests':0,'additional_openrouter_cost_usd':0,
            'summaries':summaries,'paired_to_old':differences,'targets':details,'repeated_backend_improvement':passed,
            'qualification':'Old versus new changes builder model and implementation. Two generated libraries reuse the same tasks and responses. The historical Mistral 3/20 and the old fixed first example are distinct endpoints.',
            'hashes':hashes([OUT/'registered.json',OUT/'sealed.json',OUT/'fixed-pages.json',OUT/'candidates.json',qwen.OUT/'local-generation.json'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['fixed','strict','report','check'])
    parser.add_argument('--workers',type=int,default=2)
    args = parser.parse_args()
    if args.action == 'fixed':
        fixed_scores(args.workers)
    elif args.action == 'strict':
        strict_scores(args.workers)
    else:
        value = result()
        if args.action=='check' or PUBLIC.exists():
            assert read(PUBLIC)==value
        else:
            dump(PUBLIC,value)
        print(value['summaries'])


if __name__=='__main__':
    main()
