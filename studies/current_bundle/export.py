"""Build a new local archive with current report inputs and browser evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

from studies.canvas_capacity.run import OUT as SECOND
from studies.canvas_model_replication.run import OUT as SONNET
from studies.matched_canvas.browser import OUT as FIRST, PROJECT
from studies.matched_flex.run import OUT as FLEX
from studies.study_io import ROOT, read, sha

STAGES = {'scheduled': FIRST, 'capacity_followup': SECOND, 'model_replication': SONNET, 'flex': FLEX}


def portable_suite(suite):
    """Keep assertion outcomes, withholding command lines, errors and traces."""
    return {'specs': [
        {'file': Path(spec['file']).name, 'title': spec['title'],
         'tests': [{'results': [{'status': attempt['status']} for attempt in test['results']]}
                   for test in spec['tests']]}
        for spec in suite.get('specs', [])],
        'suites': [portable_suite(child) for child in suite.get('suites', [])]}


def build(destination):
    view = read(ROOT/'studies/results/end_to_end.json')
    data = {}

    def put(name, path):
        data[name] = path.read_bytes()

    for name in [*view['source_sha256'], 'studies/end_to_end.py', 'studies/results/end_to_end.json',
                 'studies/study_io.py', 'studies/__init__.py', 'studies/canvas_capacity/__init__.py',
                 'studies/canvas_capacity/summarize.py']:
        put(name, ROOT/name)
    for name in ('__init__.py', 'study_io.py', 'end_to_end.py'):
        put('test/'+name, ROOT/'studies'/name)
    for study in ('matched_canvas','canvas_capacity','matched_flex','canvas_model_replication',
                  'canvas_fixed_reuse','canvas_interface_probe','table_behavior_probe','input_controls',
                  'canvas_speed_probe'):
        name = f'studies/{study}/PROTOCOL.md'
        put(name, ROOT/name)
    folder = Path(__file__).resolve().parent
    for name in ('verify.py','README.md'):
        put(name, folder/name)

    evidence = {}
    def put_report(label, stage, section, key, row):
        raw = stage/section/key/'report.json'
        assert sha(raw) == row['report_sha256']
        name = f'evidence/{label}/{section}/{key}.json'
        if name not in evidence:
            report = {'suites':[portable_suite(s) for s in read(raw)['suites']]}
            data[name] = json.dumps(report,indent=2).encode()
            evidence[name] = {'source_sha256':sha(raw),'study':label,'key':key,'section':section}

    studies = {**view['canvas_pilots'], 'flex':view['matched_flex']}
    for label,stage in STAGES.items():
        study = studies[label]
        for section, group in [('calibration',study['calibration']),('scores',study['rows'])]:
            for key,row in group.items():
                if row.get('report_sha256'):
                    put_report(label,stage,section,key,row)
    for label,filename in [('scheduled','canvas-fixed-reuse-20261118'),
                           ('capacity_followup','canvas-capacity-20261118-reuse'),
                           ('model_replication','canvas-sonnet-20261118-reuse')]:
        for row in read(ROOT/'studies/results'/f'{filename}.json')['rows']:
            if row.get('report_sha256'):
                put_report(label,STAGES[label],'scores',row['report'],row)
    for key,row in view['input_controls']['official'].items():
        put_report('input-controls',ROOT/'artifacts/input-controls-20261118','scores',key,row)
    data['evidence.json'] = json.dumps(evidence,indent=2).encode()
    for study,name,field in [('table-behavior-probe-20261118','observations.json','observations_sha256'),
                             ('canvas-speed-probe-20261118','traces.json','traces_sha256')]:
        path = ROOT/'artifacts'/study/name
        assert sha(path) == read(ROOT/'studies/results'/f'{study}.json')[field]
        put('diagnostics/'+study+'/'+name,path)

    runtime = ROOT/'artifacts/webbench-expand-runtime-157'
    for name in ('package.json','package-lock.json','test-util/index.js','test-util/css.js','test-util/package.json'):
        put('smoke/'+name,runtime/name)
    put('smoke/test/task-4.spec.js',PROJECT/'test/task-4.spec.js')
    put('smoke/test/task-20.spec.js',PROJECT.parent/'flex/test/task-20.spec.js')
    put('smoke/playwright.config.cjs',FIRST/'harness/157-canvas/playwright.config.cjs')
    assert sha(FIRST/'harness/157-canvas/playwright.config.cjs') == sha(FLEX/'harness/157-flex/playwright.config.cjs')
    put('smoke/Web-Bench-LICENSE.md',PROJECT.parents[1]/'LICENSE.md')
    selected = view['canvas_pilots']['scheduled']['rows']['free-1/task-4']
    pages = {'canvas/candidate':ROOT/selected['page'], 'canvas/reference':FIRST/'controls/reference',
             'canvas/blank':FIRST/'controls/blank', 'flex/reference':FLEX/'controls/reference', 'flex/blank':FLEX/'controls/blank'}
    for arm in ('free','plan'):
        pages['flex/'+arm] = ROOT/view['matched_flex']['rows'][arm+'-1/task-20']['page']
    for name,path in pages.items():
        for source in path.rglob('*'):
            if source.is_file():
                put('smoke/pages/'+name+'/'+source.relative_to(path).as_posix(),source)

    private = re.compile(rb'/home/[\w.-]+/|sk-(?:or-v1-|proj-)[A-Za-z0-9_-]{12,}|Bearer sk-|gen-[0-9]{6,}|llxler', re.I)
    for name, payload in data.items():
        if not name.endswith('.png') and private.search(payload):
            raise ValueError(f'Private identifier in {name}')
    hashes = {name:hashlib.sha256(payload).hexdigest() for name,payload in data.items()}
    data['manifest.json'] = json.dumps(hashes,indent=2).encode()
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as archive:
        for name,payload in sorted(data.items()):
            archive.writestr(name,payload)
    print(len(hashes),'hashed files;',len(evidence),'portable reports')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination',type=Path)
    build(parser.parse_args().destination)
