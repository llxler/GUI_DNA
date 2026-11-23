"""Paired compact-output fence sensitivity for the same three frozen chart backends."""
import argparse
from pathlib import Path

from studies.library_refinement_chart import adapter
from studies.study_io import ROOT, dump, now, read, sha, source_files
from studies.svg_chart_compact_local import fences as former
from . import evaluate as primary

OUT = primary.OUT/'one-fence'
RESULT = ROOT/'studies/results/compatible-chart-rebuild-fences-20261123.json'


def predeclare():
    marker=OUT/'registered.json'
    if marker.exists():
        return primary.frozen(marker)
    paths=[Path(__file__),Path(__file__).with_name('FENCES.md'),Path(former.__file__),primary.OUT/'sealed.json',primary.OUT/'fixed-pages.json',former.INSPECT/'freeze.json']
    dump(marker,{'utc':now(),'sha256':primary.hashes(paths)})
    return primary.frozen(marker)


def prepare():
    predeclare()
    path=OUT/'candidates.json'
    if path.exists():
        return primary.frozen(path)
    packages=primary.builds()
    sel=primary.candidates()['rows']
    control=primary.fixed_pages()['rows']
    arms={}
    for name,pkg in packages.items():
        rows=[]
        for record in sel[name]:
            n=record['task']
            raw=primary.qwen.OUT/'runs'/f'task-{n}'/'response.json'
            assert sha(raw)==record['response_sha256']
            action='keep'
            page={}
            if record['response'] and not record['valid_plan']:
                matched=former.FENCE.fullmatch(read(raw)['text'])
                if matched:
                    try:
                        plan=primary.qwen.read_plan(matched.group(1))
                        page=primary.plan_page(pkg,plan,primary.RUNTIME/'fence-pages'/name/f'task-{n}')
                        action='new_valid'
                    except (TypeError,ValueError,KeyError,OverflowError):
                        action='still_invalid'
                else:
                    action='no_single_fence'
            rows.append({'task':n,'response':bool(page),'files':None,'action':action,
                         'fixed_same_page':bool(page) and page['files']==control[name][n-1]['files'],**page})
        arms[name]=rows
    dump(path,{'utc':now(),'rows':arms,'sha256':primary.hashes([OUT/'registered.json',primary.OUT/'candidates.json'])})
    return primary.frozen(path)


def jobs(rows):
    return [r if not r['fixed_same_page'] else {'task':r['task'],'response':False,'files':None} for r in rows]


def score(workers):
    rows=prepare()['rows']
    for name in primary.NAMES[1:]:
        if name in rows:
            adapter.score_run(primary.RUNTIME/'single-fence-scores'/name,jobs(rows[name]),workers)


def result():
    base=primary.result()
    rows=prepare()['rows']
    details={}
    summary={}
    for name, conditioned in rows.items():
        old=name==primary.NAMES[0]
        directory=primary.qwen.PREVIOUS/'replays/svg-chart-local-single-fence/compact' if old else primary.RUNTIME/'single-fence-scores'/name
        retained=conditioned if old else jobs(conditioned)
        receipts=primary.audited_cells(directory,retained)
        data=[]
        for base_row,row in zip(base['targets'][name],conditioned,strict=True):
            n=row['task']
            assert base_row['task']==n
            if row['files']:
                assert source_files(ROOT/row['page'])==row['files']
            success=row['action']=='new_valid'
            res=base_row['fixed_example_1'] if row['fixed_same_page'] and not old else receipts[n]
            main=res if success else base_row['strict']
            fallback=res if success else base_row['fallback_deployment']
            data.append({'task':n,'action':row['action'],'valid_after_unwrap':success or base_row['compiled'],
                         'fallback_used':base_row['fallback'] and not success,'response':base_row['response'],
                         'strict':base_row['strict'],'one_fence':main,'one_fence_then_example':fallback})
        if old:
            earlier=read(former.INSPECT/'compact/results.json')['rows']
            assert all((x['task'],x['action'],x['one_fence']['passed'],x['one_fence_then_example']['passed']) ==
                       (y['task'],y['action'],y['fence_enabled'],y['fence_plus_default']) for x,y in zip(data,earlier,strict=True))
        summary[name]={'new_valid':sum(v['action']=='new_valid' for v in data), 'valid':sum(v['valid_after_unwrap'] for v in data),
                       'fallback_used':sum(v['fallback_used'] for v in data), **{k:primary.condensed(data,k) for k in ('one_fence','one_fence_then_example')}}
        details[name]=data
    return {'study':'compatible-chart-rebuild-fences-20261123','supplementary':True,'planner':primary.qwen.MODEL,
            'rule':'After first fenced output was observed and before grading new backends, accept one complete enclosing JSON Markdown fence and apply the same strict typed validator.',
            'summaries':summary,'targets':details,'paired_to_old':{n:{k:primary.paired(details[primary.NAMES[0]],d,k) for k in ('one_fence','one_fence_then_example')} for n,d in details.items() if n!=primary.NAMES[0]},
            'sha256':primary.hashes([OUT/'registered.json',OUT/'candidates.json',primary.PUBLIC,former.INSPECT/'compact/results.json'])}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','score','report','check'))
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    if args.action=='freeze':
        print(predeclare()['utc'])
    elif args.action=='score':
        score(args.workers)
    else:
        data=result()
        if args.action=='check' or RESULT.exists():
            assert read(RESULT)==data
        else:
            dump(RESULT,data)
        print(data['summaries'])
