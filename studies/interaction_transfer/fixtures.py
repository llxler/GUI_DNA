"""Private trajectories and public short examples; never imported by generation."""
def action(op,**kwargs):return {'op':op,**kwargs}
def add(text):return action('add',text=text)
def at(op,index,**kwargs):return action(op,index=index,**kwargs)
def route(value):return action('route',value=value)

def case(name,steps,capabilities=()):return {'id':name,'steps':steps,'capabilities':list(capabilities)}


def public_cases(project,index):
    if project=='todos':
        return [
            [case('trim-and-empty',[add('  alpha  '),add('   '),add('beta'),at('remove',0)]),
             case('edit-commit-cancel',[add('alpha'),at('edit',0,text=' beta ',end='Enter'),at('edit',0,text='discard',end='Escape'),at('edit',0,text='gamma',end='blur'),at('edit',0,text='  ',end='Enter')])],
            [case('status-count',[add('a'),add('b'),at('toggle',0),action('all',value=True),action('clear')],('status','views')),
             case('route-membership',[add('a'),add('b'),route('active'),at('toggle',0),route('completed'),at('toggle',0),route('all')],('status','views'))],
            [case('save-and-restore',[add('a'),add('b'),at('toggle',1),action('reload'),at('remove',0),action('reload')])]
        ][index]
    return [
        [case('batch-create',[action('run'),action('run')]),case('append-clear',[action('run'),action('add'),action('clear')]),case('many',[action('runlots')])],
        [case('update',[action('run'),action('update'),action('update')]),case('empty-update',[action('update')])],
        [case('select-delete',[action('run'),at('select',5),at('remove',1),at('remove',4)]),case('swap',[action('run'),action('swap'),action('swap')])]
    ][index]


def heldout(project):
    if project=='todos':
        cap=('status','views')
        trajectories=[
          [add('same'),add('middle'),add('same'),at('toggle',0),route('active'),at('edit',1,text='renamed'),action('reload'),route('all')],
          [add('a'),add('b'),add('c'),at('toggle',0),route('active'),at('edit',0,text='  '),action('reload'),route('all')],
          [add('a'),add('b'),at('toggle',0),route('completed'),at('edit',0,text='renamed',end='blur'),action('reload'),route('active')],
          [add('a'),add('b'),at('toggle',0),route('active'),action('all',value=True),action('reload'),route('completed'),action('clear'),action('reload')],
          [add('a'),add('b'),add('c'),at('toggle',0),at('toggle',2),route('completed'),at('remove',0),action('reload'),route('all')],
          [add('a'),add('b'),at('toggle',1),route('active'),at('draft_reload',0,text='unsaved'),route('all')],
          [add('same'),add('same'),add('same'),at('toggle',1),route('completed'),at('edit',0,text='cancel',end='Escape'),at('toggle',0),action('reload'),route('all')],
          [add('a'),add('b'),route('active'),at('toggle',0),route('completed'),add('new'),action('reload'),route('active'),at('edit',1,text='newer'),route('all')],
          [add('a'),add('b'),action('all',value=True),route('completed'),at('edit',0,text=''),action('reload'),action('clear'),add('fresh'),action('reload')],
          [add('a'),add('b'),at('toggle',0),route('completed'),action('clear'),action('reload'),route('active'),at('edit',0,text=' B ',end='blur'),action('reload')],
          [add('first'),add('second'),at('edit',0,text='duplicate'),at('edit',1,text='duplicate'),at('toggle',0),route('active'),at('remove',0),action('reload'),route('completed')],
          [add('a'),add('b'),add('c'),action('all',value=True),route('completed'),at('toggle',1),route('active'),at('edit',0,text='changed'),action('reload'),route('all'),action('clear'),action('reload')]
        ]
        return [case(f'heldout-{i+1:02d}',steps,cap) for i,steps in enumerate(trajectories)]
    trajectories=[
      [action('run'),at('select',998),action('swap'),at('remove',0),action('update'),action('add')],
      [action('run'),at('remove',0),action('update'),at('select',9),action('swap'),action('update')],
      [action('run'),at('select',1),action('add'),action('update'),action('swap'),at('remove',998)],
      [action('run'),at('select',100),at('remove',99),at('remove',0),action('update'),action('swap')],
      [action('runlots'),at('select',9999),action('update'),action('add'),action('swap'),at('remove',9999)],
      [action('run'),action('update'),at('remove',10),action('update'),action('swap'),action('update')],
      [action('run'),at('select',1),action('clear'),action('add'),action('swap'),action('update'),at('select',1)],
      [action('run'),at('select',5),action('run'),action('update'),action('swap'),at('remove',1)],
      [action('add'),action('swap'),at('select',1),at('remove',998),action('update'),action('add')],
      [action('run'),at('remove',999),at('remove',998),action('swap'),action('update'),at('select',1),action('add'),action('swap')],
      [action('run'),at('select',998),action('swap'),action('swap'),at('remove',998),action('update'),action('add')],
      [action('run'),action('update'),action('add'),at('remove',0),action('update'),at('select',1998),action('clear'),action('run')]
    ]
    return [case(f'heldout-{i+1:02d}',steps) for i,steps in enumerate(trajectories)]
