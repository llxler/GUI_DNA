"""Read-only input, page, schema and response audit of the new stages."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from gui_dna.provider import parse_json
from .core import (ROOT, PROJECTS, BUILDERS, PLANNERS, requirements, slug, digest,
                   dump, builder_messages, planner_messages, compile_plan)
from .schema import validate
from .analyze import used_response
from .generate import messages_for, output_files

BUILD = ROOT / 'artifacts/webbench-expand-build'
BASE = ROOT / 'artifacts/webbench-expand-run'


def main():
    checked_files = 0
    for stage in (BUILD, BASE):
        manifest = json.loads((stage / 'review-manifest.json').read_text())
        for name, sha in manifest['sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
            checked_files += 1
    packages, failures = {}, []
    for project in PROJECTS:
        for builder in BUILDERS:
            folder = BUILD / 'libraries' / project / slug(builder)
            assert json.loads((folder / 'messages.json').read_text()) == builder_messages(project)
            record = json.loads((folder / 'record.json').read_text())
            if record['status'] == 'frozen':
                package = json.loads((folder / 'package.json').read_text())
                assert digest(package) == record['package_sha256']
                packages[project, builder] = package
            else:
                failures.append(record)
    records, format_failures, checked_pages, matched_inputs, replay_differences = [], [], 0, 0, []
    finishes = Counter()
    for project in PROJECTS:
        for task in requirements(project)[1:]:
            for model in PLANNERS:
                jobs = [(None, 'free', None)] + [(builder, method, packages[project, builder])
                    for builder in BUILDERS if (project, builder) in packages for method in ('free_lib', 'plan')]
                for builder, method, package in jobs:
                    folder = BASE / 'runs' / project / (slug(builder) if builder else 'no_library') / slug(model) / method / task['id']
                    record = json.loads((folder / 'record.json').read_text())
                    records.append(record)
                    assert record['status'] == 'complete'
                    messages = json.loads((folder / 'messages.json').read_text())
                    assert messages == messages_for(project, task['id'], method, package)
                    if method == 'plan':
                        other = folder.parent.parent / 'free_lib' / task['id'] / 'messages.json'
                        assert messages[1] == json.loads(other.read_text())[1]
                        matched_inputs += 1
                    for attempt in record['attempts']:
                        index = attempt['attempt']
                        response = used_response(folder, index)
                        finishes[response['choices'][0]['finish_reason']] += 1
                        parsed = None
                        if method == 'plan':
                            try:
                                parsed = parse_json(response['choices'][0]['message']['content'])
                                validate(package['plan_schema'], parsed)
                            except (ValueError, TypeError, KeyError) as error:
                                format_failures.append({'project': project, 'builder': builder, 'model': model,
                                    'task': task['id'], 'attempt': index, 'error': str(error)[:500]})
                                assert f'version-{index}' not in record['versions']
                    for version in record['versions']:
                        page = folder / version
                        manifest = json.loads((page / 'source-manifest.json').read_text())
                        assert all(hashlib.sha256((page / name).read_bytes()).hexdigest() == sha for name, sha in manifest['files_sha256'].items())
                        index = version.removeprefix('version-')
                        raw = json.loads((folder / f'output-{index}.json').read_text())['text']
                        if digest(output_files(method, package, parse_json(raw))) != manifest['output_sha256']:
                            replay_differences.append({'candidate': str(folder.relative_to(ROOT)), 'version': version,
                                'scope': 'Saved source hashes verify, but regeneration differs; arbitrary code is not assumed deterministic.'})
                        checked_pages += 1
    barrier = json.loads((BASE / 'generation-complete.json').read_text())
    assert digest(records) == barrier['records_sha256']
    result = {'all_passed': True, 'frozen_hash_entries': checked_files,
              'records': len(records), 'checked_executable_versions': checked_pages,
              'matched_library_user_inputs': matched_inputs, 'used_response_finishes': dict(finishes),
              'failed_libraries': failures, 'rejected_plan_attempts': format_failures,
              'regeneration_differences': replay_differences,
              'scope': 'Saved source hashes verify; executable plans pass the closed schema; any regeneration differences listed separately. Not a semantic guarantee or heldout transfer.'}
    dump(ROOT / 'test/results/webbench-expand-audit.json', result)
    print(json.dumps({k: v if k != 'rejected_plan_attempts' else len(v) for k, v in result.items()}, indent=2))


if __name__ == '__main__':
    main()
