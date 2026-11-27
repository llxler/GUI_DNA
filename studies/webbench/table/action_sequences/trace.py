"""Record public table state after each action without inspecting application internals."""
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser


def measure(directory, cases):
    results={}
    with browser.serve('table',directory) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng:
        for name,case in cases.items():
            tab=eng.new_page(service_workers='block')
            tab.set_default_timeout(1000)
            tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
            steps=[]
            try:
                tab.goto(url+'/index.html',wait_until='load',timeout=5000)
                def cell(row,col):return tab.locator('table tr').nth(row).locator(':scope > :is(td,th)').nth(col)
                def snapshot():
                    return tab.locator('table').first.evaluate("""t=>({
                    rows:[...t.rows].map(r=>[...r.cells].map(c=>c.textContent)),
                    selected:[...t.querySelectorAll('th.selected,td.selected')].map(c=>[c.parentElement.rowIndex,c.cellIndex]),
                    editing:[...t.querySelectorAll('th,td')].filter(c=>c.isContentEditable).map(c=>[c.parentElement.rowIndex,c.cellIndex])})""")
                def record(label,expect):
                    state=snapshot();ok=bool(expect(state));steps.append(dict(action=label,passed=ok,state=state))
                    return ok
                def menu(col,label):
                    cell(0,col).click(button='right')
                    tab.get_by_text(label,exact=True).first.click()
                start=snapshot()['rows']
                row,col=case['row'],case['col']
                if name=='columns':
                    index=col+(case['side']=='Right')
                    menu(col,'Insert Col '+case['side'])
                    inserted=record('insert',lambda s:len(s['rows'])==len(start) and all(len(r)==len(b)+1 and r[:index]+r[index+1:]==b for r,b in zip(s['rows'],start)))
                    if inserted:
                        menu(index,'Delete Col')
                        record('remove',lambda s:s['rows']==start)
                elif name=='editing':
                    cell(row,col).click();record('select',lambda s:s['selected']==[[row,col]])
                    tab.keyboard.press('Enter');record('enter',lambda s:[row,col] in s['editing'])
                    tab.keyboard.press('Escape');record('escape',lambda s:not s['editing'] and s['selected']==[[row,col]])
                    tab.keyboard.press(case['arrow'])
                    dest=col+(1 if case['arrow']=='ArrowRight' else -1)
                    record('move',lambda s:s['selected']==[[row,dest]] and not s['editing'])
                else:
                    original=start[row][col]
                    menu(case['header'],'Insert Col '+case['side'])
                    offset=int(case['header']+(case['side']=='Right')<=col)
                    located=record('relocate',lambda s:len(s['rows'][row])==len(start[row])+1 and s['rows'][row][col+offset]==original)
                    if located:
                        cell(row,col+offset).click();record('select-after-insert',lambda s:s['selected']==[[row,col+offset]])
                        tab.keyboard.press(case['arrow'])
                        record('vertical-move',lambda s:s['selected']==[[row+(1 if case['arrow']=='ArrowDown' else -1),col+offset]])
            except Exception as e:
                steps.append(dict(action='browser',passed=False,error=str(e).splitlines()[0][:180]))
            finally:tab.close()
            results[name]=dict(passed=bool(steps) and all(s['passed'] for s in steps),steps=steps)
    return results


if __name__=='__main__':
    args=json.load(sys.stdin)
    print(json.dumps(measure(Path(args['page']),args['cases'])))
