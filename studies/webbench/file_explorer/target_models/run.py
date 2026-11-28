"""Evaluate two new file-explorer generators on the same four library-source arms."""
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.target_models import run as targets
from studies.webbench.file_explorer.interaction_contracts import run as interactions

docs = interactions.docs
original = docs.ORIG
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/file-explorer-target-models-20261128'
CAP = 2.50
TAGS = targets.MODELS


def register():
    old = read(original.OUT / 'registration.json')
    sources = [Path(__file__), HERE / 'PROTOCOL.md', original.OUT / 'registration.json', Path(original.base.__file__),
               Path(docs.__file__), Path(docs.dom.__file__), Path(interactions.__file__), interactions.HERE / 'probe.py']
    sums = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    for name, fingerprint in old['sources'].items():
        if sha(ROOT / name) != fingerprint:
            raise ValueError(f'Changed original source {name}')
    if core.public_input('dom1') != read(original.OUT / 'public.json') or browser.verify_contract('dom1') != read(original.OUT / 'browser.json'):
        raise ValueError('File explorer public or official inputs changed')
    f = OUT / 'registration.json'
    if not f.exists():
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(f, dict(utc=now(), deadline=targets.END.isoformat(), cap=CAP, balance=balance,
                          sources=sums, targets=old['targets'], models={t: original.action.settings('table', t, 'plan')['model'] for t in TAGS},
                          source_costs={k:v for k,v in old['source_costs'].items() if k != 'astra'}))
    if read(f)['sources'] != sums:
        raise ValueError('Registered inputs changed')
    return read(f)


def build(ledger, tag, rep, pub):
    folder = docs.SOURCE / tag / rep / 'calls/core/0'
    brief = dict(starter=pub['starter']['index.html'], requirements=pub['requirements'][:5], feature=docs.dom.DESCRIPTION['core'])
    prompt = core.messages('Return one self-contained complete HTML document implementing the public file explorer core. '
                           'Use the public starter layout; implement the actual operations, selectors and styling.', brief)
    try:
        original.base.request(ledger, ('table',tag,rep), folder, prompt, 'build', 6500)
    except original.action.typed.MISSING as exc:
        return dict(status='missing', reason=str(exc))
    first = docs.library(tag, rep, pub, ledger)
    if first['status'] != 'valid':
        return dict(status=first['status'], initial_checks=first['public'])
    final = interactions.build(tag, rep, ledger, pub)
    return dict(status='valid', parts=final['parts'], before=final['before'], after=final['after'],
                initial=sha(docs.OUT / tag / rep / 'library.json'), repair=sha(interactions.OUT / tag / rep / 'library.json'))


def deploy(job, ledger, pub, tasks, human, gpt, libraries, frozen):
    tag, n, arm = job
    folder = OUT / tag / 'targets' / str(n) / arm
    record = folder / 'record.json'
    if record.exists():
        return read(record)
    page = folder / 'page'

    def ask(msg, limit):
        return original.base.request(ledger, ('table',tag, arm[-1] if arm.startswith('self-') else 'a'), folder / 'call', msg, 'plan', limit)

    try:
        if arm == 'direct':
            raw = ask(core.direct_messages(pub, n), 11000)
            try:
                source = {'index.html': docs.parse_document(raw)}
            except ValueError:
                files = docs.receipt.first_object(raw)['files']
                source = core.files_map(files) if isinstance(files, list) else original.blind.validate_files(files)
                if not source:
                    raise ValueError('Empty direct implementation')
            result = original.emit(page, core.emit('dom1', pub['starter'] | source, page))
        elif arm == 'human':
            prompt = original.domain.messages_for(tasks[n], 'dna', human)
            prompt += [dict(role='user', content='Public starter layout:\n' + pub['starter']['index.html'])]
            plan = docs.receipt.first_object(ask(prompt, 6000))
            js = original.domain.compile_plan(plan, tasks[n]['features'], human)
            result = original.emit(page, core.emit('dom1', {'index.html': original.SHELL.read_text().replace('/*__CANDIDATE__*/', js)}, page))
        elif arm == 'gpt5-library':
            if not frozen['admitted']:
                result = dict(status='build_failed')
            else:
                prompt = core.messages('Return only a data-only JSON plan for this existing file explorer. Match the documented plan language.',
                                       dict(public=core.prefix(pub,n), schema=gpt['plan_schema'], design=gpt['design'], examples=gpt['examples']))
                result = original.emit(page, core.emit('dom1', original.blind.compile_plan(gpt, docs.receipt.first_object(ask(prompt,6000))), page))
        else:
            lib = libraries[tag,arm[-1]]
            if lib['status'] != 'valid':
                result = dict(status=lib['status'])
            else:
                parts = lib['parts']
                opts = [k for k in parts if k!='core']
                profiles = list(dict.fromkeys([tuple(opts), (), *[tuple(opts[:i]) for i in range(1,len(opts))], *[(k,) for k in opts]]))
                prompt = core.messages('Choose a feature profile that serves the latest requirement and its prerequisites. Output its number only.',
                                       dict(brief=core.prefix(pub,n), profiles=[dict(index=i,features=list(p)) for i,p in enumerate(profiles)],
                                            features={k:docs.dom.DESCRIPTION[k] for k in opts}))
                raw = original.base.uncode(ask(prompt,1800)).strip()
                if not re.fullmatch('[0-9]+',raw) or int(raw)>=len(profiles):
                    raise ValueError('Expected an available profile number')
                selected = profiles[int(raw)]
                result = docs.emit(pub, {k:v for k,v in parts.items() if k=='core' or k in selected}, page) | dict(selected=list(selected))
    except original.action.typed.MISSING as exc:
        result = dict(status='missing', reason=str(exc))
    except original.base.ERRORS as exc:
        result = dict(status='invalid', reason=str(exc)[:200])
    core.save(record, dict(project='dom1', tag=tag, task=n, arm=arm, **result))
    return read(record)


