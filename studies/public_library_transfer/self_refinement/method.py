"""Public-only design, file generation, assembly and smoke probe."""
import html
import json
import re
import subprocess
from pathlib import PurePosixPath

from studies.public_library_transfer import browser, core

DESIGN = """Design the behavior library for these public GUI requirements. Read the starter and every revision carefully. Preserve existing markup and implement the named interfaces and UI interactions literally. Design a few meaningful finite controls for conflicting behaviors; keep stable functionality always available. The configuration is data, never task numbers, generated code or a target-to-page mapping. Every value is a string. Document what EACH option visibly does. Choose a first example up front. Decompose the implementation into coherent, independently writable JavaScript modules, the starter stylesheet, and the starter's JS entrypoint; honor publicly required local module names, imports, exports and class/method names. Define exact exports and call signatures so separate authors can implement them consistently. Plan persistent state, event ownership, DOM selectors, interactions and dependencies in these contracts. JS runs in the original starter HTML, may create DOM at runtime, and reads globalThis.APP_CONFIG. CSS may read html[data-dna-CONTROL="VALUE"]. Only relative local dependencies are available. Design a tiny observable interaction smoke check achievable in your first example on initial load. Return ONE JSON object: {"controls":[{"id":"...", "values":["...", "..."],"example":"...", "description":"..."}], "files":[{"path":"...", "role":"...", "api":"..."}], "smoke":{"selector":"CSS selector for existing event target", "event":"click|dblclick|contextmenu|input|change|mouseover", "visible":"CSS selector visible after event"}}. Include 1–8 controls, each 2–12 values, 2–16 named .js/.mjs/.css paths including the JS entry point. Do not write source code yet."""
AUTHOR = """Implement the entire requested local source file in a reusable interactive GUI library. Output just its raw source, with no prose. The manifest was designed by your team; obey the exact file interfaces and own every behavior assigned to this file. Preserve starter behaviors. Read public requirements literally, including DOM IDs/classes, state updates, styling, accessibility, labels, method names and event semantics, and make interactions compose. Use raw browser APIs and relative local imports. Do not invent dependencies, use task-number branches, fetch outside files, or select prebuilt pages. Use the data-only globalThis.APP_CONFIG; each option value is a STRING. CSS may read html[data-dna-CONTROL="VALUE"]. No tools. The supplied project and manifest are the entire specification."""
PLAN = """Configure this frozen GUI library for the last request in the supplied public sequence, keeping its prerequisites. Read what each option does and supply every field. The library is already implemented. Return only a JSON object mapping each control name to its selected string value, without explanation."""
FIX = """Fix the public browser/interaction issue in the given GUI package. Preserve the existing library controls, documented behavior and public requirements. You may replace only listed source files; no HTML edits or external dependencies. Return ONE JSON object {"files":[{"path":"...", "content":"complete replacement source"}]}. Include only files that need replacement, with the complete final contents. Do not use tools."""

def text_value(value):
    return str(value).lower() if isinstance(value, bool) else value

def source(raw):
    value = raw.strip()
    fenced = re.fullmatch(r'```[\w+-]*\s*\n([\s\S]*?)\n?\s*```', value)
    if fenced:
        value = fenced.group(1)
    if not value.strip():
        raise ValueError('Empty source file')
    return value

