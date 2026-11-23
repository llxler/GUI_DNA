"""Audit fresh local plans on the identical public interface of five sealed backends."""
import argparse
from hashlib import sha256
from pathlib import Path

from gui_dna.provider import parse_json
from studies.compatible_library_rebuild import build
from studies.compatible_library_rebuild.sealed_evaluate_20261123 import score_entry
from studies.interface_blind.core import write_files
from studies.library_refinement_table.adapter import score_pages
from studies.study_io import ROOT, digest, dump, now, read, sha, source_files
from studies.table_library_sources import core
from studies.table_library_sources.run import verify
from studies.webbench_expand.schema import validate
from .prepare import HERE, OUT

RESULT = ROOT / 'studies/results/compatible-table-local-plans-20261123.json'
BACKENDS = ('original', *build.ARMS)
EVAL = OUT / 'evaluation'
PRIOR = build.OUT / 'evaluation'


def freeze():
    manifest = EVAL / 'sealed.json'
    if manifest.exists():
        frozen = read(manifest)
        verify(frozen['sources'])
        return frozen
    if (EVAL / 'scores').exists():
        raise ValueError('Unsealed candidates cannot follow official scores')
    inputs = read(OUT/'local-inputs.json')
    responses = read(OUT/'local-generation.json')
    source_paths = [OUT/f for f in ('registered.json','decoding.json','local-inputs.json','local-generation.json')]
    source_paths += [HERE/f for f in ('PROTOCOL.md','DECODING.md','prepare.py','evaluate.py')]
    decoder = ROOT/'studies/svg_chart_compact_local/local_planner.py'
    assert inputs['worker_sha256'] == sha(decoder)
    source_paths.extend([build.OUT/'sealed.json', build.OUT/'public.json', core.AI, decoder])
    assert responses['inputs_sha256'] == sha(OUT/'local-inputs.json') and responses['requests_to_remote_apis'] == 0
    registered = read(OUT/'registered.json')
    assert registered['protocol'] == sha(HERE/'PROTOCOL.md') and registered['source'] == sha(build.OUT/'public.json')
    assert read(OUT/'decoding.json')['sha256'] == sha(HERE/'DECODING.md')
    assert registered['source_sha256'] == sha(HERE/'prepare.py')
    assert inputs['revision'] == '7ae557604adf67be50417f59c2c2f167def9a775'
    assert inputs['model'] == registered['model'] and not inputs['generation_config']['do_sample']
    assert inputs['generation_config']['max_new_tokens'] == 768 and inputs['batch_size'] == 1
    sealed = read(build.OUT/'sealed.json')
    packages={'original':read(core.AI)}
    for arm in build.ARMS:
        if sealed['status'][arm]['status'] == 'accepted':
            path = build.OUT/arm/'package.json'
            assert sha(path) == sealed['status'][arm]['package_sha256']
            packages[arm]=read(path)
            assert all(packages[arm][k]==packages['original'][k] for k in ('plan_schema','examples','plan_documentation'))
            source_paths.append(path)
    rows={}
    for n in range(1,21):
        task=f'task-{n}'
        prompt=OUT/'prompts'/f'{task}.json'
        path=OUT/'runs'/task/'response.json'
        receipt=read(path)
        source_paths.extend([path,prompt])
        assert responses['response_sha256'][str(n)] == sha(path)
        assert receipt['prompt_sha256'] == inputs['prompt_sha256'][str(n)] == registered['prompt_sha256'][prompt.name] == sha(prompt)
        assert receipt['model']==inputs['model'] and receipt['revision']==inputs['revision']
        assert receipt['task']==n and receipt['output_tokens']==len(receipt['generated_token_ids']) and receipt['generation_config']==inputs['generation_config']
        plan=None
        error=None
        if receipt['complete']:
            try:
                plan=parse_json(receipt['text'])
                validate(packages['original']['plan_schema'],plan)
            except (ValueError,TypeError) as exc:
                plan=None
                error=str(exc)
        pages={}
        for arm,package in packages.items():
            if plan is None:
                continue
            files=core.render('ai',package,plan)
            hashes={k:sha256(v.encode()).hexdigest() for k,v in files.items()}
            key=digest(hashes)
            page=EVAL/'pages'/key
            if not page.exists():
                write_files(page,files)
            assert source_files(page)==hashes
            pages[arm]=key
        rows[task]={'received':receipt['complete'],'valid':plan is not None,'format_error':error,
                    'plan':plan,'pages':pages,'input_tokens':receipt['input_tokens'],'output_tokens':receipt['output_tokens']}
    frozen={'sealed_utc':now(),'sources':{str(p.relative_to(ROOT)):sha(p) for p in source_paths},'rows':rows,
            'available_backends':list(packages),'model':inputs['model'],'revision':inputs['revision']}
    dump(manifest,frozen)
    return frozen


