"""Freeze a diagnostic assertion matrix and run every BOM test serially."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
from studies import browser_jobs
from studies.study_io import ROOT, UPSTREAM, read, dump, sha, now, source_files

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/assertion-audit-20261117'
PROJECTS = ('dom1','form','calculator','table','bom','draw')
TASKS = (9,13,14,15,16,20)
OLD = 'expect(contentFrame).toBeDefined()'
NEW = 'expect(contentFrame).not.toBeNull()'


def prepare():
    assert not OUT.exists()
    entries, hashes = [], {}
    for project in PROJECTS:
        for path in sorted((UPSTREAM / 'projects' / project / 'test').rglob('*.spec.js')):
            text = path.read_text()
            lines = [{'line':i,'text':line.strip()} for i,line in enumerate(text.splitlines(),1)
                if 'toBeDefined(' in line or re.search(r'\breturn\s*;?\s*$',line)]
            entries.append({'project':project,'file':str(path.relative_to(ROOT)), 'sha256':sha(path), 'hits':lines})
            hashes[str(path.relative_to(ROOT))] = sha(path)
    dump(OUT / 'static-inventory.json', {'files':entries,'scope':'Text-pattern screening, not exhaustive control-flow proof'})
    reference = OUT / 'pages/reference'
    shutil.copytree(UPSTREAM / 'projects/bom/src', reference)
    removed = OUT / 'pages/missing-frame'
    shutil.copytree(reference, removed)
    path = removed / 'index.html'
    text = path.read_text()
    needle = '<iframe name="content" class="content"></iframe>'
    assert text.count(needle) == 1
    path.write_text(text.replace(needle,''))
    blank = OUT / 'pages/blank'
    blank.mkdir(parents=True)
    (blank / 'index.html').write_text('<!doctype html><html><body></body></html>')
    browser_jobs.OUT = OUT
    browser_jobs.prepare_harness('expansion','bom')
    original = OUT / 'harness/157-bom'
    corrected = OUT / 'harness/157-bom-nullguard'
    shutil.copytree(original, corrected, symlinks=True)
    replacements = {}
    for k in TASKS:
        path = corrected / f'test/task-{k}.spec.js'
        text = path.read_text()
        count = text.count(OLD)
        assert count > 0
        replacements[f'task-{k}'] = count
        path.write_text(text.replace(OLD, NEW))
    jobs = {}
    for version, harness in [('official','157-bom'),('nullguard','157-bom-nullguard')]:
        for control in ('reference','missing-frame','blank'):
            page = OUT / 'pages' / control
            for k in TASKS:
                key = f'{version}/{control}/task-{k}'
                jobs[key] = {'project':'bom','harness':harness,'runtime':'157',
                    'page':str(page.relative_to(ROOT)),'files':source_files(page),
                    'specs':[f'task-{k}'],'all_tests':True}
    dump(OUT / 'inputs.json', {'jobs':jobs,'replacements':replacements,'created_utc':now()})
    files = [HERE/'__init__.py',HERE/'run.py',HERE/'PROTOCOL.md',
        ROOT/'studies/study_io.py', 'studies/browser_jobs.py',ROOT/'test/todomvc_dna/evaluate.py',
        OUT/'inputs.json',OUT/'static-inventory.json',
        browser_jobs.RUNTIME['157'].parent/'package-lock.json']
    for base in (OUT/'pages',OUT/'harness'):
        files += [p for p in base.rglob('*') if p.is_file() and 'node_modules' not in p.parts]
    for name in ('index.js','css.js'):
        files.append(browser_jobs.RUNTIME['157']/'@web-bench/test-util'/name)
    hashes.update({str(p.relative_to(ROOT)):sha(p) for p in files})
    dump(OUT/'snapshot.json',{'frozen_utc':now(),'sha256':hashes})
    print(f'Frozen {len(entries)} official files, {sum(replacements.values())} guard substitutions, {len(jobs)} reports',flush=True)


def evaluate():
    snapshot = read(OUT/'snapshot.json')
    for name,checksum in snapshot['sha256'].items():
        assert sha(ROOT/name)==checksum,name
    browser_jobs.OUT = OUT
    for key,job in read(OUT/'inputs.json')['jobs'].items():
        assert datetime.now(timezone.utc) < datetime(2026,11,17,3,25,tzinfo=timezone.utc), 'Diagnostic time boundary'
        result = browser_jobs.grade(key,job)
        print(key,result['all_passed'],flush=True)
    dump(OUT/'evaluation-complete.json',{'finished_utc':now(),'inputs_sha256':sha(OUT/'inputs.json')})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','evaluate'])
    args=parser.parse_args()
    prepare() if args.action=='prepare' else evaluate()
