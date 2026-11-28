"""A finite JSON interface for forms and resource actions; all executable behavior lives in the host and SDK."""
import json
import re

FORMAT = """One JSON object: {"defaults":{},"onMount":false,"fields":[{"name":"aField","type":"text","label":"visible field label","placeholder":"","testId":"","initial":"","options":[]}],"actions":[{"label":"button text","testId":"","method":"POST","url":"/path/{props.id}","body":{"someKey":"{values.aField}"},"success":"visible success or {data.someKey}","error":"visible error","output":[]}]}. defaults defines fallback resource props. For selects, options is a list of {"value":"...", "label":"..."}. Include all genuine user actions. Empty label is allowed for an onMount GET. output may contain additional strings with {data.key}, {props.key} or {values.key}; indexed paths such as {data.items.0.name} work. Values can be interpolated within strings or passed through as a whole. All requests use the specified method and form values. Unknown keys or script code are disallowed. Fields can use type text, textarea, number, date, url, email or select. Omit unused optional properties. A label that repeats a button can instead be a placeholder when required by the brief."""

def parse(raw):
    text=raw.strip()
    fenced=re.fullmatch(r"```(?:json)?\s*\n?([\s\S]*?)\n?```",text)
    obj=json.loads(fenced[1] if fenced else text)
    def keys(record,allowed):
        if not isinstance(record,dict) or set(record)-set(allowed.split()):
            raise ValueError("Unknown keys or object expected")
    def scalar(x):return isinstance(x,(str,int,float,bool)) or x is None
    def text_values(record,names):
        if any(k in record and not isinstance(record[k],str) for k in names.split()):
            raise ValueError("Expected strings for labels, IDs and messages")
    keys(obj,"fields actions defaults onMount")
    fields,actions=obj.get("fields",[]),obj.get("actions")
    if not isinstance(fields,list) or len(fields)>12 or not isinstance(actions,list) or not 1<=len(actions)<=8:
        raise ValueError("Expected fields and one to eight actions")
    if not isinstance(obj.get("onMount",False),bool) or not isinstance(obj.get("defaults",{}),dict) or not all(scalar(x) for x in obj.get("defaults",{}).values()):
        raise ValueError("Invalid initial values")
    for f in fields:
        keys(f,"name type label placeholder testId initial options")
        if not isinstance(f.get("name"),str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*",f["name"]) or f.get("type","text") not in ("text","textarea","number","date","url","email","select"):
            raise ValueError("Invalid field identifier or type")
        text_values(f,"label placeholder testId")
        if not scalar(f.get("initial")) or not isinstance(f.get("options",[]),list):raise ValueError("Invalid field defaults")
        for option in f.get("options",[]):
            keys(option,"value label")
            if not scalar(option.get("value")) or not isinstance(option.get("label"),str):raise ValueError("Use value and label for each option")
    if len({f["name"] for f in fields})!=len(fields):raise ValueError("Duplicate field name")
    for a in actions:
        keys(a,"label testId method url body success error output")
        text_values(a,"label testId method url success error")
        if a.get("method") not in ("GET","POST","PUT","PATCH","DELETE") or not re.match(r"^/(?!/)",a.get("url","")):
            raise ValueError("Use a relative URL and an HTTP method")
        if not isinstance(a.get("body",{}),dict) or not all(scalar(v) for v in a.get("body",{}).values()):
            raise ValueError("Provide a flat request-body mapping")
        if not isinstance(a.get("output",[]),list) or not all(isinstance(x,str) for x in a.get("output",[])):
            raise ValueError("output must be a list of display strings")
    return dict(obj,fields=fields,actions=actions)
