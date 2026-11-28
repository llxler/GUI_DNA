"""Score sealed plans on official subsets and on separately registered edit/reload probes."""
from playwright.sync_api import Error, sync_playwright

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha
from studies.webgen_bench.functional_pilot import pages
from . import run

START = """title => {
  const c = window.candidate;
  let s = c.reduce(c.init(), {type: 'add', title});
  const item = s.todos.find(x => x.title === title);
  if (!item) throw Error('Cannot create item');
  s = c.reduce(s, {type: 'edit', id: item.id});
  return {id: item.id, opened: s.editing === item.id};
}"""
RESTORE = """({id,title}) => {
  const s = window.candidate.init();
  return {retained: s.todos.some(t => t.id === id && t.title === title), idle: s.editing == null};
}"""


def probe(engine, code, title, expected):
    with pages.local_tab(engine, '<!doctype html><body></body>') as tab:
        try:
            tab.add_script_tag(content=code)
            opened = tab.evaluate(START, title)
            tab.reload()
            tab.add_script_tag(content=code)
            restored = tab.evaluate(RESTORE, dict(id=opened['id'], title=title))
            return opened | restored | dict(passed=opened['opened'] == expected and all(restored.values()))
        except Error as exc:
            return dict(passed=False, error=str(exc).splitlines()[0][:240])


def evaluate():
    dest = run.HERE / 'result.json'
    if dest.exists():
        return
    sealed = read(run.OUT / 'seal.json')
    if sealed['registration'] != sha(run.OUT / 'registration.json'):
        raise ValueError('Seal does not match registration')
    weak = run.weak
    targets, _ = weak.suite.inputs()
    old = read(run.evidence.RESULT)
    cache = {}
    for result in [old, read(run.state.HERE / 'result.json')]:
        for block in result['models'].values():
            for r in block['rows']:
                if r['status'] == 'valid' and r.get('files_sha256'):
                    k = r['task'], r['files_sha256']
                    if k in cache and r['passed'] != cache[k]['passed']:
                        raise ValueError('Conflicting prior verdict')
                    cache[k] = r
    models = {}
    server = weak.evaluate.todo.Server(run.OUT)
    try:
        with browser.browser_slot(), sync_playwright() as pw, pw.chromium.launch(env=browser.browser_env()) as engine:
            for tag, reps in sealed['decisions'].items():
                model = weak.MODELS[tag]
                rows = [r for r in old['models'][model]['rows'] if r['arm'] in ('direct', 'human', 'gpt5-library', 'fixed-a', 'fixed-b')]
                probes, choices = {}, {}
                for rep, records in reps.items():
                    lib = read(run.state.OUT / tag / rep / 'library.json')
                    fixed = run.state.todo.MOD.assemble(lib['functions'], run.state.ALL)
                    probes[rep], choices[rep] = {}, {}
                    for key, item in records.items():
                        valid = item['status'] == 'valid'
                        if valid:
                            path = ROOT / item['candidate']['file']
                            digest = sha(path)
                            if digest != item['candidate']['files_sha256']:
                                raise ValueError('Sealed candidate changed')
                        choices[rep][key] = {k: v for k, v in item.items() if k != 'candidate'}
                        if key in run.PROBES:
                            title = f'Sage {key} {rep}'
                            expect = run.PROBES[key][1]
                            fixed_obs = probe(engine, fixed, title, expect)
                            obs = probe(engine, read(path)['candidate.js'], title, expect) if valid else {'status': item['status']}
                            probes[rep][key] = dict(planned=obs, fixed=fixed_obs)
                            continue
                        row = dict(task=key, arm=rep, status=item['status'], passed=False if item['status']=='invalid' else None)
                        if valid:
                            if (key, digest) in cache:
                                row = dict(cache[key, digest], arm=rep, reused=True)
                            else:
                                output = run.OUT / 'scores' / key / digest
                                weak.evaluate.score(('todomvc', targets[key], read(path), output, server))
                                row.update(weak.recovery.todo.binding.official(output, targets[key], {}), files_sha256=digest, reused=False)
                                cache[key, digest] = row
                        rows.append(row)
                models[model] = dict(rows=rows, probes=probes, choices=choices)
    finally:
        server.close()
    core.save(dest, dict(registration=sealed['registration'], seal=sha(run.OUT / 'seal.json'),
                         prior=sha(run.evidence.RESULT), models=models,
                         cost=ledger_read.totals(run.OUT / 'budget.sqlite3')))
