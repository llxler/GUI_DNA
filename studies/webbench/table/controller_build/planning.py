"""Generate isolated messages for two independently designed table interfaces."""
import argparse
import json
from pathlib import Path

from studies.study_io import ROOT, dump, now, read, sha
from studies.table_library_sources import core
from studies.svg_chart_compact_local import local_planner

OUT = ROOT / 'artifacts/public-controller-table-20261123'
SYSTEM = ('Select a valid configuration for the requested behaviors. Return only one JSON object '
          'matching the closed plan_schema. Use the keys directly at the root, with no wrapper, '
          'code, tools or explanation.')


def prepare():
    seal = read(OUT/'sealed.json')
    for name in ('rep-1','rep-2'):
        folder=OUT/name
        status=read(folder/'status.json')
        if status['status']!='accepted':
            continue
        package=read(folder/'package.json')
        assert sha(folder/'package.json')==status['package_sha256']
        plan_folder=folder/'planning'
        hashes={}
        for n in range(1,21):
            brief={'requirements':core.requirements('table')[:n+1], 'starter':core.starter(),
                   'plan_schema':package['plan_schema'],'documentation':package['plan_documentation'],
                   'examples':package['examples']}
            messages=[{'role':'system','content':SYSTEM}, {'role':'user','content':json.dumps(brief,ensure_ascii=False)}]
            dest=plan_folder/'prompts'/f'task-{n}.json'
            if dest.exists():
                assert read(dest)==messages
            else:
                dump(dest,messages)
            hashes[dest.name]=sha(dest)
        registration={'parent_seal_sha256':sha(OUT/'sealed.json'),'package_sha256':sha(folder/'package.json'),
                      'source_sha256':sha(Path(__file__)),'worker_sha256':sha(Path(local_planner.__file__)),
                      'model':local_planner.MODEL,'model_revision':local_planner.REVISION,
                      'generation_config':local_planner.GENERATION,'prompt_sha256':hashes}
        mark=plan_folder/'registered.json'
        if mark.exists():
            assert read(mark)['inputs']==registration
        else:
            dump(mark,{'utc':now(),'inputs':registration})


if __name__=='__main__':
    prepare()
