"""Continue a verified original design with deterministic Unicode punctuation normalization."""
import argparse
from pathlib import Path
import unicodedata

from studies.public_library_transfer import core
from studies.public_library_transfer.self_refinement import run as base
from studies.public_library_transfer.self_refinement.line_contract import run as lines
from studies.study_io import ROOT, read, sha

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/self-normalized-table-20261124'
PARENT=ROOT/'artifacts/self-line-contract-20261124'
MODELS={k:(model,.40,pin,pout) for k,(model,_,pin,pout) in lines.MODELS.items()}
END=lines.END
ORIGINAL_REQUEST=base.transport.request

def configure(root,source,project,models,end):
    global OUT,PARENT,MODELS,END
    OUT,PARENT=Path(root).resolve(),Path(source).resolve()
    MODELS,END=models,end
    lines.configure(OUT,project,models,end)
    base.build=build
    base.transport.request=request

def register():
    paths=[HERE/'PROTOCOL.md',Path(__file__),PARENT/'registered.json']
    source=read(PARENT/'registered.json')
    for key,model in MODELS.items():
        assert source['models'][key][0]==model[0]
        design=PARENT/key/'build/design'
        for filename in ('request.json','response.json','settled.json','error.json'):
            if (design/filename).exists(): paths.append(design/filename)
    core.save(OUT/'transfer-protocol.json',{'stage':'normalized-first-design','project':lines.PROJECT,
        'source_root':str(PARENT.relative_to(ROOT)),'unicode_version':unicodedata.unidata_version,
        'files':{str(p.relative_to(ROOT)):sha(p) for p in paths}})
    lines.register()
    assert sha(OUT/'public.json')==sha(PARENT/'public.json') and sha(OUT/'browser.json')==sha(PARENT/'browser.json')

def first_text(tag):
    lineage=read(OUT/'transfer-protocol.json')
    for name,fingerprint in lineage['files'].items():
        if sha(ROOT/name)!=fingerprint: raise ValueError('A checked first-answer input changed')
    source=PARENT/tag/'build/design'
    if not (source/'settled.json').exists(): raise base.transport.Unavailable('First architecture not received')
    assert read(source/'settled.json')['response_sha256']==sha(source/'response.json')
    assert read(source/'request.json')['body']['model']==MODELS[tag][0]
    assert read(source/'response.json')['choices'][0]['message']['role']=='assistant'
    content=read(source/'response.json')['choices'][0]['message']['content'] or ''
    return ''.join('-' if unicodedata.category(char)=='Pd' else char for char in content)

def request(tag,ledger,folder,messages,purpose,limit):
    if purpose=='build/'+lines.PROJECT+'/design': return first_text(tag)
    if purpose=='build/'+lines.PROJECT+'/design-repair': raise ValueError('No new architecture sampling registered')
    return ORIGINAL_REQUEST(tag,ledger,folder,messages,purpose,limit)

def build(tag,ledger,data):
    folder=OUT/tag/'build'
    if (folder/'status.json').exists(): return read(folder/'status.json')
    try: lines.decode(first_text(tag),read(OUT/'file-layout.json'))
    except base.MISSING as exc:
        state={'status':'missing','reason':str(exc),'repair_used':False,'source_status':[]}
    except base.INVALID as exc:
        state={'status':'invalid','reason':str(exc),'repair_used':False,'source_status':[]}
    else: return lines.build(tag,ledger,data)
    core.save(folder/'status.json',state)
    return state

generate=base.generate
score=base.score

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','verify','generate','score'))
    parser.add_argument('tag',nargs='?',choices=MODELS)
    args=parser.parse_args()
    configure(OUT,PARENT,'table',MODELS,END)
    if args.action=='register': return register()
    if args.action=='verify': return base.verify()
    if not args.tag: parser.error('Model tag required')
    globals()[args.action](args.tag)

if __name__=='__main__': main()
