"""Audit retained build programs without generating or grading a candidate."""
from collections import Counter,defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
from gui_dna.provider import parse_json
from test.history_replay.run import ROOT,read,dump,sha,digest,source_files,now
from test.webbench_expand.schema import validate
from test.interface_blind.core import slug

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/compiler-reuse-audit-20261116'


def stages():
    continued='matched-feedback-frontier-continue-20261116'
    frontier=continued if (ROOT/'artifacts'/continued/'continuation.json').exists() else 'matched-feedback-frontier-20261116'
    return [('original','webbench-expand-run'),('matched_oss','matched-feedback-20261116'),('matched_gpt5',frontier)]


def cases():
    result=[]
    for cohort,stage in stages():
        assert (ROOT/'artifacts'/stage/'generation-complete.json').exists()
        for path in sorted((ROOT/'artifacts'/stage/'runs').rglob('record.json')):
            record=read(path)
            if record['method']!='free_lib':continue
            assert record['status']=='complete'
            variants=[('final',record['versions'][-1] if record['versions'] else None)] if cohort=='original' else [
                ('first',record['attempts'][0]['version']),('final',record['attempts'][-1]['version'])]
            package=ROOT/'artifacts/webbench-expand-build/libraries'/record['project']/slug(record['builder'])/'package.json'
            for label,version in variants:
                result.append({'cohort':cohort,'project':record['project'],'builder':record['builder'],'model':record['model'],
                    'label':label,'record':str(path.relative_to(ROOT)),'package':str(package.relative_to(ROOT)),
                    'page':str((path.parent/version).relative_to(ROOT)) if version else None,
                    'output':str((path.parent/f'output-{version.removeprefix("version-")}.json').relative_to(ROOT)) if version else None})
    assert len(result)==276
    return result


def probe(package,program):
    done=subprocess.run(['node',str(HERE/'probe.cjs')],input=json.dumps({'package':package,'program':program}),
        capture_output=True,text=True,timeout=15)
    if done.returncode:return {'error':done.stderr[:2000]}
    return json.loads(done.stdout)


def classify(row,observation):
    if not row['page']:return 'no_executable_response'
    if observation.get('kind')=='files':return 'files_output_runtime_reuse_unclassified'
    if 'error' in observation:return 'instrumentation_error'
    if observation['output_sha256']!=source_files(ROOT/row['page']):return 'instrumentation_output_mismatch'
    package=read(ROOT/row['package'])
    original={k:hashlib.sha256(v.encode()).hexdigest() for k,v in package['files'].items()}
    outside=False
    for call in observation['calls']:
        if call['input_files_sha256']==original and call['output_sha256']==observation['output_sha256']:
            if not call['plan_data_only']:
                outside=True;continue
            try:validate(package['plan_schema'],call['plan'])
            except (ValueError,TypeError):outside=True
            else:return 'exact_legal_frozen_compile'
    return 'exact_outside_schema_compile' if outside else 'other_build_or_uncertified_reuse'


def run():
    assert not OUT.exists()
    rows=cases();paths=[HERE/'run.py',HERE/'probe.cjs',HERE/'PROTOCOL.md',HERE/'__init__.py',
        ROOT/'test/webbench_expand/schema.py',ROOT/'test/history_replay/run.py',ROOT/'test/interface_blind/core.py',
        ROOT/'src/gui_dna/provider.py']
    paths += [ROOT/'artifacts'/stage/'generation-complete.json' for _,stage in stages()]
    for row in rows:
        paths += [ROOT/row['record'],ROOT/row['package']]
        if row['output']:paths.append(ROOT/row['output'])
    dump(OUT/'inputs.json',{'rows':rows});paths.append(OUT/'inputs.json')
    dump(OUT/'snapshot.json',{'frozen_utc':now(),'sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths}})
    observations={};classified=[]
    for row in rows:
        if row['output']:
            parsed=parse_json(read(ROOT/row['output'])['text']);package=read(ROOT/row['package'])
            key=digest([row['package'],parsed])
            if key not in observations:
                observed=probe(package,parsed['program']) if isinstance(parsed,dict) and 'program' in parsed else {'kind':'files'}
                dump(OUT/'observations'/f'{key}.json',observed);observations[key]=observed
            observed=observations[key]
        else:key=None;observed={}
        classified.append({**row,'observation_key':key,'classification':classify(row,observed)})
    dump(OUT/'classified.json',{'rows':classified})
    dump(OUT/'complete.json',{'finished_utc':now(),'cases':len(rows),'observations':len(observations),
        'inputs_sha256':sha(OUT/'inputs.json'),'classified_sha256':sha(OUT/'classified.json')})
    print(Counter(r['classification'] for r in classified))


if __name__=='__main__':run()
