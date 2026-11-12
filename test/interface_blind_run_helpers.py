"""Generation helper for the stronger preloaded-library baseline."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path
from gui_dna.budget import BudgetStop
from gui_dna.provider import ProviderError, parse_json
from test.interface_blind.core import (SEED, compile_plan, digest, dump, planner_messages, public_check, slug, write_files)


def output_files(method, package, parsed):
    if method == 'plan':
        return compile_plan(package, parsed)
    if not isinstance(parsed.get('files'), dict):
        raise ValueError('files must be a JSON object')
    if method == 'free_lib':
        return {**package['files'], **parsed['files']}
    return parsed['files']


def candidate(client, out, project, builder, model, method, task, package):
    folder = out / 'runs' / project / (slug(builder) if builder else 'no_library') / slug(model) / method / task
    target = folder / 'record.json'
    if target.exists():
        return json.loads(target.read_text())
    messages = planner_messages(project, task, method, package)
    if method == 'free_lib':
        messages[0]['content'] = ('Implement the complete website using unrestricted JavaScript. '
            'All files in the supplied library file map are ALREADY PRESENT at their listed paths. '
            'You may import/call them directly, or replace any file to adapt or ignore the library. '
            'Return JSON only: {"files": {"index.html": "...", "new-or-modified/path.js": "..."}}. '
            'Return ONLY files you create or change. Do NOT copy unchanged library files into the output. '
            'Unspecified library files are inherited verbatim. You still own the complete page and its event bindings.')
    dump(folder / 'messages.json', messages)
    record = {'project': project, 'builder': builder, 'model': model, 'method': method, 'task': task,
              'package_sha256': digest(package) if package else None, 'attempts': [], 'versions': [], 'status': 'complete'}
    for attempt in range(3):
        try:
            raw = client.call(model, messages, folder / f'call-{attempt}', f'plan-interface-blind:{method}', seed=SEED)
        except BudgetStop:
            raise
        except ProviderError as error:
            record.update(status='transport_incomplete', error=str(error))
            break
        dump(folder / f'output-{attempt}.json', {'text': raw})
        try:
            parsed = parse_json(raw)
            files = output_files(method, package, parsed)
            version = f'version-{attempt}'
            write_files(folder / version, files)
            record['versions'].append(version)
            dump(folder / version / 'source-manifest.json', {'files_sha256': {n: hashlib.sha256(v.encode()).hexdigest() for n, v in files.items()}, 'output_sha256': digest(files)})
            feedback = public_check(folder / version)
        except (ValueError, KeyError, TypeError, TimeoutError, subprocess.TimeoutExpired) as error:
            feedback = [str(error)[:1600]]
        record['attempts'].append({'attempt': attempt, 'feedback': feedback})
        if not feedback:
            break
        messages += [{'role': 'assistant', 'content': raw},
                     {'role': 'user', 'content': 'Public format/compiler/load feedback:\n' + '\n'.join(feedback) + '\nReturn the full corrected JSON output.'}]
    dump(target, record)
    print(f'{project} {builder or "none"} {model} {method} {task}: {record["status"]}, versions={len(record["versions"])}', flush=True)
    return record

