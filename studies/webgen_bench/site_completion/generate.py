"""Seal one directly generated page and a shared configuration for every new site."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ..component_contracts.typed_inputs import local_edits, native_visibility
from ..functional_pilot import generate as gen, pages, schema
from ..functional_pilot.native_plans import content, run as native

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/webgen-site-completion-20261128'
CANDIDATES = HERE/'candidates.json'
END = datetime(2026, 11, 28, 10, 32, tzinfo=timezone.utc)
CAP = 3.50
MODEL_LIBRARIES = {
    'gemma': local_edits.OUT/'build/gemma/library.json',
    'qwen9': native_visibility.OUT/'build/qwen9/library.json',
    'deepseek-flash': native.OUT/'build/deepseek-flash/library.json',
}
PLAN_PROMPT = content.SPEC + """
For each action explicitly requested in the brief, identify its entry control, inputs and observable result.
Choose a form for user input, a detail for revealing content, and actual rows for collections.
Put the main workflow first, group related actions in the same view, use exact labels from the brief,
and reserve text blocks for information. Use short labels and realistic distinct records.
Only claim actions the selected component can perform. Return the resulting plan only."""
DIRECT_PROMPT = """Build a locally working website for the supplied brief. For each requested action
provide its entry control, inputs and observable result, using browser state as needed. Put the main
workflow first and keep labels clear. Deliver one concise HTML document with inline CSS and scripts.
Use no external resources. Return only the document, with working behavior before decorative content."""


def input_sites():
    import duckdb
    assert sha(gen.SRC) == read(gen.REG)['sha256']
    rows = duckdb.sql('select id, instruction, Category.primary_category from read_parquet(?)',
                      params=[str(gen.SRC)]).fetchall()
    selected = {}
    for category, original in read(gen.REG)['pilot_sites'].items():
        group = sorted((r for r in rows if r[2] == category),
                       key=lambda r: (hashlib.sha256(('gui-dna-webgen-v1:'+r[0]).encode()).digest(), r[0]))
        assert {r[0] for r in group[:2]} == set(original)
        selected.update((site, brief) for site, brief, _ in group[3:6])
    assert len(selected) == 9
    return selected


def direct_document(raw):
    text = gen.BASE.uncode(raw).strip()
    block = re.fullmatch(r'```(?:html)?\s*\n(.*?)(?:\n```)?', text, flags=re.S | re.I)
    if block:
        text = block[1].strip()
    if not re.match(r'(?:<!doctype\s+html[^>]*>\s*)?<html\b', text, re.I) or not re.search(r'<body\b[^>]*>', text, re.I):
        raise ValueError('Return an HTML document with html and body elements')
    return text


def target(tag, site, brief, arm, ledger):
    directory = OUT/'jobs'/tag/site/arm
    saved = directory/'record.json'
    if saved.exists():
        return read(saved)
    plan = arm == 'plan'
    msg = core.messages(PLAN_PROMPT if plan else DIRECT_PROMPT,
                        {'brief': brief, 'example': content.EXAMPLE} if plan else {'brief': brief})
    for attempt in range(2):
        try:
            raw = gen.call(ledger, tag, directory/str(attempt), msg, 'plan', 8192 if tag == 'gemma' else 12000)
            if plan:
                result = dict(status='valid', config=content.compile_plan(gen.parse(raw)))
            else:
                html = direct_document(raw)
                result = pages.write_html(directory/'site', html) | {'closed_document':bool(re.search(r'</html\s*>', html, re.I))}
            break
        except gen.MISSING as exc:
            result = dict(status='missing', reason=str(exc))
            break
        except gen.ERRORS as exc:
            result = dict(status='invalid', reason=str(exc)[:200])
            msg += [{'role':'assistant', 'content':raw}, {'role':'user', 'content':
                    'Public format error: '+result['reason']+'. Return one complete, concise corrected document.'}]
    core.save(saved, result)
    return result


def self_page(tag, config, library):
    if tag == 'deepseek-flash':
        return native.html(config, library['parts'], library['mode'])
    return native_visibility.dom.comp.previous.site(config, library['parts'], True)


def generate():
    sites = input_sites()
    training = gen.OUT/'generation-input.json'
    assert set(sites).isdisjoint(read(training))
    files = [Path(__file__), HERE/'PROTOCOL.md', gen.SRC, gen.REG, training, gen.DIST, pages.SDK/'sdk.js',
             pages.SDK/'sdk.css', Path(content.__file__), Path(gen.__file__), Path(gen.BASE.__file__),
             Path(native.__file__), Path(native_visibility.dom.comp.previous.__file__), *MODEL_LIBRARIES.values()]
    hashes = {str(f.relative_to(ROOT)):sha(f) for f in files}
    reg = OUT/'registration.json'
    if not reg.exists():
        balance = check_credits(CAP)
        assert balance['sufficient'] and datetime.now(timezone.utc) < END
        core.save(reg, dict(utc=now(), deadline=END.isoformat(), cap=CAP, balance=balance,
                            sites=sorted(sites), sources=hashes, models={tag:gen.model(tag) for tag in gen.BUILDERS}))
    assert read(reg)['sources'] == hashes and read(reg)['sites'] == sorted(sites)
    if CANDIDATES.exists():
        assert read(CANDIDATES)['seal'] == sha(OUT/'seal.json')
        return
    core.save(OUT/'briefs.json', sites)
    libraries = {tag:read(f) for tag,f in MODEL_LIBRARIES.items()}
    sdk_check = pages.check(pages.page(schema.SAMPLE,'human'), True)
    assert all(sdk_check['checks'].values())
    for tag, library in libraries.items():
        assert library['status'] == 'valid'
        assert all(pages.check(self_page(tag, schema.SAMPLE, library))['checks'].values())
    ledger = Ledger(OUT/'budget.sqlite3', CAP, CAP)
    rows = {tag:{} for tag in gen.TAGS}
    with patch.multiple(gen.BASE, OUT=OUT, END=END, template=gen.settings), patch.object(gen,'OUT',OUT), ThreadPoolExecutor(max_workers=7) as workers:
        donor_task = workers.submit(gen.build, 'gpt5', read(training), ledger)
        jobs = {(t,s,a):workers.submit(target,t,s,b,a,ledger) for s,b in sites.items() for t in gen.TAGS for a in ('direct','plan')}
        donor = donor_task.result()
        for tag in gen.TAGS:
            for site in sites:
                direct = jobs[tag,site,'direct'].result()
                plan = jobs[tag,site,'plan'].result()
                arms = {'direct':direct}
                for arm in ('human','self','gpt5-library'):
                    if arm == 'gpt5-library' and donor['status'] != 'valid':
                        arms[arm] = {k:donor[k] for k in ('status','reason') if k in donor}
                    elif plan['status'] != 'valid':
                        arms[arm] = plan
                    else:
                        config = plan['config']
                        page = self_page(tag, config, libraries[tag]) if arm == 'self' else pages.page(config,'human' if arm == 'human' else donor['parts'])
                        arms[arm] = pages.write_html(OUT/'sites'/tag/site/arm, page)
                rows[tag][site] = arms
    plans = {str(p.relative_to(OUT)):sha(p) for p in (OUT/'jobs').glob('*/*/plan/record.json')}
    sources = {tag:sha(f) for tag,f in MODEL_LIBRARIES.items()} | {'gpt5':sha(OUT/'build/gpt5/library.json'),'human':sha(gen.DIST)}
    seal = dict(registration=sha(reg), sources=sources, plans=plans, rows=rows)
    core.save(OUT/'seal.json', seal)
    core.save(CANDIDATES, seal | dict(seal=sha(OUT/'seal.json'), sdk_public=sdk_check,
              models=read(reg)['models'], donor_status=donor['status'], cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__ == '__main__':
    with browser.lock(OUT/'run.lock'):
        generate()
