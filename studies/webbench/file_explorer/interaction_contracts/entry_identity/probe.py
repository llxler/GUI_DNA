"""Track the actual newly created entry across the user's subsequent actions."""
import json
import re
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser
from studies.study_io import ROOT


def observe(out,candidate):
    path=browser.served_page(out,'dom1',ROOT/candidate['page'],candidate['files'])
    checks,feedback,trace={},{},{}
    with browser.browser_slot(),browser.serve('dom1',path) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng:
        tab=eng.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        tab.set_default_timeout(1200)
        responses,dialogs,errors=[],[],[]
        def reply(d):
            dialogs.append([d.type,d.message[:1800]])
            d.accept(responses.pop(0) if d.type=='prompt' and responses else None)
        tab.on('dialog',reply)
        tab.on('pageerror',lambda e:errors.append(str(e)[:180]))
        entries=tab.locator('.entries .entry')
        def button(name):return tab.get_by_role('button',name=re.compile('^'+name+'$',re.I)).first
        def command(name):return tab.locator('.menu:visible .menu-item-'+name+':visible').first
        def ids():return entries.evaluate_all('(es)=>es.map(e=>e.id)')
        def by_id(key):return tab.locator('[id='+json.dumps(key)+']')
        def create(kind):
            before=set(ids());button(kind).click();after=set(ids())
            new=after-before
            if len(new)!=1 or '' in new:raise ValueError(f'{kind} added {len(new)} distinct new ids')
            return new.pop()
        def root_space():
            # A physical mouse click in the panel outside any child entry clears selection if space exists.
            pos=tab.locator('.entries').first.evaluate('''e=>{const b=e.getBoundingClientRect();for(let y=b.bottom-4;y>b.top;y-=12)for(let x=b.right-4;x>b.left;x-=16)if(document.elementFromPoint(x,y)===e)return [x,y];return null}''')
            if pos:tab.mouse.click(*pos)
        def reset():
            dialogs.clear();errors.clear();responses.clear()
            tab.goto(url+'/index.html',wait_until='load')
            root_space()
        def run(name):
            reset()
            if name=='roundtrip':
                expected={'entries':[{'type':'dir','name':'paper-folder','children':[{'type':'file','name':'leaf','content':'violet'}]}]}
                responses.append(json.dumps(expected));button('imp').click()
                loaded=tab.locator('.entries .dir .dir-content .file').count()==1
                button('exp').click()
                outputs=[json.loads(msg) for t,msg in dialogs if t=='alert' and msg.lstrip().startswith('{')]
                def tree(nodes):
                    return [(v.get('type'),v.get('name'),v.get('content') if v.get('type')=='file' else tree(v.get('children',[]))) for v in nodes]
                return bool(loaded and outputs and tree(outputs[-1]['entries'])==tree(expected['entries']))
            if name in ('nest','menu_child'):
                folder=create('dir')
                if name=='nest':
                    child=create('file')
                    return by_id(child).evaluate('(e)=>[e.parentElement.closest(".entry")?.id,e.classList.contains("selected")]')==[folder,True]
                before=set(ids());by_id(folder).click(button='right');command('add-file').click();diff=set(ids())-before
                return len(diff)==1 and by_id(diff.pop()).evaluate('(e)=>e.parentElement.closest(".entry")?.id')==folder
            fid=create('file');file=by_id(fid)
            if name=='snapshot':
                trace['initial_count']=len(ids())-1
                trace['file']=file.evaluate('(e)=>e.outerHTML.slice(0,450)')
                trace['parent']=file.evaluate('(e)=>e.parentElement.outerHTML.slice(0,1100)')
                trace['tools']=tab.locator('.tools').first.evaluate('(e)=>e.outerHTML.slice(0,950)')
                trace['visible']=file.is_visible()
                file.click(button='right')
                trace['menu']=tab.locator('.menu').evaluate_all('(es)=>es.slice(0,2).map(e=>e.outerHTML.slice(0,1300))')
                return True
            if name=='insert':
                second=create('file')
                return by_id(second).evaluate('(e)=>[e.previousElementSibling?.id,e.classList.contains("selected")]')==[fid,True]
            if name=='focus':
                second=create('file');button('del').click()
                return by_id(second).count()==0 and file.count()==1 and file.evaluate('e=>e.classList.contains("selected")')
            if name=='reopen':
                file.click();editor=tab.locator('.editor').first;editor.fill('violet river');editor.press('Tab')
                create('file');file.click()
                return editor.input_value()=='violet river'
            file.click(button='right')
            if name=='delete':
                command('delete').click()
                return file.count()==0 and tab.locator('.menu:visible').count()==0
            if name=='rename':
                responses.append('field-notes');command('rename').click()
                return any(t=='prompt' for t,_ in dialogs) and 'field-notes' in file.inner_text()
            same_content=file.get_attribute('data-content');command('copy').click()
            root_space();folder=create('dir');by_id(folder).click(button='right');command('paste').click()
            return bool(same_content and same_content in by_id(folder).locator('.dir-content .file').evaluate_all('(es)=>es.map(e=>e.dataset.content)'))
        for name in ('snapshot','insert','focus','nest','menu_child','delete','rename','copy','reopen','roundtrip'):
            try:
                ok=bool(run(name))
                if name!='snapshot':checks[name]=ok
                if not ok or errors:feedback[name]={'errors':list(errors),'dialogs':list(dialogs)}
            except Exception as exc:
                if name!='snapshot':checks[name]=False
                feedback[name]={'error':str(exc).splitlines()[0][:180],'errors':list(errors),'dialogs':list(dialogs)}
    return dict(checks=checks,feedback=feedback,rendered=trace)