def score(frozen,workers):
    if (EVAL/'scored.json').exists():
        return
    jobs=[]
    evidence={}
    borrowed={}
    parent=PRIOR/'scores-complete.json'
    if parent.exists():
        borrowed=read(parent)['results']
    for task,row in frozen['rows'].items():
        for key in set(row['pages'].values()):
            job=f'{task}-{key}'
            page=EVAL/'pages'/key
            assert digest(source_files(page))==key
            if job in borrowed:
                candidate=ROOT/borrowed[job]['report_file']
                assert (PRIOR/'pages'/key).is_dir() and digest(source_files(PRIOR/'pages'/key))==key
                assert score_entry(candidate.parent,task)==borrowed[job]
                evidence[job]=str(candidate.relative_to(ROOT))
            else:
                jobs.append((job,task,page))
    if jobs:
        score_pages(EVAL,jobs,workers)
        evidence.update({key:str((EVAL/'scores'/key/'report.json').relative_to(ROOT)) for key,_,_ in jobs})
    dump(EVAL/'scored.json',{'sealed_sha256':sha(EVAL/'sealed.json'),'reports':evidence,'scored':now()})


def report(frozen):
    stage=read(EVAL/'scored.json')
    assert stage['sealed_sha256']==sha(EVAL/'sealed.json')
    rows={}; used=set()
    for task,row in frozen['rows'].items():
        outcomes={}
        for arm in BACKENDS:
            key=row['pages'].get(arm)
            if key is None:
                outcomes[arm]=False if arm in frozen['available_backends'] and row['received'] else None
                continue
            assert digest(source_files(EVAL/'pages'/key))==key
            job=f'{task}-{key}'; used.add(job)
            path=ROOT/stage['reports'][job]
            assert path.name=='report.json' and path.parent.name==job
            outcomes[arm]=score_entry(path.parent,task)['passed']
        rows[task]={**row,'passed':outcomes}
    assert used==set(stage['reports'])
    totals={arm:{'observed':sum(r['passed'][arm] is not None for r in rows.values()),
                 'passed':sum(r['passed'][arm] is True for r in rows.values()),
                 'gained_vs_original':[t for t,r in rows.items() if r['passed'][arm] is True and r['passed']['original'] is False],
                 'lost_vs_original':[t for t,r in rows.items() if r['passed'][arm] is False and r['passed']['original'] is True]}
            for arm in frozen['available_backends']}
    return {'project':'table','model':frozen['model'],'model_revision':frozen['revision'],'planned':len(rows),'received':sum(r['received'] for r in rows.values()),
            'strictly_valid':sum(r['valid'] for r in rows.values()),'distinct_valid_plans':len({digest(r['plan']) for r in rows.values() if r['valid']}),
            'new_planning':'One independent, source-blind local greedy response per public target prefix, shared across every compatible backend.',
            'totals':totals,'targets':rows,'fixed_control_report':'compatible-library-rebuild-20261123.json#fixed_documentation_example_1',
            'score_manifest_sha256':sha(EVAL/'scored.json'),'candidate_seal_sha256':stage['sealed_sha256'],'remote_planning_calls':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['freeze','score','report','check'])
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    if args.action=='check' and not (EVAL/'sealed.json').exists():
        raise SystemExit('Missing candidate seal.')
    frozen=freeze()
    if args.action=='score':
        score(frozen,args.workers)
    if args.action in ('report','check'):
        out=report(frozen)
        if args.action=='report' and not RESULT.exists():
            dump(RESULT,out)
        else:
            assert read(RESULT)==out
        print(out['strictly_valid'],{k:r['passed'] for k,r in out['totals'].items()})
