"""Verify symmetric code delivery for the previously generated no-library baseline."""
import argparse
import hashlib
import json
import subprocess

from studies.study_io import ROOT, dump, now, read, sha
from .run import HERE, MODELS, OLD, ORIGINAL, OUT, RESULT, evaluate, inputs


def source_hash(source):
    return hashlib.sha256(source.encode()).hexdigest()


def sources():
    paths = [HERE/'direct.py', HERE/'direct.cjs', HERE/'DIRECT.md', OLD]
    return {str(path.relative_to(ROOT)): sha(path) for path in paths}


def seal():
    marker = OUT/'direct-control/seal.json'
    rows = {}
    tasks = inputs()
    for tag, model in MODELS.items():
        rows[model] = marked = {}
        original = {(r['task'], r['arm']): r for r in read(ORIGINAL/tag/'seal.json')['rows']}
        for task, info in tasks.items():
            record = original[task,'direct']
            folder = ORIGINAL/tag/'targets'/task/'direct'
            value = None
            if record['status'] == 'valid':
                assert sha(folder/'files.json') == record['files_sha256']
                value = read(folder/'files.json')[info['public']['module']+'.js']
            response = folder/'call/response.json'
            raw = read(response)['choices'][0]['message'].get('content') if response.exists() else None
            if response.exists():
                assert record['response_sha256'] == sha(response)
            output = subprocess.run(['node', str(HERE/'direct.cjs')], input=json.dumps({'original':value, 'raw':raw}),
                                    text=True, capture_output=True, check=True, cwd=ROOT)
            proposal = json.loads(output.stdout)
            row = marked[task] = {'original_status': record['status'],
                                  'original_source_sha256': source_hash(value) if value is not None else None,
                                  'response_sha256': sha(response) if response.exists() else None,
                                  'visible_characters': len(raw or '')}
            if proposal is None:
                row['disposition'] = 'no_alternative' if raw else 'no_visible_content'
            else:
                src = proposal['source']
                row.update(candidate_source_sha256=source_hash(src), format=proposal['kind'])
                if src == value:
                    row['disposition'] = 'identical'
                else:
                    row['disposition'] = 'recovered'
                    path = OUT/'direct-control/files'/tag/(task+'.json')
                    dump(path, {info['public']['module']+'.js': src})
                    row['candidate_sha256'] = sha(path)
    if marker.exists():
        previous = read(marker)
        assert previous['sources'] == sources() and previous['rows'] == rows
    else:
        dump(marker, {'sources': sources(), 'utc': now(), 'rows': rows})


def run():
    marker = OUT/'direct-control/seal.json'
    sealed = read(marker)
    assert sealed['sources'] == sources()
    tasks = inputs()
    old = read(OLD)['models']
    for tag, model in MODELS.items():
        by_task = {r['task']:r for r in old[model]['rows'] if r['arm'] == 'direct'}
        for task, row in sealed['rows'][model].items():
            before = by_task[task]
            row.update(original_passed=before['passed'], symmetric_passed=before['passed'],
                       report_sha256=before.get('report_sha256'))
            if row['disposition'] == 'recovered':
                path = OUT/'direct-control/files'/tag/(task+'.json')
                assert sha(path) == row['candidate_sha256']
                info = tasks[task]
                folder = OUT/'direct-control/scores'/tag/task
                verdict = evaluate.score((info['group'], info, read(path), folder, None))
                assert verdict['report_sha256'] == sha(folder/'jest.json')
                row.update(symmetric_passed=verdict['passed'], report_sha256=verdict['report_sha256'])
    dump(HERE/'direct-result.json', {**sealed, 'seal_sha256': sha(marker)})


def check():
    data = read(HERE/'direct-result.json')
    assert data['sources'] == sources()
    matrices = read(RESULT)['rows']
    assert set(matrices) == set(data['rows']) == set(MODELS.values())
    for model, rows in data['rows'].items():
        assert set(rows) == set(matrices[model])
        for task, row in rows.items():
            before = matrices[model][task]['direct']
            assert row['original_passed'] == before['passed']
            if row['disposition'] == 'recovered':
                assert row['candidate_source_sha256'] != row['original_source_sha256']
                assert row['report_sha256']
            else:
                assert row['symmetric_passed'] == before['passed'] and row['report_sha256'] == before.get('report_sha256')
        print(model, sum(r['symmetric_passed'] for r in rows.values()), '/',len(rows),
              'recovered',sum(r['disposition']=='recovered' for r in rows.values()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('register','score','check'))
    action = parser.parse_args().action
    {'register':seal,'score':run,'check':check}[action]()
