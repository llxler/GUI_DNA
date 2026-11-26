"""Isolate each public trajectory when candidate code grows its own state indefinitely."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from studies.browser_worker import reentrant_slots
from studies.public_library_transfer import browser, core
from studies.study_io import now, read, sha
from . import run, todo


def features(functions,enabled,spec):
    source=todo.MOD.assemble(functions,enabled)
    known=todo.CONTRACT.feedback.evaluate_public(source,list(spec['spec']))
    original=(todo.HERE/'sequences.cjs').read_text()
    lines=original.splitlines(keepends=True)
    common=''.join(line for line in lines if not line.startswith("scenario('") and 'process.stdout.write' not in line)
    # This runs only after an assertion throws. Keep the measured failure but bound its diagnostic snapshot.
    common=common.replace('try{state=JSON.parse', 'try{if((scope.s?.todos?.length??0)>50)throw Error("State exceeded 50 items");state=JSON.parse')
    folder=run.OUT/'public-workers'
    folder.mkdir(parents=True,exist_ok=True)
    for line in lines:
        match=re.match(r"scenario\('([^']+)',(\[[^\]]+\])",line)
        if not match:continue
        name,owners=match[1],ast.literal_eval(match[2])
        script=folder/(name+'.cjs')
        if not script.exists():script.write_text(common+line+'process.stdout.write(JSON.stringify(tests));')
        key=hashlib.sha256(source.encode()).hexdigest()
        path=folder/'observations'/key/(name+'.json')
        if not path.exists():
            try:
                proc=subprocess.run(['node','--max-old-space-size=220',str(script)],input=json.dumps({'source':source}),
                                    capture_output=True,text=True,timeout=7,check=True)
                result=json.loads(proc.stdout)[name]
            except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as exc:
                result=dict(passed=False,owners=owners,error='Public event handler exceeded the isolated worker resources',
                            worker_status=type(exc).__name__)
            core.save(path,result)
        known['flow-'+name]=read(path)
    return known


def main():
    run.register()
    stamp=run.OUT/'isolated-public-worker.json'
    if not stamp.exists():core.save(stamp,dict(utc=now(),registration=sha(run.REG),worker=sha(__file__),
        reason='The original Ministral routing function appends to the array it iterates, exhausting the public tester.',
        handling='Run each identical public scenario in its own child. Cap diagnostic state after a failure, keep every frozen assertion and retain prior receipts.'))
    original=todo.BASE.request
    def request(ledger,case,root,messages,stage,max_tokens):
        receipt=root/'transmission-1/request.json'
        if case==('todomvc','ministral3','a') and receipt.exists() and read(receipt)['body']['messages']!=messages:
            root=run.OUT/'isolated-prompts'/root.relative_to(run.OUT)
        return original(ledger,case,root,messages,stage,max_tokens)
    with browser.lock(run.OUT/'run.lock'),patch.object(browser,'browser_slot',reentrant_slots(browser.browser_slot)):
        with patch.object(todo,'features',features),patch.object(todo.BASE,'request',request):
            run.generate()
        run.score()


if __name__=='__main__':main()
