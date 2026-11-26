"""Give the Qwen generator the same semantic plan interface across library sources."""
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import time
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.typed_components import run as typed
from .. import run as survey
from ..module_links import run as links
from studies.webgen_bench.functional_pilot.function_binding import run as websites

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/form-qwen-source-comparison-20261126pm'
ARCHIVE=typed.OUT/'form/qwen9/build-a/fixed/20/page'
CAP=.65
END=datetime(2026,11,26,13,55,tzinfo=timezone.utc)
REG=OUT/'registration.json'

def register():
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(survey.__file__),Path(links.__file__),links.HERE/'link.cjs',survey.form.COMPILER,
           typed.HERE/'result.json',*(survey.BASE/name for name in ('public.json','browser.json','gpt5-library.json','human.json')),
           *(p for p in ARCHIVE.rglob('*') if p.is_file())]
    sums={str(f.relative_to(ROOT)):sha(f) for f in files}
    if not REG.exists():
        b=check_credits(CAP);assert b['sufficient']
        core.save(REG,dict(utc=now(),deadline=END.isoformat(),models={'qwen9':survey.action.settings('table','qwen9','plan')['model']},
                           cap=CAP,balance=b,sources=sums,targets=list(range(1,21))))
    assert read(REG)['sources']==sums
    return read(REG)

def prepare(tag,rep,pub,ledger):
    folder=OUT/tag/rep;dest=folder/'library.json'
    if dest.exists():return read(dest)
    initial=OUT/'initial-source'/tag/'original/library.json'
    if not initial.exists():
        files={p.relative_to(ARCHIVE).as_posix():p.read_text() for p in ARCHIVE.rglob('*') if p.is_file() and not p.is_relative_to(ARCHIVE/'assets') and p.name!='index.js'}
        pkg=dict(files=files,compiler=survey.form.COMPILER.read_text())
        core.save(initial,dict(package=pkg))
    raw=read(initial)['package']
    before=survey.public(raw,False,folder/'public/initial')
    if rep=='original':
        result=dict(package=raw,before=before,after=before,repairs=[])
    else:
        with patch.multiple(links,OUT=OUT/'linked',PARENT=OUT/'initial-source'):
            patchlib=links.prepare(tag,'original')
        pkg=patchlib['package'];checks=patchlib['after'];history=[];used=set()
        for i in range(3):
            if all(checks['checks'].values()) and not checks['errors']:break
            names={Path(k).stem:k for k in pkg['files'] if k.startswith('common/') and k.endswith('.js')}
            stack=str(checks['errors'])
            from_stack=[n for n in names if n+'.js' in stack]
            options=from_stack+(['SingleSelectionQuestion'] if not checks['checks']['radio'] else [])+(['OpenQuestion'] if not checks['checks']['text'] else [])+['Survey','Contents','Question']
            name=next((n for n in options if n in names and n not in used),None)
            if not name:break
            used.add(name);key=names[name]
            msg=core.messages('Repair one complete JavaScript ES module in your own questionnaire library. Keep the same named exports, public constructors, and existing working behavior. Output the full module alone.',
                              dict(module=key,current=pkg['files'][key],available_modules=list(names.values()),
                                   public_example=survey.EXAMPLE,public_observation=checks,requirements=pub['requirements']))
            try:
                raw_reply=survey.action.compact.base.request(ledger,('table',tag,'a'),folder/'repairs'/name,msg,'build',5000)
                src=survey.action.build.modules.js_block(raw_reply);survey.form.syntax({key:src})
                new={**pkg,'files':pkg['files']|{key:src}};after=survey.public(new,False,folder/'public'/str(i))
                prev={k for k,v in checks['checks'].items() if v};cur={k for k,v in after['checks'].items() if v}
                keep=prev<cur and len(after['errors'])<=len(checks['errors'])
                history.append(dict(module=key,after=after,retained=keep))
                if keep:pkg,checks=new,after
            except (ValueError,*survey.action.typed.MISSING) as exc:history.append(dict(module=key,error=str(exc)))
        result=dict(package=pkg,before=before,after=checks,repairs=history,links=patchlib['edits'])
    core.save(dest,result);return read(dest)

def run():
    register()
    with patch.multiple(survey,OUT=OUT,HERE=HERE,TAGS=('qwen9',),FROZEN={'qwen9':{'a':ARCHIVE,'original':ARCHIVE}},
                        CAP=CAP,register=register,prepare=prepare),patch.object(survey.action,'END',END):
        survey.main('generate')
        survey.main('score')

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        while not (websites.HERE/'judgments.json').exists() or not (ROOT/'studies/webbench/table/selection_binding/interaction_repairs/result.json').exists():
            if datetime.now(timezone.utc)>=END:raise RuntimeError('Primary batch incomplete at deadline')
            time.sleep(6)
        run()
