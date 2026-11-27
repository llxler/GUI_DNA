"""Independent input/output examples for the public TodoMVC controller signatures."""
def examples(first, second, title, other):
    rows=[dict(id=first,title=title,completed=False),dict(id=second,title=other,completed=True)]
    def state(todos, **updates):
        return dict(dict(todos=todos,nextId=second+1,filter='all',editing=None),**updates)
    def change(i, **kw):
        return [x|kw if j==i else x for j,x in enumerate(rows)]
    def event(name, **payload):
        return dict(type=name,**payload)
    def case(s,e,want,**kwargs):
        return dict(state=s,event=e,expected=want,**kwargs)
    s=state(rows)
    result={
      'init':[case(None,None,dict(todos=[],filter='all',editing=None),stored=[]),
              case(None,None,dict(todos=rows,filter='all',editing=None),stored=rows)],
      'persist':[case(s,None,rows)],
      'select':[],
      'add':[case(s,event('add',title='  '+title+' plus  '),rows+[dict(title=title+' plus',completed=False)],semantic='append'),
             case(s,event('add',title='   '),s)],
      'destroy':[case(s,event('destroy',id=first),state(rows[1:])),case(s,event('destroy',id=second),state(rows[:1]))],
      'toggle':[case(s,event('toggle',id=first),state(change(0,completed=True))),case(s,event('toggle',id=second),state(change(1,completed=False)))],
      'toggleAll':[case(s,event('toggleAll'),state(change(0,completed=True))),
                   case(state(change(0,completed=True)),event('toggleAll'),state(change(1,completed=False)))],
      'edit':[case(s,event('edit',id=first),state(rows,editing=first)),case(s,event('edit',id=second),state(rows,editing=second))],
      'save':[case(state(rows,editing=first),event('save',id=first,title='  Revised  '),state(change(0,title='Revised'))),
              case(state(rows,editing=second),event('save',id=second,title='   '),state(rows[:1]))],
      'cancel':[case(state(rows,editing=first),event('cancel',id=first,title='Draft'),s)],
      'clearCompleted':[case(s,event('clearCompleted'),state(rows[:1])),case(state(change(0,completed=True)),event('clearCompleted'),state([]))],
      'route':[case(s,event('route',filter='active'),state(rows,filter='active')),case(s,event('route',filter='completed'),state(rows,filter='completed'))],
    }
    for subset,active in [(rows,'all'),(rows,'completed'),(rows,'active'),([], 'all'),(change(0,completed=True),'all')]:
        count=sum(not x['completed'] for x in subset)
        visible=[x for x in subset if active=='all' or x['completed']==(active=='completed')]
        result['select'].append(case(state(subset,filter=active),None,dict(visible=visible,countText=str(count)+(' item left' if count==1 else ' items left'),
                allCompleted=bool(subset) and count==0,hasCompleted=any(x['completed'] for x in subset),hasTodos=bool(subset),editing=None,filter=active)))
    return result
