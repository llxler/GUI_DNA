"""Reconstruct classifications, with optional independent VM reexecution."""
from collections import Counter,defaultdict
from .run import ROOT,OUT,read,dump,sha,digest,parse_json,probe,classify,cases
from test.replay_hashes import verify_report_hash


def reconstruct(reexecute=False):
    complete=read(OUT/'complete.json')
    verify_report_hash(OUT/'inputs.json',complete['inputs_sha256'])
    verify_report_hash(OUT/'classified.json',complete['classified_sha256'])
    inputs=read(OUT/'inputs.json')['rows'];assert inputs==cases()
    rows=read(OUT/'classified.json')['rows'];assert [{k:v for k,v in r.items() if k not in ('classification','observation_key')} for r in rows]==inputs
    repeated=set();groups=defaultdict(Counter)
    for row in rows:
        key=row['observation_key'];observation=read(OUT/'observations'/f'{key}.json') if key else {}
        if reexecute and key and key not in repeated:
            parsed=parse_json(read(ROOT/row['output'])['text']);package=read(ROOT/row['package'])
            observed=probe(package,parsed['program']) if 'program' in parsed else {'kind':'files'}
            assert observed==observation,'Instrumented VM reexecution changed';repeated.add(key)
        assert classify(row,observation)==row['classification']
        groups[row['cohort']+'/'+row['label']][row['classification']]+=1
    return {'cases':len(rows),'distinct_observations':complete['observations'],'groups':{k:dict(v) for k,v in sorted(groups.items())},
        'rows':rows,'scope':'Posthoc execution-path audit, no new model or browser scores. Exact reuse requires unchanged compiler input files, schema-valid data, complete output matching a captured compiler return and the original saved source. Files-form runtime reuse remains unclassified; no full-library upper bound or causal claim.'}


if __name__=='__main__':
    result=reconstruct(True);dump(ROOT/'test/results/compiler-reuse-audit.json',result);print(result['groups'])
