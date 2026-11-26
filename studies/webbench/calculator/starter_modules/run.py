"""Build calculator behaviors as independently verified additions to the official starter."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import json
import re
from unittest.mock import patch
from urllib.parse import urlsplit

from playwright.sync_api import Error,sync_playwright
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from studies.webbench.file_explorer.document_library import run as receiver
from ..key_groups import run as original

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/calculator-starter-modules-20261126'
CAP=.85
TAG='qwen9'
RULES={'powers':'Add square root, square and reciprocal; update the same arithmetic display and value.',
       'trigonometry':'Implement pi and the public trigonometric and hyperbolic keys, with the required order.',
       'layout':'Set the clear button width and match the display to the button panel.',
       'theme':'Implement the public toggle button, placement, and initial/reversible theme.',
       'mode':'Implement the reversible mode control and its specified visible buttons.',
       'memory':'Implement memory buttons, recall and the memory panel with shared memory state.',
       'history':'Implement click history and clickable history items.'}
REPS=('a','b')
api=original.action


def register():
    files=[HERE/'PROTOCOL.md',HERE/'probe.js',Path(__file__),Path(receiver.__file__),original.OUT/'registration.json',original.OUT/'seal.json']
    files.extend(original.OUT/TAG/'build'/r/'library.json' for r in REPS)
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    f=OUT/'registration.json'
    if not f.exists():
        bal=check_credits(CAP)
        assert bal['sufficient']
        core.save(f,dict(sources=sums,utc=now(),balance=bal,cap=CAP,model=api.settings('table',TAG,'plan')['model'],deadline=api.END.isoformat()))
    assert read(f)['sources']==sums
    return read(f)


def emit(pub,components,dest):
    scripts=[]
    for fragment in components.values():
        scripts.extend(['<style>'+fragment['style']+'</style>','<script>\n{\n'+fragment['script']+'\n}\n</script>'])
    html=pub['starter']['index.html']
    assert html.count('</body>')==1
    return original.files.emit(dest,core.emit('calculator',{'index.html':html.replace('</body>','\n'.join(scripts)+'</body>')},dest))


def probes(candidate,names):
    dest=ROOT/candidate['page']
    states,errors={},[]
    with browser.serve('calculator',dest) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        tab=engine.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        tab.on('pageerror',lambda exc:errors.append(str(exc)[:140]))
        script=(HERE/'probe.js').read_text()
        for name in names:
            try:
                tab.goto(url,wait_until='load',timeout=9500)
                states[name]=tab.evaluate(script,name) is True
            except Error as exc:
                states[name]=False
                errors.append(str(exc).splitlines()[0][:140])
    return dict(checks=states,errors=sorted(set(errors)))


def prepare(rep,pub,ledger):
    folder=OUT/rep
    f=folder/'library.json'
    if f.exists():return read(f)
    components={}
    baseline=probes(emit(pub,{},folder/'public/starter'),('base',*RULES))
    assert baseline['checks']['base']
    history={}
    prev=baseline
    for name,role in RULES.items():
        history[name]=[]
        msg=core.messages('Extend exactly the supplied browser calculator with one complete ordinary function installFeature(root). It is invoked after the original starter script with root=document. Read the real calculate(value), displayValue, DOM and existing onclick handlers. Preserve those existing actions. Implement the assigned feature using real browser behavior. Do not return HTML, imports, extra files or a new page. No test code or sample-specific logic.',dict(role=role,starter=pub['starter'],public_requirements=pub['requirements'],previously_installed=list(components)))
        for attempt in range(2):
            try:
                raw=api.compact.base.request(ledger,('table',TAG,rep),folder/'calls'/name/str(attempt),msg,'build',5200)
                fragment=receiver.installer(raw)
                trial={**components,name:fragment}
                after=probes(emit(pub,trial,folder/'public'/name/str(attempt)),('base',*RULES))
                gain={k for k,v in after['checks'].items() if v}
                before={k for k,v in prev['checks'].items() if v}
                keep=name in gain-before and before<=gain and not after['errors']
                history[name].append(dict(observed=after,retained=keep))
                if keep:
                    components,prev=trial,after
                    break
                feedback=after
            except api.typed.MISSING as exc:
                history[name].append(dict(reason=str(exc)))
                break
            except ValueError as exc:
                feedback=str(exc)
                history[name].append(dict(reason=feedback))
            msg=msg+[dict(role='assistant',content=raw),dict(role='user',content='Correct only the installer using its public behavior: '+json.dumps(feedback,ensure_ascii=False))]
    status='valid' if {'powers','trigonometry','memory'}&components.keys() else 'build_failed'
    core.save(f,dict(status=status,source=components,baseline=baseline,final=prev,history=history))
    return read(f)


def main(phase):
    reg=register()
    pub=read(original.OUT/'public.json')
    f=OUT/'seal.json'
    if phase=='generate':
        if f.exists():return
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        rows=[]
        with patch.multiple(api.compact.base,OUT=OUT,END=api.END,template=api.settings),ThreadPoolExecutor(max_workers=3) as pool:
            libs=dict(zip(REPS,pool.map(lambda r:prepare(r,pub,ledger),REPS),strict=True))
            for rep,lib in libs.items():
                if lib['status']!='valid':continue
                fixed=emit(pub,lib['source'],OUT/rep/'fixed')
                host=emit(pub,{},OUT/rep/'starter')
                def plan(n):
                    dest=OUT/rep/'plans'/str(n)
                    msg=core.messages('Choose the calculator extensions needed for the current requirement. The original starter supplies basic arithmetic. Return only a JSON array of exact option names.',dict(public=core.prefix(pub,n),options={k:RULES[k] for k in lib['source']}))
                    try:
                        raw=api.compact.base.request(ledger,('table',TAG,rep),dest/'call',msg,'plan',1400)
                        selected=json.loads(api.compact.base.uncode(raw))
                        if not isinstance(selected,list) or any(not isinstance(k,str) or k not in lib['source'] for k in selected):
                            raise ValueError('Expected only registered extensions')
                        return emit(pub,{k:src for k,src in lib['source'].items() if k in selected},dest/'page')
                    except api.typed.MISSING as exc:return dict(status='missing',reason=str(exc))
                    except original.base.ERRORS as exc:return dict(status='invalid',reason=str(exc)[:180])
                for n,candidate in enumerate(pool.map(plan,range(1,21)),1):
                    for arm,value in [('planned',candidate),('fixed',fixed),('starter',host)]:
                        rows.append(dict(project='calculator',task=n,rep=rep,arm=arm,**value))
        core.save(f,dict(registration=sha(OUT/'registration.json'),rows=rows,libraries={r:sha(OUT/r/'library.json') for r in REPS}))
        return
    seal=read(f)
    assert seal['registration']==sha(OUT/'registration.json') and all(sha(OUT/r/'library.json')==v for r,v in seal['libraries'].items())
    harness=browser.verify_contract('calculator')
    assert harness==read(original.OUT/'registration.json')['harness']
    graded=browser.evaluate(seal['rows'],OUT,{'calculator':harness},3)
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(f),cost=ledger_read.totals(OUT/'budget.sqlite3'),
        libraries={r:{'status':read(OUT/r/'library.json')['status'],'options':list(read(OUT/r/'library.json')['source']),
                      'public':read(OUT/r/'library.json')['final']} for r in REPS},
        rows=[dict(task=r['task'],arm=r['arm'],rep=r['rep'],status=r['status'],passed=False if r['status']=='invalid' else r['passed'],report_sha256=r.get('report_sha256')) for r in graded]))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('generate','score'))
    phase=p.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):main(phase)
