"""Measure state changes using public user actions on the unchanged table starter."""
from urllib.parse import urlsplit

from playwright.sync_api import Error, sync_playwright
from studies.public_library_transfer import browser
from studies.study_io import ROOT

OWNERS={
    'selected':('markSelection','cellClick'), 'visible':('menuVisibility',),
    'row':('rowAction','menuVisibility'), 'col':('columnAction','menuVisibility'),
    'arrow':('navigate','markSelection'), 'delete':('editingKeys','cellClick'),
    'edit':('editCell',), 'clipboard':('clipboardKeys',), 'resize':('resizeCells',),
    'reorder':('reorderCells','selectGroup'),
}


def measure(root, candidate):
    page=ROOT/candidate['page']
    served=browser.served_page(root,'table',page,candidate['files'])
    observed={}
    errors=[]
    with browser.serve('table',served) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        tab=engine.new_page(service_workers='block')
        tab.set_default_timeout(1500)
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        tab.on('pageerror',lambda e:errors.append(str(e)[:240]))
        def reset():tab.goto(url+'/index.html',wait_until='load')
        def selection():
            cell=tab.locator('tbody td').first
            cell.click()
            return cell.evaluate("e=>e.classList.contains('selected')")
        def menu(kind):
            body=kind!='col'
            cell=tab.locator('tbody td' if body else 'thead th').first
            cell.click(button='right')
            if kind=='visible':return tab.locator('.menu:visible').count()==1
            action=tab.locator('.menu:visible .menu-item-insert-'+('row-above' if body else 'col-left')+':visible')
            count=tab.locator('tbody tr' if body else 'thead th')
            before=count.count()
            if not action.count():return False
            action.first.click()
            return count.count()==before+1
        def arrow():
            tab.keyboard.press('ArrowRight')
            return tab.locator('thead th').first.evaluate("e=>e.classList.contains('selected')")
        def remove():
            cell=tab.locator('tbody td').first
            cell.click();tab.keyboard.press('Delete')
            return cell.text_content()==''
        def edit():
            cell=tab.locator('tbody td').first
            cell.dblclick()
            return cell.evaluate('e=>e.isContentEditable')
        def clipboard():
            cells=tab.locator('tbody td')
            text=cells.nth(0).text_content()
            cells.nth(0).click();tab.keyboard.press('Control+c');cells.nth(1).click();tab.keyboard.press('Control+v')
            return cells.nth(1).text_content()==text
        def resize():
            cell=tab.locator('tbody td').first;box=cell.bounding_box()
            x=box['x']+box['width']/2;y=box['y']+box['height']-1
            tab.mouse.move(x,y);tab.mouse.down();tab.mouse.move(x,y+36,steps=6);tab.mouse.up()
            return cell.bounding_box()['height']>box['height']+8
        def reorder():
            cells=tab.locator('tbody tr > :first-child')
            before=cells.all_text_contents()
            cells.first.click(button='right')
            ctl=tab.locator('.menu:visible .menu-item-select-row:visible')
            if not ctl.count():return False
            ctl.first.click();cells.first.drag_to(cells.nth(1),target_position={'x':10,'y':30})
            return cells.all_text_contents()==list(reversed(before))
        probes={'selected':selection,'visible':lambda:menu('visible'),'row':lambda:menu('row'),'col':lambda:menu('col'),
                'arrow':arrow,'delete':remove,'edit':edit,'clipboard':clipboard,'resize':resize,'reorder':reorder}
        for name,fn in probes.items():
            try:
                reset();observed[name]=bool(fn())
            except (Error,TypeError) as e:
                observed[name]=False
                errors.append(name+': '+str(e).splitlines()[0][:140])
    return dict(checks=observed,errors=sorted(set(errors)))


def admitted(observation):
    return all(observation['checks'][k] for k in ('selected','visible','row')) and not observation['errors']
