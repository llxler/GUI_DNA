"""Replay a single explicit JSON block symmetrically in paired and direct responses."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re

from studies.public_library_transfer import core, browser
from studies.study_io import ROOT, now, read, sha
from .. import run as parent

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/duo-json-delivery-20261125'
RESULT=HERE/'result.json'
FENCE=re.compile(r'^\s*```([^\n\r]*)\r?\n(.*?)^\s*```\s*$',re.M|re.S)
TAGS=[t for p,t in parent.ORDER if p=='duo']


def block(raw):
    blocks=FENCE.findall(raw)
    if len(blocks)!=1 or blocks[0][0].strip().lower()!='json':
        raise ValueError('Expected one explicit JSON fence')
    return json.loads(blocks[0][1])


def register():
    files=[HERE/'PROTOCOL.md',Path(__file__),parent.suite.RESULT,parent.HERE/'result.json',
           Path(parent.duo.bundle.__code__.co_filename),Path(parent.runtime.__file__)]
    files.extend(parent.OUT/'duo'/t/r/'seal.json' for t in TAGS for r in ('a','b'))
    files.extend(parent.suite.OUT/t/'seal.json' for t in TAGS)
    sources={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not (OUT/'registration.json').exists():
        core.save(OUT/'registration.json',dict(utc=now(),sources=sources,new_api_calls=0))
    assert read(OUT/'registration.json')['sources']==sources


def prepare():
    register()
    tasks,_=parent.suite.inputs()
    items=[]
    for tag in TAGS:
        for rep in ('a','b'):
            root=parent.OUT/'duo'/tag/rep
            seal=read(root/'seal.json')
            for task,row in seal['rows'].items():
                group=tasks[task]['group']
                if seal['builds'][group]['status']!='valid':
                    continue
                for arm in ('direct','self','fixed'):
                    if arm=='direct':
                        dest=parent.suite.OUT/tag/'targets'/task/'direct'
                        original=read(dest/'result.json')
                        files=dest/'files.json'
                        receipt=dest/'call/response.json'
                    else:
                        original=row[arm]
                        files=ROOT/original['file'] if original['status']=='valid' else None
                        receipt=next((p.with_name('response.json') for p in sorted((root/'targets'/task/'plan').glob('transmission-*/settled.json'))),None)
                    status=original['status']
                    item=dict(model=parent.suite.MODELS[tag][0],rep=rep,task=task,arm=arm,original_status=status,status=status)
                    if status=='valid':
                        assert sha(files)==original['files_sha256']
                        item.update(file=str(files.relative_to(ROOT)),files_sha256=sha(files))
                    elif status=='invalid' and receipt and receipt.exists():
                        item['response_sha256']=sha(receipt)
                        try:
                            val=block(read(receipt)['choices'][0]['message'].get('content') or '')
                            if arm=='direct':
                                if not isinstance(val,dict) or not isinstance(val.get('source'),str) or not val['source'].strip():
                                    raise ValueError('Expected a standalone source in the original envelope')
                                result={tasks[task]['public']['module']+'.js':val['source']}
                            else:
                                components=seal['builds'][group]['components']
                                setting=parent.duo.parse_plan(json.dumps(val),sorted(components))
                                if setting is None:raise ValueError('Invalid original component pair')
                                modules=[]
                                for k,v in sorted(components.items()):
                                    assert sha(ROOT/v['source'])==v['source_sha256']
                                    modules.append(dict(id=k,source=read(ROOT/v['source'])['source']))
                                result=parent.duo.bundle(tasks[task]['public']['module'],dict(components=modules),setting)
                        except (ValueError,KeyError,TypeError):
                            pass
                        else:
                            files=OUT/'candidates'/tag/rep/task/arm/'files.json'
                            core.save(files,result)
                            item.update(status='valid',file=str(files.relative_to(ROOT)),files_sha256=sha(files))
                    items.append(item)
    core.save(OUT/'seal.json',dict(registration_sha256=sha(OUT/'registration.json'),items=items))
    return items


def main():
    rows=prepare()
    targets,_=parent.suite.inputs()
    def score(item):
        if item['status']!='valid':
            return {**item,'passed':None if item['status']=='missing' else False}
        task=item['task']
        path=ROOT/item['file']
        assert sha(path)==item['files_sha256']
        folder=OUT/'scores'/task/item['files_sha256']
        with browser.lock(folder/'.lock'),browser.browser_slot():
            result=parent.runtime.score((targets[task]['group'],targets[task],read(path),folder,None))
        assert sha(folder/'jest.json')==result['report_sha256']
        return {**item,'passed':result['passed'],'report_sha256':result['report_sha256']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        scored=list(pool.map(score,rows))
    core.save(RESULT,dict(source_sha256=sha(parent.HERE/'result.json'),seal_sha256=sha(OUT/'seal.json'),
                          new_api_calls=0,new_api_cost=0,rows=scored))


if __name__=='__main__':
    main()
