"""Browser executor and independent state oracle; cases are explicit inputs."""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright
from test.interface_blind.core import Server, browser_env


def todo_snapshot(page):
    return page.locator('.todo-list li:visible').evaluate_all('''els => els.map(li => ({
      title: li.querySelector('label')?.textContent,
      completed: li.classList.contains('completed'),
      checked: li.querySelector('.toggle')?.checked ?? null
    }))''')


def todo_case(page, steps, capabilities):
    items, route, next_id = [], 'all', 1
    events = []
    def visible():
        return [x for x in items if route=='all' or x['completed']==(route=='completed')]
    def check():
        expected=[{'title':x['title'],'completed':x['completed'],'checked':x['completed'] if 'status' in capabilities else None} for x in visible()]
        # Extra controls are permitted; their presence does not add obligations
        # to a development scenario whose contract does not request them.
        actual=todo_snapshot(page)
        if 'status' not in capabilities:
            for x in actual:
                x['checked']=None
        assert actual==expected, {'expected_visible':expected,'actual_visible':actual}
        if 'status' in capabilities:
            assert page.locator('.todo-count strong').text_content().strip()==str(sum(not x['completed'] for x in items))
            if items:
                assert page.locator('#toggle-all').is_checked()==all(x['completed'] for x in items)
            assert page.locator('.clear-completed').is_visible()==any(x['completed'] for x in items)
        if 'views' in capabilities:
            assert page.locator('.main').is_visible()==bool(items)
            assert page.locator('.footer').is_visible()==bool(items)
    check()
    for step in steps:
        op=step['op']
        if op=='add':
            page.locator('.new-todo').fill(step['text'])
            page.locator('.new-todo').press('Enter')
            title=step['text'].strip()
            if title:
                items.append({'id':next_id,'title':title,'completed':False});next_id+=1
            assert page.locator('.new-todo').input_value()=='' or not title
        elif op in ('toggle','remove','edit','draft_reload'):
            row=visible()[step['index']]
            li=page.locator('.todo-list li:visible').nth(step['index'])
            if op=='toggle':
                li.locator('.toggle').click();row['completed']=not row['completed']
            elif op=='remove':
                li.hover();li.locator('.destroy').click();items.remove(row)
            else:
                li.locator('label').dblclick()
                editor=li.locator('.edit')
                assert editor.is_visible()
                assert editor.evaluate('e => e === document.activeElement')
                editor.fill(step['text'])
                end=step.get('end','Enter')
                if op=='draft_reload':
                    page.reload()
                elif end=='blur':
                    page.locator('.new-todo').click()
                else:
                    editor.press(end)
                if op!='draft_reload' and end!='Escape':
                    title=step['text'].strip()
                    if title:row['title']=title
                    else:items.remove(row)
        elif op=='route':
            route=step['value']
            name={'all':'All','active':'Active','completed':'Completed'}[route]
            page.locator('.filters').get_by_text(name,exact=True).click()
        elif op=='all':
            page.locator('#toggle-all').set_checked(step['value'])
            for x in items:x['completed']=step['value']
        elif op=='clear':
            page.locator('.clear-completed').click()
            items[:]=[x for x in items if not x['completed']]
        elif op=='reload':
            page.reload()
        else:
            raise ValueError(op)
        page.wait_for_timeout(40)
        check()
        events.append({'action':step,'visible':todo_snapshot(page)})
    return {'steps':len(steps),'events':events}


def row_snapshot(page):
    return page.locator('tbody').evaluate('''body => {
      const seen=window.__interactionReplayNodes || (window.__interactionReplayNodes=new Map());
      const changed=[];
      const rows=Array.from(body.querySelectorAll('tr')).map(tr => {
        const id=tr.dataset.id;
        if(seen.has(id) && seen.get(id)!==tr) changed.push(id);
        seen.set(id,tr);
        return {id:Number(id),display:tr.children[0]?.textContent.trim(),
          label:tr.children[1]?.querySelector('a')?.textContent,
          selected:tr.classList.contains('danger')};
      });
      return {rows,changed};
    }''')


def rows_case(page,steps,capabilities):
    rows, next_id, selected = [], 1, None
    events=[]
    def check():
        actual=row_snapshot(page)
        expected=[{**r,'display':str(r['id']),'selected':r['id']==selected} for r in rows]
        assert actual['rows']==expected, {'expected_count':len(expected),'actual_count':len(actual['rows']),
            'first_difference':next(((i,a,b) for i,(a,b) in enumerate(zip(expected,actual['rows'])) if a!=b),None)}
        assert not actual['changed'], {'changed_DOM_identities':actual['changed'][:12]}
    check()
    for step in steps:
        op=step['op']
        if op in ('run','runlots','add'):
            page.locator('#'+op).click()
            count=10000 if op=='runlots' else 1000
            new=[{'id':i,'label':f'Row {i}'} for i in range(next_id,next_id+count)]
            next_id+=count
            if op=='add':rows.extend(new)
            else:rows=new;selected=None
        elif op=='clear':
            page.locator('#clear').click();rows=[];selected=None
        elif op=='update':
            page.locator('#update').click()
            for i in range(0,len(rows),10):rows[i]['label']+=' !!!'
        elif op=='swap':
            page.locator('#swaprows').click()
            if len(rows)>=999:rows[1],rows[998]=rows[998],rows[1]
        elif op in ('select','remove'):
            row=rows[step['index']]
            tr=page.locator('tbody tr').nth(step['index'])
            if op=='select':
                tr.locator('td').nth(1).locator('a').click();selected=row['id']
            else:
                tr.locator('a.remove').click();rows.pop(step['index'])
                if selected==row['id']:selected=None
        else:raise ValueError(op)
        page.wait_for_timeout(40)
        check()
        events.append({'action':step,'rows':len(rows),'selected':selected,'ids_head':[r['id'] for r in rows[:3]]})
    return {'steps':len(steps),'events':events}


def evaluate(folder,project,cases):
    server=Server(Path(folder))
    reports=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(env=browser_env())
            for case in cases:
                context=browser.new_context()
                context.route('**/*',lambda route: route.continue_() if route.request.url.startswith(f'http://127.0.0.1:{server.port}/') else route.abort())
                page=context.new_page()
                page.set_default_timeout(2500)
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                try:
                    page.goto(f'http://127.0.0.1:{server.port}/index.html',timeout=10000)
                    result=(todo_case if project=='todos' else rows_case)(page,case['steps'],case.get('capabilities',[]))
                    assert not errors, {'page_errors':errors}
                    reports.append({'id':case['id'],'passed':True,**result})
                except Exception as error:
                    reports.append({'id':case['id'],'passed':False,'error':f'{type(error).__name__}: {error}'[:3500], 'page_errors':errors})
                finally:
                    context.close()
            browser.close()
    finally:
        server.close()
    return {'all_passed':bool(reports) and all(r['passed'] for r in reports),'passed':sum(r['passed'] for r in reports),
            'total':len(reports),'cases':reports,'failures':[r for r in reports if not r['passed']]}
