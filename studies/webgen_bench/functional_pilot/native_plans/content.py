"""Map a target's literal content and chosen interactions to the common component interface."""
from ..schema import validate

EXAMPLE={'title':'Reading room','sections':[{'title':'Workshop','intro':'Local notices','blocks':[
 {'kind':'detail','label':'Read details','text':'Shelf amber'},
 {'kind':'table','label':'Books','headers':['Book','Shelf'],'rows':[['Local guide','Amber']]},
 {'kind':'form','label':'Entry','fields':[{'name':'nickname','label':'Nickname','kind':'text','required':True}],'submit':'Save entry','feedback':'Entry saved'}]}]}
SPEC="""Complete one JSON document with title and sections. A section has title, intro and blocks.
A block is precisely one of {kind:'text',label,text}, {kind:'detail',label,text} (click to open),
{kind:'table',label,headers:[strings],rows:[[cell strings]]}, or {kind:'form',label,fields:[{name,label,kind,required,choices?}],submit,feedback}.
Form field kinds are text, number, multiline, choice or check. choice fields require a choices array of strings.
All content is plain text. Supply representative real rows, products, people, details and clearly named actions as the brief needs.
Use all necessary sections, maximum 12, about 1–4 blocks each. Provide no HTML, code, URLs, or schema wrappers.
Keep your whole JSON under 14000 characters. Describe the requested website, without discussing implementation."""
def text(d,k):
    v=d[k]
    if not isinstance(v,str) or not v.strip():raise ValueError(f'{k} must be nonempty text')
    return v
def sequence(d,k):
    a=d[k]
    if not isinstance(a,list):raise ValueError(f'{k} must be an array')
    return a
def compile_plan(plan):
    if not isinstance(plan,dict):raise ValueError('Expected a document')
    sections=sequence(plan,'sections')
    if not 1<=len(sections)<=12:raise ValueError('Expected 1 to 12 sections')
    data={};tabs=[]
    for i,section in enumerate(sections):
        title=text(section,'title');body=[]
        if section.get('intro'):body.append(dict(type='tpl',tpl=text(section,'intro')))
        for j,b in enumerate(sequence(section,'blocks')):
            label=text(b,'label');kind=text(b,'kind')
            if kind=='text':node=dict(type='panel',title=label,body={'type':'tpl','tpl':text(b,'text')})
            elif kind=='detail':node=dict(type='button',label=label,actionType='dialog',dialog={'title':label,'body':{'type':'tpl','tpl':text(b,'text')}})
            elif kind=='table':
                headers=sequence(b,'headers');rows=sequence(b,'rows')
                if not headers or not all(isinstance(h,str) for h in headers):raise ValueError('Expected string table headers')
                keys=[f'c{k}' for k in range(len(headers))]
                if any(not isinstance(r,list) or len(r)!=len(keys) or any(not isinstance(v,(str,int,float,bool)) for v in r) for r in rows):raise ValueError('Each data row must match its headers')
                key=f'table{i}x{j}';data[key]=[dict(zip(keys,r,strict=True)) for r in rows]
                node=dict(type='panel',title=label,body={'type':'table','columns':[{'name':k,'label':h} for k,h in zip(keys,headers,strict=True)],'source':'${'+key+'}'})
            elif kind=='form':
                inputs=[]
                for field in sequence(b,'fields'):
                    k=text(field,'kind')
                    names={'text':'input-text','number':'input-number','multiline':'textarea','choice':'select','check':'checkbox'}
                    if k not in names:raise ValueError('Unknown form field kind '+k)
                    row=dict(type=names[k],label=text(field,'label'),name=text(field,'name'),required=field.get('required',False))
                    if not isinstance(row['required'],bool):raise ValueError('required must be boolean')
                    if k=='choice':
                        choices=sequence(field,'choices')
                        if not all(isinstance(a,str) for a in choices):raise ValueError('Choices must be strings')
                        row['options']=[{'label':a,'value':a} for a in choices]
                    if k=='check':row['option']=row['label']
                    inputs.append(row)
                node=dict(type='form',title=label,body=inputs,actions=[{'type':'submit','label':text(b,'submit')}],
                          onEvent={'submitSucc':{'actions':[{'actionType':'toast','args':{'msg':text(b,'feedback')}}]}})
            else:raise ValueError('Unknown block kind '+kind)
            body.append(node)
        tabs.append(dict(title=title,body=body))
    return validate(dict(type='page',title=text(plan,'title'),data=data,body=[dict(type='tabs',tabs=tabs)]))
