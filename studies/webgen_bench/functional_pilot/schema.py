"""The bounded AMIS language shared by the upstream and model-written renderers."""
import json
import re

FIELDS = {
    'page': 'title, body (node or array), data (initial key/value object)',
    'tabs': 'tabs: [{title,body}]; user chooses a tab',
    'container': 'body', 'panel':'title, body',
    'tpl':'tpl: plain text with optional ${field} substitution; no markup',
    'table':'columns:[{name,label}], source: ${rows} where page.data.rows is an array of records',
    'form':'title, body (array of inputs), actions (array of submit buttons), data; validate required fields before submitting',
    'input-text':'name,label,placeholder,required,value', 'input-number':'name,label,required,value',
    'textarea':'name,label,required,value','select':'name,label,options:[{label,value}],required,value',
    'checkbox':'name,label,option,value',
    'button':'label,level,actionType: dialog or toast, dialog:{title,body}, or msg; onEvent optional',
    'submit':'label,level',
    'dialog':'title,body',
}
SPEC = ("Return a single AMIS page JSON object, never a schema wrapper. Use these exact types and properties. "
        "Represent navigation by tabs. For details use actionType=dialog with dialog.title and dialog.body. "
        "Populate actual representative records and a real body for each section. For local feedback use "
        "onEvent:{click:{actions:[{actionType:'toast',args:{msg:'...'}}]}} or submitSucc in a form. "
        "A submit action may save values within the session. No other action types; no network, HTML, JS, "
        "expressions other than simple field substitutions, executable strings, or URLs. Body can be one node or a list.")
SAMPLE = {'type':'page','title':'Reading room','data':{'books':[{'name':'Local guide'}]},'body':[{'type':'tabs','tabs':[
    {'title':'Start','body':{'type':'tpl','tpl':'Local notices'}},
    {'title':'Workshop','body':[{'type':'table','source':'${books}','columns':[{'name':'name','label':'Book'}]},
    {'type':'button','label':'Read details','actionType':'dialog','dialog':{'title':'Shelf details','body':{'type':'tpl','tpl':'Shelf amber'}}},
    {'type':'form','title':'Entry','body':[{'type':'input-text','name':'nickname','label':'Nickname','required':True}],
     'actions':[{'type':'submit','label':'Save entry'}],
     'onEvent':{'submitSucc':{'actions':[{'actionType':'toast','args':{'msg':'Entry saved'}}]}}}]}]}]}
# Whitelist the configuration nodes before either source is compiled.
ALLOWED={'type','title','body','data','tabs','tpl','columns','name','label','source','actions','placeholder','required','value','options','option','level','actionType','dialog','msg','onEvent','click','submitSucc','args'}
def validate(value):
    if not isinstance(value,dict) or value.get('type')!='page':raise ValueError('Root must be a page node')
    count=0
    def visit(obj,role='node'):
        nonlocal count
        if isinstance(obj,list):
            for v in obj:visit(v,role)
            return
        if not isinstance(obj,dict):raise ValueError('Expected a JSON object or array for '+role)
        count+=1
        for k in obj:
            if k not in ALLOWED:raise ValueError('Unsupported property '+k[:60])
        for k,v in obj.items():
            if k=='type' and v not in FIELDS:raise ValueError('Unsupported component '+str(v)[:50])
            if k=='actionType' and v not in ('dialog','toast','submit'):raise ValueError('Unsupported action '+str(v)[:70])
            if k in ('body','tabs','columns','options','actions','click','submitSucc','dialog','args'):visit(v,k)
            if k=='onEvent':
                if not isinstance(v,dict) or not v.keys()<= {'click','submitSucc'}:raise ValueError('Only click and submitSucc events supported')
                for event in v.values():visit(event,'event')
        if role=='body' and 'type' not in obj:raise ValueError('Every body node needs type')
    visit(value)
    raw=json.dumps(value,ensure_ascii=False)
    if count>450 or len(raw)>100000:raise ValueError('Configuration exceeds size limit')
    if re.search(r'<\s*/?\s*[a-zA-Z]|javascript\s*:|https?://|(?i:__proto__|constructor\.prototype)|\$\{(?![a-zA-Z_][\w.]*\})',raw):
        raise ValueError('Only plain local content and simple field references are allowed')
    return value
