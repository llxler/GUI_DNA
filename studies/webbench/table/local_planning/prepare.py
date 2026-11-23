"""Freeze identical per-target inputs for independent source-blind table planning."""
import json
from pathlib import Path
from studies.compatible_library_rebuild.build import OUT as BUILD
from studies.study_io import ROOT, dump, now, read, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/compatible-table-local-plans-20261123'


def prepare():
    protocol = HERE / 'PROTOCOL.md'
    public = read(BUILD / 'public.json')
    inputs = {}
    for index in range(1,21):
        brief = {'requirements': public['requirements'][:index+1], 'starter':public['starter'],
                 'plan_schema':public['plan_schema'], 'documentation':public['plan_documentation'],
                 'examples':public['examples']}
        messages = [
            {'role':'system','content':'Select a valid configuration for the requested behaviors. Return only one JSON object matching the closed plan_schema. Use the keys directly at the root, with no wrapper, code, tools or explanation.'},
            {'role':'user','content':json.dumps(brief,ensure_ascii=False)}]
        dest = OUT / 'prompts' / f'task-{index}.json'
        if dest.exists() and read(dest) != messages:
            raise ValueError('Frozen prompt differs')
        if not dest.exists():
            dump(dest,messages)
        inputs[dest.name] = sha(dest)
    manifest=OUT/'registered.json'
    if manifest.exists():
        assert read(manifest)['prompt_sha256'] == inputs
    else:
        dump(manifest,{'at':now(),'model':'Qwen/Qwen2.5-0.5B-Instruct','source':sha(BUILD/'public.json'),
                       'prompt_sha256':inputs,'protocol':sha(protocol),'source_sha256':sha(Path(__file__))})


if __name__ == '__main__':
    prepare()
