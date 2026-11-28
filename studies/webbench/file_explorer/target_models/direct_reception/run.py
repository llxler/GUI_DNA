"""Replay all file-explorer Direct responses with the advertised file format."""
import json
from pathlib import Path
import re
import shutil

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.file_explorer.target_models import run as study

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/file-explorer-direct-reception-20261128'
TAGS = ('gemma', 'qwen9', 'oss', 'deepseek-flash')
OLD = study.docs.OUT
ORIGIN = study.original.OUT


def decode(raw):
    text = raw.strip()
    fence = re.fullmatch(r'```(?:json|html)?[ \t]*\r?\n(.*?)\r?\n?```', text, re.S | re.I)
    if fence:
        text = fence[1].strip()
    if text.startswith('{'):
        obj = json.loads(text)
        files = obj['files']
        sources = core.files_map(files) if isinstance(files, list) else study.original.blind.validate_files(files)
        if not sources:
            raise ValueError('Empty file package')
        return 'package', sources
    if re.match(r'(?:<!doctype\s+html\b|<html\b)', text, re.I):
        return 'html', {'index.html': study.docs.parse_document(text)}
    raise ValueError('Expected a JSON package or a standalone HTML document')


def prepare():
    previous = { (r['tag'],r['task']):r for source in (study.OUT/'seal.json', OLD/'controls.json')
                for r in read(source)['rows'] if r['arm']=='direct' }
    sources = [Path(__file__), HERE/'PROTOCOL.md', Path(core.__file__), Path(study.__file__),
               Path(study.docs.__file__), Path(study.docs.receipt.__file__), ORIGIN/'public.json',
               study.OUT/'seal.json', OLD/'controls.json', ORIGIN/'browser.json']
    checks = {}
    replies = {}
    for tag in TAGS:
        for n in range(1,21):
            folder = (study.OUT/tag/'targets'/str(n)/'direct' if tag in study.TAGS
                      else ORIGIN/tag/'deploy/direct'/str(n))
            raw, receipt = study.docs.receipt.delivered([folder/'call'])
            replies[tag,n] = raw, receipt
            checks[str(receipt.relative_to(ROOT))] = sha(receipt)
    reg = OUT/'registration.json'
    inputs = {str(p.relative_to(ROOT)):sha(p) for p in sources}
    if not reg.exists():
        core.save(reg, dict(utc=now(), sources=inputs, delivered=checks, paid_calls=0,
                           models={tag:study.original.action.settings('table',tag,'plan')['model'] for tag in TAGS}))
    assert read(reg)['sources']==inputs and read(reg)['delivered']==checks
    if (OUT/'seal.json').exists():
        return
    starter = read(ORIGIN/'public.json')['starter']
    rows = []
    for (tag,n),(raw,receipt) in replies.items():
        old = previous[tag,n]
        dest = OUT/tag/str(n)/'page'
        try:
            format_name, files = decode(raw)
            record = study.original.emit(dest,core.emit('dom1',starter|files,dest))
        except (ValueError, TypeError, KeyError) as exc:
            format_name,record = 'invalid',dict(status='invalid',reason=str(exc)[:200])
        rows.append(dict(project='dom1',tag=tag,task=n,arm='direct',format=format_name,
                         original_status=old['status'],original_digest=browser.digest(old['files']) if old['status']=='valid' else None,
                         response=checks[str(receipt.relative_to(ROOT))],**record))
    core.save(OUT/'seal.json',dict(registration=sha(reg),rows=rows))


def score():
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json')
    contract=browser.verify_contract('dom1')
    assert contract==read(ORIGIN/'browser.json')
    for r in seal['rows']:
        if r['status']!='valid':
            continue
        checksum=browser.digest(r['files'])
        rel=Path('browser/scores/dom1')/f'task-{r["task"]}'/checksum/'score.json'
        target=OUT/rel
        if target.is_file():
            continue
        for peer in (OLD,ORIGIN,study.OUT):
            old=peer/rel
            if not old.is_file():
                continue
            v=browser.verify_receipt(peer,old,dict(project='dom1',task=r['task'],files_digest=checksum,contract_digest=browser.digest(contract)))
            copy=target.with_name('reused-report.json')
            copy.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(peer/v['report'],copy)
            core.save(target,dict(v,report=str(copy.relative_to(OUT)),source_receipt=str(old.relative_to(ROOT)),
                                  source_receipt_sha256=sha(old),source_report=str((peer/v['report']).relative_to(ROOT))))
            break
    verdicts=browser.evaluate(seal['rows'],OUT,{'dom1':contract},3)
    reg=read(OUT/'registration.json')
    by_model={}
    for tag,model in reg['models'].items():
        rows=[]
        for v in verdicts:
            if v['tag']!=tag:
                continue
            rows.append({k:v[k] for k in ('task','arm','format','status','original_status','original_digest','response','report_sha256')}
                        |dict(files_digest=browser.digest(v['files']) if v['status']=='valid' else None,
                              passed=False if v['status']=='invalid' else v['passed']))
        by_model[model]=rows
    core.save(HERE/'result.json',dict(registration=seal['registration'],seal=sha(OUT/'seal.json'),paid_calls=0,models=by_model))


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        prepare()
        if not (HERE/'result.json').exists():
            score()
