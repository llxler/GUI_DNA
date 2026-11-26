"""Exercise publicly specified state changes on a fresh page for each sequence."""
import json
import re
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser
from studies.study_io import ROOT


def observe(out, candidate):
    stage = browser.served_page(out, 'dom1', ROOT / candidate['page'], candidate['files'])
    checked, errors, trace = {}, {}, {}
    with browser.browser_slot(), browser.serve('dom1', stage) as url, sync_playwright() as playwright:
        with playwright.chromium.launch(env=browser.browser_env()) as engine:
            tab = engine.new_page(service_workers='block')
            tab.route('**/*', lambda r: r.continue_() if urlsplit(r.request.url).netloc == urlsplit(url).netloc else r.abort())
            tab.set_default_timeout(1050)
            responses, dialogs, js_errors = [], [], []
            def reply(d):
                dialogs.append([d.type, d.message[:1400]])
                d.accept(responses.pop(0) if d.type == 'prompt' and responses else None)
            tab.on('dialog', reply)
            tab.on('pageerror', lambda e: js_errors.append(str(e)[:180]))
            def press(name):
                tab.locator('.tools button').filter(has_text=re.compile(r'^\s*'+name+r'\s*$', re.I)).first.click()
            def entry(kind=''):
                return tab.locator('.entries .entry'+kind)
            def command(name):
                tab.locator('.menu:visible .menu-item-'+name+':visible').first.click()
            def run(name):
                tab.goto(url+'/index.html', wait_until='load')
                dialogs.clear(); responses.clear(); js_errors.clear()
                if name == 'roundtrip':
                    tree = {'entries':[{'type':'dir','name':'paper-folder','children':[{'type':'file','name':'leaf','content':'violet'}]}]}
                    responses.append(json.dumps(tree))
                    press('imp')
                    loaded = entry('.dir').count()==1 and entry('.dir').first.locator('.dir-content .file').count()==1
                    press('exp')
                    values = [json.loads(msg) for kind,msg in dialogs if kind=='alert' and msg.lstrip().startswith('{')]
                    def content(nodes):
                        return [(e.get('type'),e.get('name'),e.get('content') if e.get('type')=='file' else content(e.get('children',[]))) for e in nodes]
                    return bool(loaded and values and content(values[-1]['entries']) == content(tree['entries']))
                if name=='nest':
                    press('dir'); directory=entry('.dir').first; press('file')
                    return directory.locator('.dir-content .file.selected').count()==1
                press('file'); file=entry('.file').first
                if name=='insert':
                    first_id=file.get_attribute('id');press('file');selected=entry('.file.selected')
                    return bool(first_id and selected.count()==1 and selected.evaluate('(e)=>e.previousElementSibling?.id')==first_id)
                if name=='focus':
                    first_id=file.get_attribute('id');press('file');press('del')
                    return bool(first_id and entry('.file').count()==1 and entry('.selected').count()==1 and entry('.selected').get_attribute('id')==first_id)
                if name=='reopen':
                    file.click();element_id=file.get_attribute('id')
                    editor=tab.locator('.editor').first
                    editor.fill('violet river');editor.press('Tab');press('file')
                    tab.locator('[id='+json.dumps(element_id)+']').click()
                    return editor.input_value()=='violet river'
                file.click(button='right')
                if name=='snapshot':
                    trace['tree']=tab.locator('.entries').first.evaluate('(e)=>e.outerHTML.slice(0,2000)')
                    trace['menu']=tab.locator('.menu').evaluate_all('(es)=>es.map(e=>e.outerHTML.slice(0,1800)).slice(0,2)')
                    trace['tools']=tab.locator('.tools').first.evaluate('(e)=>e.outerHTML.slice(0,1200)')
                    return True
                if name=='delete':
                    command('delete')
                    return entry().count()==0 and tab.locator('.menu:visible').count()==0
                responses.append('field-notes');command('rename')
                return any(t=='prompt' for t,_ in dialogs) and 'field-notes' in file.inner_text()
            for name in ('snapshot','insert','nest','focus','delete','rename','roundtrip','reopen'):
                try:
                    passed=bool(run(name))
                    if name!='snapshot':checked[name]=passed
                    if not passed or js_errors:errors[name]={'page_errors':list(js_errors),'dialogs':list(dialogs)}
                except Exception as exc:
                    if name!='snapshot':checked[name]=False
                    errors[name]={'error':str(exc).splitlines()[0][:180],'page_errors':list(js_errors),'dialogs':list(dialogs)}
    return {'checks':checked,'feedback':errors,'rendered':trace}
