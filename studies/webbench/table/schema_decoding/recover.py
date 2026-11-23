"""Resume an interrupted local GPU session with its frozen code, inputs and weights."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from . import generate as stage


def main():
    reg=stage.read(stage.OUT/'registered.json')
    assert stage.sha(Path(stage.__file__))==reg['generator_sha256']
    assert stage.sha(stage.HERE/'PROTOCOL.md')==reg['protocol_sha256']
    for path,checksum in reg['sources'].items():
        assert stage.sha(stage.ROOT/path)==checksum
    assert not (stage.OUT/'sealed.json').exists()
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    env=stage.read(stage.OUT/'environment.json')
    assert env['torch']==torch.__version__ and env['transformers']==transformers.__version__ and env['gpu']==torch.cuda.get_device_name(0)
    tokenizer=AutoTokenizer.from_pretrained(str(stage.SNAPSHOT),local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(str(stage.SNAPSHOT),local_files_only=True,trust_remote_code=False,
                                               dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
    hashes={}
    for n in range(1,21):
        for arm in stage.ARMS:
            out=stage.OUT/arm/f'task-{n}.json'
            if not out.exists():
                if datetime.now(timezone.utc)>=datetime(2026,11,23,6,12,tzinfo=timezone.utc):
                    raise TimeoutError('Registered inference deadline')
                host,pkg=stage.source(arm)
                prompt=host/'prompts'/f'task-{n}.json'
                assert stage.sha(prompt)==reg['sources'][str(prompt.relative_to(stage.ROOT))]
                messages=stage.read(prompt);schema=stage.read(pkg)['plan_schema']
                assert json.loads(messages[1]['content'])['plan_schema']==schema
                row=stage.infer(torch,tokenizer,model,messages,schema)
                assert row['decisions']
                stage.save(out,{**row,'task':n,'arm':arm,'complete':True,'model':stage.MODEL,'revision':stage.REVISION,
                                'prompt_sha256':stage.sha(prompt),'package_sha256':stage.sha(pkg),'utc':stage.now()})
            hashes[str(out.relative_to(stage.OUT))]=stage.sha(out)
        print('completed target',n,flush=True)
    stage.save(stage.OUT/'sealed.json',{'sealed':stage.now(),'registered_sha256':stage.sha(stage.OUT/'registered.json'),
               'environment_sha256':stage.sha(stage.OUT/'environment.json'),'response_sha256':hashes,'requests_to_remote_apis':0})


if __name__=='__main__':
    main()
