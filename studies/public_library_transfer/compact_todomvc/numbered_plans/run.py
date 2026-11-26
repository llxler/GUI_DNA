"""Interpret an unambiguous integer label without requesting a new model response."""
from copy import deepcopy
from pathlib import Path
import re
from unittest.mock import patch

from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from ..syntax_reception import run as reception

contract=reception.contract
weak=contract.events.weak
HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/todo-numbered-plans-20261126'


def number(raw,maximum):
    raw=contract.events.base.uncode(raw).strip().lower().strip('* `')
    found=re.fullmatch(r'(?:(?:(?:the|my|selected|chosen|correct|best|requested|final|i choose|i select)\s+)*'
        r'(?:answer|configuration|profile|index|choice|option)(?:\s+(?:is|number|configuration|index|option))*\s*[:=#-]?\s*)?'
        r'(\d+)\s*[.!]?',raw)
    if found and int(found[1])<maximum:return int(found[1])
    return None


def main():
    sources={t:(reception.OUT if t==reception.TAG else contract.OUT) for t in contract.TAGS}
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(contract.__file__),reception.HERE/'result.json',contract.HERE/'result.json']
    for tag,root in sources.items():
        files.extend([root/tag/'seal.json',*(root/tag/r/'library.json' for r in ('a','b'))])
        files.extend((root/tag).glob('*/todo-*/call/transmission-*/settled.json'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    reg=OUT/'registration.json'
    if not reg.exists():core.save(reg,dict(utc=now(),sources=hashes,new_calls=0))
    assert read(reg)['sources']==hashes
    changed={}
    for tag,root in sources.items():
        seal=read(root/tag/'seal.json')
        rows=deepcopy(seal['rows'])
        changed[tag]=[]
        for rep in ('a','b'):
            lib=read(root/tag/rep/'library.json')
            if lib['status']!='valid':continue
            names=list(lib['options'])
            profiles=list(dict.fromkeys([tuple(names),(),*((n,) for n in names),*(tuple(n for n in names if n!=k) for k in names)]))
            for task,arms in rows.items():
                if arms[rep]['status']!='invalid':continue
                raw,path=reception.delivered([root/tag/rep/task/'call'])
                idx=number(raw,len(profiles))
                if idx is None:continue
                config={k:k not in names or k in profiles[idx] for k in contract.modules.OPTIONS}
                dest=OUT/tag/rep/task/'files.json'
                core.save(dest,{'candidate.js':contract.modules.assemble(lib['functions'],config)})
                arms[rep]=dict(status='valid',file=str(dest.relative_to(ROOT)),files_sha256=sha(dest))
                changed[tag].append(dict(task=task,rep=rep,index=idx,response_sha256=sha(path)))
        core.save(OUT/tag/'seal.json',dict(rows=rows,libraries=seal['libraries'],registration=sha(reg)))
    with patch.multiple(weak,OUT=OUT,MODELS={t:weak.SMALL[t] for t in sources}):weak.score()
    core.save(HERE/'result.json',dict(registration=sha(reg),changed=changed,new_calls=0,
             models={weak.SMALL[t]:read(OUT/t/'result.json') for t in sources}))


if __name__=='__main__':
    with browser.lock(OUT/'.lock'):main()
