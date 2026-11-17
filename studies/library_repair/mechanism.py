"""Posthoc four-page intervention for one observed context-menu failure."""
import argparse
import hashlib
from .core import ROOT, HERE, read, dump, digest, source_folder, source_output, original_package
from .run import now, library_folder
from .evaluate import saved_files
from .evaluator import prepare as prepare_harness, grade
from test.webbench_expand.generate import output_files
from test.interface_blind.core import write_files

OUT = ROOT / 'artifacts/library-repair-mechanism-20261113'


def prepare():
    assert (ROOT / 'artifacts/library-repair-available-20261113/evaluation-complete.json').exists()
    assert not (OUT / 'grading-started.json').exists()
    folder = source_folder('table', 'openai/gpt-5', 'openai/gpt-oss-120b', 'plan', 20)
    plan = source_output(folder)
    old = saved_files(folder)
    package = read(library_folder('table', 'openai/gpt-5', 'feedback') / 'package.json')
    revised = output_files('plan', package, plan)
    anchor = 'e.preventDefault();\n      const pos = grid.getCellCoords(cell);'
    inserted = 'e.preventDefault();\n      e.stopPropagation();\n      const pos = grid.getCellCoords(cell);'
    removed = '      e.stopPropagation(); // prevent global contextmenu handler from hiding just-shown menu\n'
    assert old['index.js'].count(anchor) == 1
    assert revised['index.js'].count(removed) == 1
    original_plus = {**old, 'index.js': old['index.js'].replace(anchor, inserted)}
    revised_minus = {**revised, 'index.js': revised['index.js'].replace(removed, '')}
    pages = {'original': old, 'original_plus_stop': original_plus, 'feedback': revised, 'feedback_minus_stop': revised_minus}
    rows = []
    for name, files in pages.items():
        page = OUT / 'pages' / name
        write_files(page, files)
        rows.append({'name': name, 'page': str(page.relative_to(ROOT)), 'files_sha256': digest(files)})
    protocol = {'frozen_utc': now(), 'posthoc': True, 'project': 'table', 'task': 'task-20',
        'source': str(folder.relative_to(ROOT)), 'plan': plan, 'rows': rows,
        'scope': 'Single observed page/task, chosen after availability results. Four fixed pages, one evaluation each. '
                 'Only stopPropagation is added to the original or removed from the feedback implementation; '
                 'original candidate scores unchanged. Not a new model result or global defect attribution.',
        'script_sha256': hashlib.sha256((HERE / 'mechanism.py').read_bytes()).hexdigest()}
    target = OUT / 'protocol.json'
    if target.exists():
        saved = read(target)
        protocol['frozen_utc'] = saved['frozen_utc']
        assert saved == protocol
    else:
        dump(target, protocol)


def verify():
    protocol = read(OUT / 'protocol.json')
    assert hashlib.sha256((HERE / 'mechanism.py').read_bytes()).hexdigest() == protocol['script_sha256']
    for row in protocol['rows']:
        page = ROOT / row['page']
        assert digest({p.relative_to(page).as_posix(): p.read_text() for p in page.rglob('*') if p.is_file()}) == row['files_sha256']
    return protocol


def evaluate():
    protocol = verify()
    prepare_harness()
    target = OUT / 'grading-started.json'
    if not target.exists():
        dump(target, {'started_utc': now(), 'protocol_sha256': digest(protocol)})
    assert read(target)['protocol_sha256'] == digest(protocol)
    for row in protocol['rows']:
        folder = OUT / 'scores' / row['name']
        if not (folder / 'score.json').exists():
            dump(folder / 'score.json', grade('table', ROOT / row['page'], 'task-20', folder / 'report.json'))
        print(row['name'], read(folder / 'score.json')['all_passed'], flush=True)


def analyze():
    protocol = verify()
    assert protocol['frozen_utc'] <= read(OUT / 'grading-started.json')['started_utc']
    rows = []
    for row in protocol['rows']:
        folder = OUT / 'scores' / row['name']
        score = read(folder / 'score.json')
        assert hashlib.sha256((folder / 'report.json').read_bytes()).hexdigest() == score['report_sha256']
        rows.append({**row, **score, 'report': str((folder / 'report.json').relative_to(ROOT))})
    dump(ROOT / 'test/results/library-repair-mechanism.json', {'protocol': protocol, 'rows': rows})
    for row in rows:
        print(row['name'], row['all_passed'], row['tests'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'evaluate', 'analyze'])
    phase = parser.parse_args().phase
    {'prepare': prepare, 'evaluate': evaluate, 'analyze': analyze}[phase]()
