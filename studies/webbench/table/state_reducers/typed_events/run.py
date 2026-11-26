"""Confirm a fully specified event interface with two fresh builders."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as reducers
from ...interaction_modules.state_contract import resume

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/table-typed-events-20261126pm'
CAP = .75
prior = reducers.prior
transport = prior.BASE

EXAMPLES = {
    'click': {'kind':'click','cell':[1,2]}, 'context': {'kind':'context','cell':[1,2]},
    'dismiss': {'kind':'dismiss','cell':None},
    'item': {'kind':'item','cell':[1,2],'label':'Insert Row Below'},
    'key': {'kind':'key','cell':None,'key':'ArrowRight','mod':False,'shift':False},
    'double': {'kind':'double','cell':[1,1]},
    'drag': {'kind':'drag','cell':[2,2],'start':{'cell':[1,1],'right':30,'bottom':15,'width':80,'height':40},'dx':40,'dy':20},
}

def observe(candidate):
    with browser.browser_slot():
        cmd=[sys.executable,'-m',resume.__name__,'reserved','studies.webbench.table.interaction_modules.probe']
        try:
            proc=subprocess.run(cmd,input=json.dumps(candidate),text=True,capture_output=True,check=True,timeout=32)
            return json.loads(proc.stdout)
        except subprocess.TimeoutExpired:
            return dict(checks={},errors=['Public probe exceeded 32 seconds after browser admission'])

class Provider:
    OUT, END, template = transport.OUT, transport.END, transport.template
    uncode = staticmethod(transport.uncode)

    @staticmethod
    def request(ledger, case, dest, messages, stage, limit):
        if stage=='build':
            group=dest.parents[1].name
            events=reducers.GROUPS[group][1]
            sample=(reducers.HERE/'units.cjs').read_text()
            example=sample.split("case '"+group+"':",1)[1].split('break;',1)[0]
            extra=dict(event_examples=[EXAMPLES[k] for k in events],
                       types='For cell, active and anchor use pairs such as [1,2]. Access cell[0] and cell[1]. Null cell is normal for key and dismiss. mod and shift are booleans. event.kind identifies the type. state.target keeps the latest context cell. Guard nulls. Menu labels match the public brief exactly.',
                       public_unit_examples=example,
                       example_helpers='click(r,c) supplies kind click and cell [r,c]; key(k,x) supplies kind key and key k, optional flags x; item(label,r,c) supplies kind item with label and cell [r,c]. Equivalence means same JSON value.')
            messages=[messages[0],{**messages[1],'content':messages[1]['content']+'\nPUBLIC INTERFACE EXAMPLES\n'+json.dumps(extra)},*messages[2:]]
        return transport.request(ledger,case,dest,messages,stage,limit)

def register():
    dest=OUT/'registration.json'
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(reducers.__file__),reducers.HERE/'host.js',reducers.HERE/'units.cjs',
           Path(resume.__file__),prior.HERE/'probe.py',prior.PUBLIC,prior.HERE/'result.json']
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not dest.exists():
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(dest,dict(utc=now(),deadline=prior.END.isoformat(),balance=balance,cap=CAP,
                            sources=sums,seeds=[2026112641,2026112642]))
    assert read(dest)['sources']==sums

def run():
    def template(_,tag,phase):return prior.old.settings('table',tag,phase)|{'seed':2026112641}
    with patch.multiple(transport,OUT=OUT,END=prior.END,template=template),patch.multiple(prior,BASE=Provider,observe=observe),patch.multiple(reducers,OUT=OUT,CAP=CAP,register=register):
        reducers.generate()
        with patch.object(reducers,'HERE',HERE):reducers.score()

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):run()
