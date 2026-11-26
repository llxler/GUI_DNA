"""Execute independent public interaction sequences in a disposable browser."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Error, sync_playwright
from studies.public_library_transfer import browser
from studies.study_io import ROOT

OUT=ROOT/'artifacts/table-interaction-modules-20261126pm'


def probe(candidate):
    page=ROOT/candidate['page']
    served=browser.served_page(OUT,'table',page,candidate['files'])
    with browser.serve('table',served) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng:
        tab=eng.new_page(service_workers='block')
        tab.set_default_timeout(850)
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        observed={}
        errors=[]
        tab.on('pageerror', lambda e:errors.append(str(e)[:160]))
        def cells():return tab.locator('table tr > :is(td,th)')
        def select(i):return cells().nth(i).evaluate("e=>e.classList.contains('selected')")
        def key(k):tab.keyboard.press(k)
        def menu(i,name):
            cells().nth(i).click(button='right')
            item=tab.locator('.menu:visible .menu-item-'+name)
            if not item.count():return False
            item.first.click()
            return True
        def selected():
            cells().nth(4).click();cells().nth(5).click()
            return select(5) and not select(4)
        def row():
            old=tab.locator('tbody tr').count()
            return menu(5,'insert-row-below') and tab.locator('tbody tr').count()==old+1 and not tab.locator('.menu:visible').count()
        def col():
            old=tab.locator('thead th').count()
            return menu(1,'insert-col-left') and tab.locator('thead th').count()==old+1 and tab.locator('tbody tr').first.locator('td').count()==old+1
        def arrow():
            key('ArrowRight');a=select(0);key('ArrowDown')
            return a and select(3) and not select(0)
        def wrap():
            cells().nth(2).click();key('Tab');a=select(3);key('Shift+Tab')
            return a and select(2)
        def edit():
            cells().nth(4).dblclick();a=cells().nth(4).evaluate('e=>e.isContentEditable')
            key('Escape');return a and select(4) and not cells().nth(4).evaluate('e=>e.isContentEditable')
        def clear():
            cells().nth(5).click();key('Delete');return cells().nth(5).inner_text()==''
        def clip():
            cells().nth(4).click();key('Control+c');cells().nth(7).click();key('Control+v')
            return cells().nth(7).inner_text()==cells().nth(4).inner_text() and bool(cells().nth(4).inner_text())
        def drag():
            a,b=[cells().nth(i).bounding_box() for i in (4,8)]
            xy=lambda z:(z['x']+z['width']/2,z['y']+z['height']/2)
            tab.mouse.move(*xy(a));tab.mouse.down();tab.mouse.move(*xy(b),steps=5);tab.mouse.up()
            return all(select(i) for i in (4,5,7,8)) and not select(3)
        def resize():
            c=cells().nth(4);b=c.bounding_box();x,y=b['x']+15,b['y']+b['height']-1
            tab.mouse.move(x,y);tab.mouse.down();tab.mouse.move(x,y+29,steps=5);tab.mouse.up()
            return c.bounding_box()['height']>b['height']+10
        def reorder():
            targets=tab.locator('tbody tr td:first-child')
            old=targets.all_text_contents()
            if not menu(3,'select-row'):return False
            targets.nth(0).drag_to(targets.nth(1))
            return targets.all_text_contents()==old[::-1]
        for name,test in [('selection',selected),('row',row),('column',col),('arrow',arrow),('wrap',wrap),('edit',edit),('clear',clear),('clipboard',clip),('range',drag),('resize',resize),('reorder',reorder)]:
            try:
                tab.goto(url+'/index.html',wait_until='load',timeout=4500)
                observed[name]=bool(test())
            except (Error,TypeError) as e:observed[name]=False;errors.append(name+': '+str(e).splitlines()[0][:150])
        return dict(checks=observed,errors=sorted(set(errors))[:12])


if __name__=='__main__':
    print(json.dumps(probe(json.load(sys.stdin))))
