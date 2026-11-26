"""Causal replay of a one-line DOM event correction on frozen GPT-5 pages."""
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from studies.webbench.table_interactions import run as prior,diagnose

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-menu-propagation-20261126'
TARGET="document.addEventListener('contextmenu', (evt)=>{"
AFTER=TARGET+'\n      if (evt.defaultPrevented) return;'


def altered(row,dest):
    source=ROOT/row['page']
    assert browser.tree(source)==row['files']
    files={k:(source/k).read_text() for k in row['files'] if not k.startswith('assets/')}
    assert files['index.js'].count(TARGET)==1
    files['index.js']=files['index.js'].replace(TARGET,AFTER,1)
    out=core.emit('table',files,dest)
    assert {k for k,v in out.items() if row['files'].get(k)!=v}=={'index.js'}
    return {**row,'page':str(dest.relative_to(ROOT)),'files':out}


def public(page):
    served=browser.served_page(OUT,'table',ROOT/page['page'],page['files'])
    with browser.browser_slot(),browser.serve('table',served) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        tab=engine.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        tab.set_default_timeout(1800)
        tab.goto(url+'/index.html')
        first=tab.locator('tbody td').first
        menu=tab.locator('.menu:visible')
        first.click(button='right')
        visible=menu.count()>0
        before=tab.locator('tbody tr').count()
        button=menu.locator('.menu-item-insert-row-above')
        if button.count():button.first.click()
        insert=tab.locator('tbody tr').count()==before+1
        first.click(button='right')
        tab.locator('body').evaluate("el=>el.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,button:2}))")
        return dict(visible_inside=visible,inserted=insert,hidden_outside=menu.count()==0)


def main():
    cells=read(prior.RESULT)['cells']
    files=[Path(__file__),HERE/'PROTOCOL.md',prior.RESULT,diagnose.RESULT,Path(prior.__file__),Path(browser.__file__)]
    files+=[prior.OUT/'table'/c['tag']/'gpt5-library/seal.json' for c in cells]
    reg=OUT/'registration.json'
    sources={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not reg.exists():core.save(reg,dict(utc=now(),sources=sources,new_calls=0))
    assert read(reg)['sources']==sources
    rows=[]
    old={}
    for c in cells:
        tag=c['tag']
        seal=prior.OUT/'table'/tag/'gpt5-library/seal.json'
        assert sha(seal)==c['seal_sha256']
        verdict={(r['arm'],r['task']):r for r in c['rows']}
        for r in read(seal)['rows']:
            arm,n=r['arm'],r['task']
            if arm!='gpt5-library':continue
            old[tag,n]=verdict[arm,n]['passed']
            val=altered(r,OUT/'planned'/tag/str(n)) if r['status']=='valid' else r
            rows.append(dict(val,tag=tag,arm='corrected-plan'))
    registered=read(prior.OUT/'registration.json')['cells'][0]
    pkg=read(ROOT/registered['package']);pub=core.public_input('table')
    checks={}
    for i,plan in enumerate(prior.choices(pkg,'gpt5-library','table')):
        before=prior.compact.compile_page('table','gpt5-library',pkg,plan,pub,OUT/'profiles'/str(i)/'before')
        after=altered(before,OUT/'profiles'/str(i)/'after')
        checks[i]=dict(before=public(before),after=public(after))
        for label,page in [('original-fixed',before),('corrected-fixed',after)]:
            rows.extend(dict(page,project='table',task=n,tag=str(i),arm=label) for n in range(1,21))
    seal=OUT/'seal.json'
    core.save(seal,dict(registration=sha(reg),rows=rows,checks=checks))
    protocol=browser.verify_contract('table')
    results=[]
    for value in browser.evaluate(rows,OUT,{'table':protocol},4):
        arm,t,n=value['arm'],value['tag'],value['task']
        rec=dict(arm=arm,tag=t,task=n,status=value['status'],passed=False if value['status']=='invalid' else value['passed'],report_sha256=value.get('report_sha256'))
        if arm=='corrected-plan':rec['before']=old[t,n]
        results.append(rec)
    core.save(HERE/'result.json',dict(registration=sha(reg),seal=sha(seal),new_calls=0,public=checks,rows=results))


if __name__=='__main__':
    with browser.lock(OUT/'.lock'):main()
