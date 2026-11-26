"""Build each renderer from its own local input contract, keeping complete helper code."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import generate as gen, pages, schema
from ..mounted_components import run as previous

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webgen-component-functions-20261126pm'
CAP=.30
KINDS={
    'page':('start',{'title':'My page','body':[{'type':'tpl','tpl':'News'}]},'Show heading and delegate body to env.mount(root,component.body). The host already owns page data.'),
    'tpl':('start',{'tpl':'Weather bulletin'},'Put the literal component.tpl into the current root as plain text using env.text.'),
    'tabs':('tabs',{'tabs':[{'title':'News','body':{'type':'tpl','tpl':'News updates'}},{'title':'Events','body':[{'type':'tpl','tpl':'New events'}]}]},'Show a button for each literal title. Select the first pane initially; clicking another should show only its body. Delegate each body to env.mount.'),
    'container':('start',{'body':{'type':'tpl','tpl':'News'}},'Mount all supplied body children.'),
    'panel':('start',{'title':'Recent','body':{'type':'tpl','tpl':'One record'}},'Show the heading and mount children inside an element.'),
    'table':('record',{'columns':[{'name':'city','label':'City'}],'source':'${cities}'},'Table data comes from env.get(component.source), an ARRAY of objects, e.g. [{city:"Perth"}]. Append real table/th/td elements with actual labels and cell values.'),
    'button':('details',{'label':'More','actionType':'dialog','dialog':{'title':'Details','body':{'type':'tpl','tpl':'Extra note'}}},'A native button displays its label. Its click handler opens a dialog by calling env.mount(root,{...component.dialog,type:"dialog"}) or displays its toast message.'),
    'dialog':('details',{'title':'Details','body':{'type':'tpl','tpl':'New message'}},'You are called when opened. Display title, mount body and supply a close button that removes this dialog.'),
    'form':('form',{'title':'Sample','body':[{'type':'input-text','name':'user'}],'actions':[{'type':'submit','label':'Send'}],'onEvent':{'submitSucc':{'actions':[{'actionType':'toast','args':{'msg':'Done'}}]}}},'Create native form, mount body AND actions into form, show title. On submit prevent default; collect named fields and display the literal success message from component.onEvent.submitSucc.actions at args.msg.'),
    'submit':('form',{'label':'Post'},'Create a native button, type submit; use component.label as its visible text. The host mounted root inside the form.'),
}
for kind in pages.GROUPS['input']:
    KINDS[kind]=('form',{'name':'user','label':'Name','required':True,'options':[{'label':'First','value':'1'}]},'Create an appropriate native control with its actual name and required/value, labeled visibly. Support all supplied options for a select.')
PROMPT="""Write JavaScript statements for ONE component, inside a function whose formal parameters are root, component and env.
Return only the function BODY as JavaScript, without markdown, imports, surrounding function or discussion.
root is a real HTMLElement, already mounted. component is the supplied data object for your single component type.
env.mount(realParent,childOrArray) appends child components and returns nothing. env.text(value) interpolates a text value.
env.get(keyOrReference) returns raw page data and accepts names or ${name}. env.data is mutable page data.
Use native DOM APIs and event listeners. You own this behavior. Do not implement any other component types.
All literal labels, texts and data come from component, never from the demonstration. No network or global helpers."""
def html(config,parts):
    funcs=','.join(json.dumps(k)+':('+fn+')' for k,fn in parts.items())
    loader=(previous.HERE/'mount.js').read_text().replace('HANDLERS','{'+funcs+'}').replace('name => data[name]',r"""name => data[String(name ?? '').replace(/^\$\{([\w.]+)\}$/,'$1')]""")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>App</title><style>'+pages.BASE_CSS+
            '</style></head><body><main id="app"></main><script>const schema='+json.dumps(config,ensure_ascii=False).replace('<',r'\u003c')+';\n'+loader+'</script></body></html>')

def body(raw):
    txt=gen.BASE.uncode(raw).strip()
    fence=re.search(r'```(?:javascript|js)?\s*\n([\s\S]*?)```',txt,re.I)
    code=(fence[1] if fence else txt).strip()
    declared=re.match(r'^(?:export\s+(?:default\s+)?)?function\s+(\w+)\s*\(([^)]*)\)',code)
    if declared and len(declared[2].split(','))==3:
        code=re.sub(r'^export\s+(?:default\s+)?','',code)
        fn='(function(){'+code+'\nreturn '+declared[1]+';})()'
    else:fn='function render(root,component,env){\n'+code+'\n}'
    completed=subprocess.run(['node','--check','-'],input='('+fn+')',capture_output=True,text=True,timeout=6)
    if completed.returncode:raise ValueError('JavaScript syntax error: '+completed.stderr[:180])
    return fn

def build(t, ledger):
    folder=OUT/'build'/t;f=folder/'library.json'
    if f.exists():return read(f)
    briefs=read(gen.OUT/'generation-input.json')
    try:
        design=gen.call(ledger,t,folder/'design',core.messages('Summarize common reusable interactions in under 100 words. Output no site-specific code.',briefs),'build',1100)
    except gen.MISSING as e:
        core.save(f,dict(status='missing',parts={},reason=str(e)));return read(f)
    def fn(kind,i,obs):
        need,ex,role=KINDS[kind]
        d=folder/'types'/kind/str(i)
        msg=core.messages(PROMPT,dict(type=kind,role=role,example_input={'type':kind,**ex},library_design=design[:700],public_feedback=obs))
        try:return body(gen.call(ledger,t,d/'call',msg,'build',2700))
        except (gen.MISSING+gen.ERRORS) as e:return ''
    def attempt(parts,where):
        rec=pages.write_html(folder/where,html(schema.SAMPLE,parts))
        return previous.check('integration',ROOT/rec['file'])
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks={k:pool.submit(fn,k,0,None) for k in KINDS}
        parts={k:src for k,job in tasks.items() if (src:=job.result())}
        orig=attempt(parts,'first')
        missed=[k for k,(need,_,_) in KINDS.items() if not orig['checks'].get(need) or k not in parts]
        updated=dict(parts);history=[]
        if missed:
            tasks={k:pool.submit(fn,k,1,{'current_function':parts.get(k),'public_observation':orig,'focus':KINDS[k][0]}) for k in missed}
            for k,job in tasks.items():
                if src:=job.result():updated[k]=src
            second=attempt(updated,'repaired')
            old={k for k,v in orig['checks'].items() if v}
            new={k for k,v in second['checks'].items() if v}
            keep=old<=new and len(updated)>=len(parts)
            history.append(dict(checks=second,retained=keep))
            if keep:parts=updated
        else:second=orig;keep=True
    observed=second if keep else orig
    valid=len(parts)==len(KINDS) and len(observed['checks'])==5 and all(observed['checks'].values())
    core.save(f,dict(status='valid' if valid else 'build_failed',parts=parts,first=orig,integration=observed,history=history,
                     delivered_types=sorted(parts),design=design))
    return read(f)

def run():
    old=previous.HERE/'candidates.json';prev=read(old);reg=OUT/'registration.json'
    files=[Path(__file__),HERE/'PROTOCOL.md',old,Path(previous.__file__),previous.HERE/'mount.js',gen.OUT/'generation-input.json',previous.OUT/'seal.json']
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not reg.exists():
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(reg,dict(utc=now(),cap=CAP,balance=balance,sources=sums,deadline=gen.END.isoformat()))
    assert read(reg)['sources']==sums
    if (HERE/'candidates.json').exists():return
    rows=prev['rows'];libs=prev['libraries'];tags=[t for t in gen.TAGS if libs[t]['status']=='build_failed']
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(gen.BASE,OUT=OUT,END=gen.END,template=gen.settings),ThreadPoolExecutor(max_workers=2) as pool:
        tasks={t:pool.submit(build,t,ledger) for t in tags}
        for t,job in tasks.items():
            lib=job.result();libs[t]={k:v for k,v in lib.items() if k!='parts'}
            for site,arms in rows[t].items():
                plan=read(previous.native.OUT/'plans'/t/site/'record.json')
                if lib['status']!='valid':v=dict(status=lib['status'])
                elif plan['status']!='valid':v={k:a for k,a in plan.items() if k!='config'}
                else:v=pages.write_html(OUT/'sites'/t/site/'self',html(plan['config'],lib['parts']))
                arms['self']=v
    core.save(OUT/'seal.json',dict(registration=sha(reg),rows=rows,libraries={t:sha(OUT/'build'/t/'library.json') for t in tags}))
    core.save(HERE/'candidates.json',dict(registration=sha(reg),seal=sha(OUT/'seal.json'),previous=sha(old),libraries=libs,rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):run()
