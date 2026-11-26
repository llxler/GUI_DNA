"""Replay public table actions on the exact two fixed implementations used by the Qwen comparison."""
import argparse
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,digest
from . import run

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/frozen-table-actions-20261125'
RESULT=HERE/'table-actions.json'


def trace():
    public=run.base.old_root('table','qwen')/'inputs/table/public.json'
    source=[Path(__file__),public,Path(browser.__file__)]
    fixed={}
    for arm in ('human','gpt5-library'):
        seal=run.OUT/'table/qwen'/arm/'seal.json'
        source.append(seal)
        fixed[arm]=read(seal)['fixed']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in source}
    reg=OUT/'protocol.json'
    if not reg.exists():core.save(reg,dict(sources=hashes,benchmark_feedback='Post hoc public-behavior diagnosis; never used for generation.',
        actions=['right-click first body cell, inspect menu and insert-above control','press ArrowLeft from initial state',
                 'select first body cell and press Delete','double-click first body cell'],fees_usd=0))
    assert read(reg)['sources']==hashes
    data={}
    for arm,r in fixed.items():
        path=ROOT/r['page']; browser.verify_page(path,r['files'],'table')
        served=browser.served_page(OUT,'table',path,r['files'])
        with browser.serve('table',served) as url,sync_playwright() as pw, pw.chromium.launch(env=browser.browser_env()) as engine:
            tab=engine.new_page(service_workers='block')
            tab.route('**/*',lambda rr:rr.continue_() if urlsplit(rr.request.url).netloc==urlsplit(url).netloc else rr.abort())
            errors=[]
            tab.on('pageerror',lambda e:errors.append(str(e)[:250]))
            def reset():
                tab.goto(url+'/index.html',wait_until='load')
                return tab.locator('tbody td').first
            cell=reset()
            cell.click(button='right')
            control=tab.locator('.menu-item-insert-row-above')
            context=dict(visible_menu=tab.locator('.menu:visible').count(),visible_insert_above=control.filter(visible=True).count())
            if context['visible_insert_above']:
                before=tab.locator('tbody tr').count()
                control.first.click()
                context['row_count_change']=tab.locator('tbody tr').count()-before
            reset()
            tab.keyboard.press('ArrowLeft')
            selected=tab.locator('.selected')
            nav=dict(selected_cells=selected.count(),first_top_left=tab.locator('.table tr:first-child > :first-child.selected').count()>0)
            cell=reset()
            before=cell.text_content()
            cell.click()
            tab.keyboard.press('Delete')
            removed=dict(before=before,after=cell.text_content(),selection=tab.locator('td.selected').count())
            cell=reset()
            cell.dblclick()
            edit=cell.evaluate('e => e.isContentEditable')
            data[arm]=dict(files_digest=digest(r['files']),right_click=context,arrow_left=nav,delete=removed,
                          double_click_editable=edit,errors=sorted(set(errors)))
    return dict(registration_sha256=sha(reg),scope='Public action probes on frozen default pages; no official score changes.',arms=data)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    data=trace()
    if args.write:core.save(RESULT,data)
    assert read(RESULT)==data
    print(data['arms'])
