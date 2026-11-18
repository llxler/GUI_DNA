"""Compare target-specific plans against three prespecified fixed pages."""
from pathlib import Path
from studies.matched_canvas.browser import OUT as MAIN, TASKS, add_assets, score
from studies.matched_canvas.evaluate import verify
from studies.interface_blind.core import write_files
from studies.webbench_expand.core import compile_plan
from studies.study_io import ROOT, dump, read, sha, source_files, digest

OUT = ROOT/'artifacts/canvas-fixed-reuse-20261118'
HERE = Path(__file__).resolve().parent
RESULT = ROOT/'studies/results/canvas-fixed-reuse-20261118.json'


def freeze():
    paths = [HERE/'run.py',HERE/'PROTOCOL.md']
    snapshot = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    frozen = OUT/'freeze.json'
    if frozen.exists():
        assert read(frozen) == snapshot
    else:
        dump(frozen,snapshot)


def evaluate():
    verify(MAIN/'generated.json')
    verify(MAIN/'protocol-freeze.json')
    primary = read(MAIN/'evaluation.json')['results']
    cached = {}
    disagreements = []
    for key, row in sorted(primary.items()):
        if row['page']:
            identity = digest(source_files(ROOT/row['page'])), key.split('/')[1]
            if identity in cached and cached[identity][1]['passed'] != row['passed']:
                disagreements.append(key)
            cached.setdefault(identity, (key, row))
    controls = []
    for rep in (1,2):
        folder = MAIN/f'plan-{rep}'
        sources = {}
        if (folder/'prepare/frozen.json').exists():
            package = read(folder/'prepare/frozen.json')
            for i, example in enumerate(package['examples']):
                name = 'example-'+str(i)
                page = OUT/f'plan-{rep}'/name
                files = compile_plan(package,example['plan'])
                if not page.exists():
                    write_files(page, files)
                    add_assets(page)
                assert all((page/n).read_bytes()==v.encode() for n,v in files.items())
                sources[name] = page
        last = primary[f'plan-{rep}/task-20']
        if last['page']:
            sources['final-page'] = ROOT/last['page']
        for name in ('example-0','example-1','final-page'):
            for task in TASKS:
                page = sources.get(name)
                row = {'repetition':rep,'control':name,'task':task,'passed':None}
                if page:
                    identity = digest(source_files(page)),task
                    row['source_digest'] = identity[0]
                    key = f'fixed-{rep}/{name}/{task}'
                    previous = cached.get(identity)
                    if previous:
                        key, outcome = previous
                    else:
                        outcome = score(page,task,key)
                        cached[identity] = key,outcome
                    assert sha(MAIN/'scores'/key/'report.json') == outcome['report_sha256']
                    row.update(passed=outcome['passed'],report=key, report_sha256=outcome['report_sha256'])
                controls.append(row)
    result = {'protocol_sha256':sha(HERE/'PROTOCOL.md'),'rows':controls,'duplicate_conflicts':disagreements,
              'primary_evaluation_sha256':sha(MAIN/'evaluation.json'), 'new_api_cost_usd':0}
    dump(OUT/'results.json',result)
    dump(RESULT,result)


if __name__ == '__main__':
    import sys
    freeze()
    if '--freeze' not in sys.argv:
        evaluate()
