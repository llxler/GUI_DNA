"""Prespecified deterministic merging; no access to targets' hidden trajectories."""
from copy import deepcopy
from itertools import combinations
import json
from .core import ROOT,BUILD,PROJECTS,BUILDERS,CONDITIONS,dump,digest,slug,compile_plan,write_files

OUT=ROOT/'artifacts/interaction-transfer-controls-20261115'


def merge(first,second):
    if type(first) is not type(second):raise ValueError('Conflicting types')
    if isinstance(first,dict):
        result=deepcopy(first)
        for key,value in second.items():
            result[key]=merge(result[key],value) if key in result else deepcopy(value)
        return result
    if isinstance(first,list):
        result=deepcopy(first)
        for value in second:
            if value not in result:result.append(deepcopy(value))
        return result
    if first!=second:raise ValueError('Conflicting scalar values')
    return deepcopy(first)


def prepare():
    assert not (OUT/'inputs.json').exists()
    rows=[]
    for project in PROJECTS:
        for builder in BUILDERS:
            for condition in CONDITIONS:
                library=BUILD/'libraries'/project/slug(builder)/condition
                record=json.loads((library/'record.json').read_text())
                package=json.loads((library/'package.json').read_text()) if record['status']!='failed' else None
                for size in (1,2,3):
                    for indices in combinations(range(3),size):
                        name='merge-'+'-'.join(map(str,indices))
                        row={'project':project,'builder':builder,'condition':condition,'control':name,'subset':list(indices),
                             'deployed_control':size==3,'fixed_example':size==1,'page':None,'error':None}
                        folder=OUT/'pages'/project/slug(builder)/condition/name
                        try:
                            if package is None:raise ValueError('Unavailable library')
                            plans=[next(e['plan'] for e in package['examples'] if e['id']==f'dev-{i}') for i in indices]
                            plan=deepcopy(plans[0])
                            for other in plans[1:]:plan=merge(plan,other)
                            dump(folder/'plan.json',plan)
                            files=compile_plan(package,plan)
                            write_files(folder,files)
                            import hashlib
                            dump(folder/'source-manifest.json',{'files_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()}})
                            row['page']=str(folder.relative_to(ROOT))
                        except (ValueError,KeyError,TypeError) as error:row['error']=str(error)
                        rows.append(row)
    dump(OUT/'inputs.json',{'rows':rows,'selection':'All seven nonempty development-example subsets; fixed algorithm, no hidden-score selection.'})
    print('Deterministic controls prepared',len(rows),'executable',sum(r['page'] is not None for r in rows),flush=True)


if __name__=='__main__':prepare()
