"""Run from a fresh extraction. Browser checks use only local pages and fixtures."""
import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
from studies.study_io import cases_by_file

ROOT = Path(__file__).resolve().parent


def read(p):
    return json.loads((ROOT/p).read_text())


def outcome(report,task):
    cases = cases_by_file(report)
    assert set(cases)=={task} and cases[task]
    if all(case['passed'] for case in cases[task]):
        return True
    assert any(s in ('failed','timedOut') for c in cases[task] for s in c['statuses'])
    return False


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):
        pass


def smoke(view):
    observed = {}
    folder = ROOT/'smoke'
    targets = {'canvas/reference':('task-4',True),'canvas/blank':('task-4',False),
        'canvas/candidate':('task-4',view['scheduled']['rows']['free-1/task-4']['passed']),
        'flex/reference':('task-20',True),'flex/blank':('task-20',False)}
    for arm in ('free','plan'):
        targets['flex/'+arm] = ('task-20',view['flex']['rows'][arm+'-1/task-20']['passed'])
    for name,(task,expected) in targets.items():
        server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=folder/'pages'/name))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as tmp:
                report=Path(tmp)/'report.json'
                run=subprocess.run(['node','node_modules/@playwright/test/cli.js','test','--config','playwright.config.cjs',
                    '--workers=1','--max-failures=1',f'test/{task}.spec.js','--output',tmp+'/output'],
                    cwd=folder,timeout=200,env={**os.environ,'CANDIDATE_URL':f'http://127.0.0.1:{server.server_port}',
                    'REPORT_FILE':str(report),'EVAL_PROJECT_ROOT':str(folder/'pages'/name),'CI':'1'})
                payload=json.loads(report.read_text())
                assert not [e for e in payload.get('errors',[]) if 'maximum allowed failures' not in e.get('message','')]
                observed[name]=outcome(payload,task)
                assert observed[name] == expected, (name,observed[name],expected)
                assert run.returncode==int(not observed[name])
        finally:
            server.shutdown()
            server.server_close()
    return observed


def main(browser):
    hashes=read('manifest.json')
    for name,hash_value in hashes.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==hash_value,name
    for package in ('studies','test'):
        subprocess.run([sys.executable,'-m',package+'.end_to_end','--check'],cwd=ROOT,
                       stdout=subprocess.DEVNULL,check=True)
    view=read('studies/results/end_to_end.json')
    pilots={**view['canvas_pilots'],'flex':view['matched_flex']}
    entries=read('evidence.json')
    expected = {}
    def register(label, section, key, row):
        name = f'evidence/{label}/{section}/{key}.json'
        value = (row['report_sha256'], row['passed'])
        if name in expected:
            assert expected[name] == value
        expected[name] = value
    for label,study in pilots.items():
        for section,rows in [('calibration',study['calibration']), ('scores',study['rows'])]:
            for key,row in rows.items():
                if row.get('report_sha256'):
                    register(label,section,key,row)
    for label,name in [('scheduled','canvas-fixed-reuse-20261118'),
                       ('capacity_followup','canvas-capacity-20261118-reuse'),
                       ('model_replication','canvas-sonnet-20261118-reuse')]:
        for row in read('studies/results/'+name+'.json')['rows']:
            if row.get('report_sha256'):
                register(label,'scores',row['report'],row)
    for key,row in view['input_controls']['official'].items():
        register('input-controls','scores',key,row)
    assert expected.keys()==entries.keys()
    for path,ref in entries.items():
        assert (ref['source_sha256'],outcome(read(path),ref['key'].split('/')[-1])) == expected[path]
    table = read('diagnostics/table-behavior-probe-20261118/observations.json')
    for page in [*table['controls'].values(), *table['pages'].values()]:
        for op,trials in page.items():
            for trial in trials:
                action,sham = trial['action'],trial['sham']
                before = action['before']
                actual = None
                if before and before[0] and before[0][0] and before == sham['before']:
                    expected_after = before[1:] if op=='delete_row' else [['',*before[0][1:]],*before[1:]]
                    actual = action['after'] == expected_after and sham['after'] == before
                assert actual == trial['response']
    for lib in view['table_behavior']['libraries'].values():
        for v in lib['variants'].values():
            if 'responses' in v:
                obs=table['pages'][v['source_digest']]
                assert v['responses']=={op:[r['response'] for r in trials] for op,trials in obs.items()}
    traces = read('diagnostics/canvas-speed-probe-20261118/traces.json')
    for sequence in [*traces.values(), *view['canvas_speed']['calibration'].values()]:
        for r in sequence:
            d,z = r['d'],r['z']
            value = None
            if None not in d+z and d[0]==z[0] and d[0]>=d[1] and z[0]>=z[1]:
                value = (d[0]-d[1])-(z[0]-z[1])
            assert value == r['acceleration_px']
    for lib in view['canvas_speed']['libraries'].values():
        for row in lib.get('rows',{}).values():
            if 'values' in row:
                assert row['values']==[r['acceleration_px'] for r in traces[row['source_digest']]]
    print(json.dumps({'verified_files':len(hashes),'portable_reports':len(entries),
                      'distinct_original_reports':len({e['source_sha256'] for e in entries.values()}),'current_view_recomputed':True,
                      'report_namespaces':['studies','test'],'matched_target_positions':sum(len(v['rows']) for v in pilots.values()),
                      'fresh_browser':smoke(pilots) if browser else None}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--browser',action='store_true')
    main(parser.parse_args().browser)
