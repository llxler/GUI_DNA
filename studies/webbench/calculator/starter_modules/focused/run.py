"""Present one calculator behavior as a JavaScript-only task with the actual starter ABI."""
import argparse
import json
import re
from pathlib import Path
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from .. import run as parent

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/calculator-function-prompts-20261126'
CAP=.75
ORIGINAL=core.messages
REQUIREMENTS={'powers':(1,2,3),'trigonometry':(4,5,6,14),'layout':(7,12,13),
              'theme':(8,9,10),'mode':(11,12),'memory':(15,16,18,19),'history':(17,20)}


def register():
    f=OUT/'registration.json'
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(parent.__file__),parent.HERE/'probe.js',parent.HERE/'result.json',parent.OUT/'registration.json',parent.original.OUT/'public.json']
    # parent.HERE and parent.OUT are rebound during execution only.
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        bal=check_credits(CAP)
        assert bal['sufficient']
        core.save(f,dict(utc=now(),sources=hashes,balance=bal,cap=CAP,model=parent.TAG,deadline=parent.api.END.isoformat()))
    assert read(f)['sources']==hashes
    return read(f)


def messages(instruction,data):
    if not instruction.startswith('Extend exactly the supplied browser calculator'):
        return ORIGINAL(instruction,data)
    role=data['role']
    name=next(k for k,v in parent.RULES.items() if v==role)
    starter=data['starter']['index.html']
    script=re.search(r'<script>(.*?)</script>',starter,re.S)[1].strip()
    records=data['public_requirements']
    details='\n'.join(records[i-1]['description'] for i in REQUIREMENTS[name])
    suffix=('The host calls your function exactly once with the live document. The starter script below has already executed. '
            'Use its existing displayValue and calculate, preserve basic + and =. Insert scientific keys as ordinary buttons when appropriate. '
            'Begin with function installFeature(root) { and finish with its closing }. Return only that function. It is a JS module fragment, no HTML document or markdown.')
    text='Implement just this action: '+role+'\nPublic behavior:\n'+details+'\nAvailable elements: .calculator, .buttons, input#display and existing four-operation keys.\nAlready running script:\n'+script+'\n'+suffix
    return [dict(role='system',content='You write individual JavaScript functions for an existing application.'),dict(role='user',content=text)]


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('generate','score'))
    phase=p.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):
        reg=register()
        with patch.multiple(parent,OUT=OUT,CAP=CAP,register=lambda:reg),patch.object(core,'messages',messages):
            if phase=='generate':parent.main(phase)
            else:
                # Keep the frozen public probe under its original location; redirect only the final result.
                save=core.save
                def write(path,value):
                    if path==parent.HERE/'result.json':path=HERE/'result.json'
                    save(path,value)
                with patch.object(core,'save',write):parent.main(phase)
