"""Observe event propagation and single-cell deletion for all four registered profiles."""
import argparse
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha
from . import run

RESULT=run.HERE/'public-actions.json'


def measure():
    reg=run.register()
    cell=reg['cells'][0]
    source=ROOT/cell['package']
    pub=read(run.base.old_root('table',cell['tag'])/'inputs/table/public.json')
    controls={}
    with sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        for i,plan in enumerate(run.choices(read(source),'gpt5-library','table')):
            dest=run.OUT/'public-actions'/str(i)
            row=run.compact.compile_page('table','gpt5-library',read(source),plan,pub,dest)
            served=browser.served_page(run.OUT,'table',dest,row['files'])
            with browser.serve('table',served) as url:
                tab=engine.new_page(service_workers='block')
                tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
                tab.goto(url+'/index.html',wait_until='load')
                tab.evaluate("""() => {window.menuTrace = []; for(const el of [document.querySelector('.table'),document]){
                  el.addEventListener('contextmenu',()=>window.menuTrace.push({phase:el===document?'document':'table',
                    visible:[...document.querySelectorAll('.menu')].some(e=>e.getBoundingClientRect().height>0)}));}}""")
                cell_node=tab.locator('tbody td').first
                cell_node.click(button='right')
                trace=tab.evaluate('menuTrace')
                tab.goto(url+'/index.html',wait_until='load')
                before=cell_node.text_content()
                cell_node.click();tab.keyboard.press('Delete')
                after=cell_node.text_content()
                tab.goto(url+'/index.html',wait_until='load')
                cell_node.dblclick()
                controls[str(i)]=dict(plan=plan,contextmenu=trace,delete_before=before,delete_after=after,
                                      double_click_editable=cell_node.evaluate('e=>e.isContentEditable'))
                tab.close()
    return dict(sources={'script':sha(Path(__file__)),'registration':sha(run.OUT/'registration.json'),'package':sha(source)},
                scope='Public browser actions on every registered interaction profile.',controls=controls)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    data=measure()
    if args.write:core.save(RESULT,data)
    assert read(RESULT)==data
    for key,v in data['controls'].items():print(key,v)
