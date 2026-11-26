"""Use pinned WebVoyager prompts, visual labels and parsing on local Playwright pages."""
import ast
import re

from . import pages

SOURCE=pages.UP/'evaluator'
UI=SOURCE/'src/ui_test_webgen/ui_eval_with_answer.py'
OPERATOR=SOURCE/'webvoyager/run.py'
UTILS=SOURCE/'webvoyager/utils.py'
PROMPTS=SOURCE/'webvoyager/prompts.py'
def select_source(file,names):
    tree=ast.parse(file.read_text());items=[]
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in names:items.append(node)
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in names:items.append(node)
    env={'re':re}
    assert len(items)==len(names)
    exec(compile(ast.Module(items,type_ignores=[]),str(file),'exec'),env)
    return env
FUNCTIONS=select_source(UTILS,{'get_web_element_rect','extract_information','clip_message_and_obs'})
PROMPT=select_source(PROMPTS,{'SYSTEM_PROMPT'})['SYSTEM_PROMPT']
TEMPLATE=select_source(UI,{'ui_prompt_template'})['ui_prompt_template']
FORM=select_source(OPERATOR,{'format_msg','ui_limit_prompt_template'})
class Element:
    def __init__(self,attrs):self.attrs=attrs;self.tag_name=attrs['tag']
    def get_attribute(self,key):return self.attrs.get(key)

class Labels:
    def __init__(self,tab):self.tab=tab
    def execute_script(self,src):
        js="""() => {const [labels,items]=(function(){"""+src+"""})(); window.__wgLabels=labels;
        window.__wgItems=items.map(i=>i.element);
        return items.map(i=>({text:i.text,attrs:{tag:i.element.tagName.toLowerCase(),type:i.element.getAttribute('type'),
          'aria-label':i.element.getAttribute('aria-label')}}));}"""
        rows=self.tab.evaluate(js)
        return [],[{'element':Element(x['attrs']),'text':x['text']} for x in rows]
    def observe(self):return FUNCTIONS['get_web_element_rect'](self,fix_color=True)[2]
    def clear(self):self.tab.evaluate('()=>{for(const e of window.__wgLabels||[])e.remove()}')
    def act(self,key,info):
        if key not in ('click','type','scroll','wait','goback'):raise ValueError('Unsupported or non-local action')
        if key=='wait':self.tab.wait_for_timeout(1000);return
        if key=='goback':self.tab.go_back(wait_until='domcontentloaded',timeout=3000);return
        index=str(info[0] if key=='click' else info['number'])
        if key=='scroll' and index=='WINDOW':
            self.tab.mouse.wheel(0,(1 if info['content']=='down' else -1)*510);return
        if not index.isdigit() or len(index)>4:raise ValueError('Invalid labeled element')
        handle=self.tab.evaluate_handle('i=>window.__wgItems?.[i]',int(index))
        try:
            el=handle.as_element()
            if not el:raise ValueError('No matching page element')
            if key=='click':el.click(timeout=1800)
            elif key=='type':
                el.fill(info['content'],timeout=1800);el.press('Enter',timeout=1800)
            elif key=='scroll':
                el.evaluate('(e,step)=>e.scrollBy(0,step)',510 if info['content']=='down' else -510)
        finally:handle.dispose()

def final_answer(s):
    pattern=r'(?:\bANSWER\s*[;:]\s*)?\[?\s*(YES|NO|PARTIAL)\s*\]?[.!]?'
    match=re.fullmatch(pattern,s.strip(),flags=re.I)
    return match[1].upper() if match else None