def manifest(raw, data):
    value = core.parse(raw)
    if not isinstance(value, dict):
        raise ValueError('Manifest must be an object')
    controls = value['controls']
    if not isinstance(controls, list) or not 1 <= len(controls) <= 8:
        raise ValueError('Expected one to eight controls')
    names = set()
    for c in controls:
        key = c['id']
        values = [text_value(v) for v in c['values']]
        example = text_value(c['example'])
        if (not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', key) or key in names
            or not 2 <= len(values) <= 12 or len(set(values)) != len(values)
            or not all(isinstance(v,str) and re.fullmatch(r'[\w .+-]{1,64}', v) for v in values)
            or example not in values or not isinstance(c['description'],str) or not c['description'].strip()):
            raise ValueError(f'Invalid control domain/documentation for {key!r}')
        c['values'], c['example'] = values, example
        names.add(key)
    entry = re.findall(r'<script\b[^>]*\bsrc=["\x27]([^"\x27]+)["\x27]',data['starter']['index.html'],flags=re.I)
    if len(entry)!=1:
        raise ValueError('Expected a unique public starter script')
    entry = str(PurePosixPath(entry[0]))
    files = value['files']
    if not isinstance(files,list) or not 2 <= len(files) <= 16:
        raise ValueError('Expected two to sixteen source files')
    paths=core.files_map([{'path':f['path'],'content':''} for f in files])
    if entry not in paths or any(not p.endswith(('.js','.mjs','.css')) for p in paths):
        raise ValueError(f'Expected named source files, including {entry}')
    for f in files:
        if not all(isinstance(f[k],str) for k in ('role','api')): raise ValueError('Describe all interfaces')
    smoke=value['smoke']
    if (smoke['event'] not in ('click','dblclick','contextmenu','input','change','mouseover')
        or not all(isinstance(smoke[k],str) and 0 < len(smoke[k]) <= 512 for k in ('selector','visible'))):
        raise ValueError('Invalid public smoke probe')
    return {'controls':controls,'files':files,'entry':entry,'smoke':smoke}

def plan(raw, spec):
    selected=core.parse(raw)
    if isinstance(selected,dict) and set(selected)=={'plan'} and 'plan' not in {c['id'] for c in spec['controls']}:
        selected=selected['plan']
    names=[c['id'] for c in spec['controls']]
    if isinstance(selected,list) and len(selected)==len(names):
        selected=dict(zip(names,selected))
    if not isinstance(selected,dict) or set(selected)!=set(names):
        raise ValueError('Configuration fields differ from the manifest')
    result={c['id']:text_value(selected[c['id']]) for c in spec['controls']}
    for c in spec['controls']:
        if result[c['id']] not in c['values']: raise ValueError('Configuration value outside the manifest')
    return result

def first(spec):
    return {c['id']: c['example'] for c in spec['controls']}

def emit(data, files, configuration, target):
    markup=data['starter']['index.html']
    attrs=''.join(f' data-dna-{key}="{html.escape(val,quote=True)}"' for key,val in configuration.items())
    markup,count=re.subn(r'<html\b',lambda m:m[0]+attrs,markup,count=1,flags=re.I)
    if not count: raise ValueError('Missing public html element')
    setup='<script>globalThis.APP_CONFIG='+json.dumps(configuration)+'</script>'
    markup,count=re.subn(r'(<head\b[^>]*>)',lambda m:m[0]+setup,markup,count=1,flags=re.I)
    if not count: raise ValueError('Missing public head element')
    return core.emit(data['project'],data['starter'] | files | {'index.html':markup},target)

PROBE = """
const {chromium} = require(process.argv[1]);
(async () => {
  const browser=await chromium.launch();
  try {
    const page=await browser.newPage();
    const probe=JSON.parse(process.argv[3]);
    await page.goto(process.argv[2]+'/index.html',{waitUntil:'networkidle',timeout:20000});
    const target=page.locator(probe.selector).first();
    await target.dispatchEvent(probe.event,{bubbles:true,cancelable:true,button:probe.event==='contextmenu'?2:0},{timeout:2200});
    await page.locator(probe.visible).first().waitFor({state:'visible',timeout:2200});
    process.stdout.write(JSON.stringify({passed:true}));
  } catch(e) {process.stdout.write(JSON.stringify({passed:false,detail:String(e).slice(0,1200)}));}
  finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
"""

def examine(data,spec,files,dest):
    digests=emit(data,files,first(spec),dest)
    project=data['project']
    errors=browser.public_load(project,dest)
    probe=None
    if not errors:
        _, runtime, _=browser.contract(project)
        with browser.serve(project,dest) as url:
            result=subprocess.run(['node','-e',PROBE,str(runtime/'node_modules/@playwright/test'),url,json.dumps(spec['smoke'])],
                                  env=browser.browser_env(),capture_output=True,text=True,timeout=60,check=True)
        probe=json.loads(result.stdout)
    return {'load_errors':errors,'probe':probe,'files':digests}
