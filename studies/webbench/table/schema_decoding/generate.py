"""Score legal token continuations with a frozen causal LM while emitting closed JSON."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/schema-constrained-table-20261123'
BASE = ROOT/'artifacts/public-controller-table-20261123'
OLD = ROOT/'artifacts/compatible-table-local-plans-20261123'
REVISION = '7ae557604adf67be50417f59c2c2f167def9a775'
MODEL = 'Qwen/Qwen2.5-0.5B-Instruct'
SNAPSHOT = Path.home()/'.cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B-Instruct/snapshots'/REVISION
ARMS = ('original','rep-1','rep-2')


def read(path):
    return json.loads(path.read_text())


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    temp.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def source(arm):
    if arm=='original':
        return OLD,ROOT/'artifacts/webbench-expand-build/libraries/table/openai__gpt-5/package.json'
    return BASE/arm/'planning',BASE/arm/'package.json'


def infer(torch, tokenizer, model, messages, schema):
    tokens=tokenizer.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,
                                         return_dict=True,return_tensors='pt')['input_ids'].to(model.device)
    cache=None
    scores=None
    output=[]
    branches=[]

    def forward(ids):
        nonlocal cache,scores
        with torch.inference_mode():
            state=model.model(input_ids=ids,past_key_values=cache,use_cache=True)
            cache=state.past_key_values
            scores=model.lm_head(state.last_hidden_state[:,-1:])[0,0].float()

    def append(ids):
        if ids:
            output.extend(ids)
            forward(torch.tensor([ids],device=model.device))

    def emit(fragment):
        append(tokenizer.encode(fragment,add_special_tokens=False))

    def visit(node,path):
        kind=node['type']
        if kind=='object':
            emit('{')
            for i,(key,child) in enumerate(node['properties'].items()):
                emit((',' if i else '')+json.dumps(key)+':')
                visit(child,path+'.'+key)
            emit('}')
            return
        values=[True,False] if kind=='boolean' else node['enum']
        if kind not in ('string','boolean'):
            raise ValueError('Unregistered schema type '+kind)
        continuations=[tokenizer.encode(json.dumps(v),add_special_tokens=False) for v in values]
        while any(continuations):
            if not all(continuations):
                raise ValueError('Ambiguous terminal tokenization')
            edges=sorted({seq[0] for seq in continuations})
            if len(edges)>1:
                logits=scores[edges].tolist()
                assert all(__import__('math').isfinite(x) for x in logits)
                token=edges[max(range(len(edges)),key=lambda i:logits[i])]
                branches.append({'field':path,'tokens':edges,'logits':logits,'selected':token})
            else:
                token=edges[0]
            append([token])
            continuations=[seq[1:] for seq in continuations if seq[0]==token]

    forward(tokens)
    visit(schema,'$')
    raw=tokenizer.decode(output,skip_special_tokens=False,clean_up_tokenization_spaces=False)
    return {'response':raw,'plan':json.loads(raw),'input_tokens':tokens.shape[-1],'generated_token_ids':output,
            'input_token_ids_sha256':hashlib.sha256(json.dumps(tokens[0].tolist(),separators=(',',':')).encode()).hexdigest(),
            'decisions':branches}


def main():
    if OUT.exists():
        raise SystemExit('This registered stage already exists')
    evidence={}
    for arm in ARMS:
        host,pkg=source(arm)
        inputs=[pkg,host/'local-inputs.json',host/'registered.json',*[host/'prompts'/f'task-{n}.json' for n in range(1,21)]]
        evidence.update({str(p.relative_to(ROOT)):sha(p) for p in inputs})
    save(OUT/'registered.json',{'registered':now(),'arms':ARMS,'protocol_sha256':sha(HERE/'PROTOCOL.md'),
         'generator_sha256':sha(Path(__file__)),'model':MODEL,'revision':REVISION,'sources':evidence})
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(str(SNAPSHOT),local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(str(SNAPSHOT),local_files_only=True,trust_remote_code=False,
                                               dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
    save(OUT/'environment.json',{'model':MODEL,'revision':REVISION,'torch':torch.__version__,
         'transformers':transformers.__version__,'gpu':torch.cuda.get_device_name(0),
         'weights_sha256':read(OLD/'local-inputs.json')['model_files_sha256'],'dtype':'float16','attention':'sdpa'})
    hashes={}
    for n in range(1,21):
        for arm in ARMS:
            if datetime.now(timezone.utc)>=datetime(2026,11,23,6,12,tzinfo=timezone.utc):
                raise TimeoutError('Registered inference deadline')
            host,pkg=source(arm)
            prompt=host/'prompts'/f'task-{n}.json'
            messages=read(prompt)
            schema=read(pkg)['plan_schema']
            assert json.loads(messages[1]['content'])['plan_schema']==schema
            assert sha(prompt)==evidence[str(prompt.relative_to(ROOT))] and sha(pkg)==evidence[str(pkg.relative_to(ROOT))]
            row=infer(torch,tokenizer,model,messages,schema)
            assert row['decisions']
            path=OUT/arm/f'task-{n}.json'
            save(path,{**row,'task':n,'arm':arm,'complete':True,'model':MODEL,'revision':REVISION,
                       'prompt_sha256':sha(prompt),'package_sha256':sha(pkg),'utc':now()})
            hashes[str(path.relative_to(OUT))]=sha(path)
        print('completed target',n,flush=True)
    save(OUT/'sealed.json',{'sealed':now(),'registered_sha256':sha(OUT/'registered.json'),'environment_sha256':sha(OUT/'environment.json'),
         'response_sha256':hashes,'requests_to_remote_apis':0})


if __name__=='__main__':
    main()