def generate(reg):
    seal = OUT / 'seal.json'
    if seal.exists():
        return
    ledger = Ledger(OUT / 'budget.sqlite3', CAP, CAP)
    pub, gpt = read(original.OUT / 'public.json'), read(original.GPT / 'package.json')
    human, tasks = original.domain.library(), {t['k']:t for t in original.domain.tasks()}
    assert len(human['functions']) == 44
    dest = OUT / 'fixed/gpt5'
    files = core.emit('dom1', original.blind.compile_plan(gpt, gpt['examples'][0]['plan']), dest)
    admission = original.library.observe(OUT, dest, files)
    baseline = {'starter': docs.emit(pub, {}, OUT/'fixed/starter'),
                'fixed-gpt5-library': original.emit(dest, files) if admission['admitted'] else dict(status='build_failed')}
    pairs = list(product(TAGS, 'ab'))
    arms = ('direct','human','gpt5-library','self-a','self-b')
    with patch.multiple(original.base, OUT=OUT, END=targets.END, template=original.action.settings), \
            patch.multiple(docs, SOURCE=OUT/'initial', OUT=OUT/'documents'), patch.object(docs.dom,'OUT',OUT/'documents'), \
            patch.object(interactions,'OUT',OUT/'interactions'), ThreadPoolExecutor(max_workers=4) as pool:
        libraries = dict(zip(pairs, pool.map(lambda p:build(ledger,*p,pub), pairs), strict=True))
        rows = list(pool.map(lambda job: deploy(job,ledger,pub,tasks,human,gpt,libraries,admission),
                             product(TAGS,reg['targets'],arms)))
    for tag in TAGS:
        controls = dict(baseline)
        for rep in 'ab':
            value = libraries[tag,rep]
            for name in ('fixed','core'):
                parts = value.get('parts',{})
                controls[name+'-'+rep] = (docs.emit(pub, parts if name=='fixed' else {'core':parts['core']},
                                                        OUT/tag/name/rep) if value['status']=='valid' else dict(status=value['status']))
        rows += [dict(project='dom1',tag=tag,task=n,arm=k,**v) for n in reg['targets'] for k,v in controls.items()]
    core.save(seal, dict(registration=sha(OUT/'registration.json'), rows=rows, public=admission,
                         libraries={t:{r:{k:v for k,v in libraries[t,r].items() if k!='parts'} for r in 'ab'} for t in TAGS}))


def score(reg):
    seal = read(OUT/'seal.json')
    assert seal['registration'] == sha(OUT/'registration.json')
    protocol = browser.verify_contract('dom1')
    assert protocol == read(original.OUT/'browser.json')
    rows = browser.evaluate(seal['rows'], OUT, {'dom1':protocol}, 4)
    models = {m:[dict(task=r['task'], arm=r['arm'],status=r['status'],passed=False if r['status']=='invalid' else r['passed'],
                           report_sha256=r['report_sha256']) for r in rows if r['tag']==t] for t,m in reg['models'].items()}
    core.save(HERE/'result.json', dict(registration=seal['registration'], seal=sha(OUT/'seal.json'), models=models,
                                       cost=ledger_read.totals(OUT/'budget.sqlite3'), public=seal['public'],
                                       libraries=seal['libraries'],source_costs=reg['source_costs']))


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        registration = register()
        generate(registration)
        if not (HERE/'result.json').exists():
            score(registration)
