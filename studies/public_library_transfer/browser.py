"""Score a sealed Web-Bench page against exactly one original task file per run."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from studies.study_io import ROOT, UPSTREAM, cases_by_file, digest, dump, read, sha
from studies.todomvc_dna.evaluate import Server, browser_env
from studies.webbench_draw.browser import Server as ViteServer

OUT = ROOT / 'artifacts/public-library-transfer-20261123'
ARTIFACTS = ROOT / 'artifacts'
PROJECTS = ('dom1', 'form', 'calculator', 'table', 'bom', 'svg-chart', 'draw', 'canvas', 'flex', 'expression-editor')
TASKS = tuple(range(1, 21))
VITE = {'draw', 'svg-chart'}
UPSTREAM_COMMIT = '7b31ca2b786eef120dd49ce63dd03d0c0006046d'
BLANK = '<!doctype html><title>Blank</title>'


def tree(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        dump(temporary, value)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def preserve_json(path, value):
    with lock(path.with_suffix('.lock')):
        if path.exists():
            if read(path) != value:
                raise ValueError(f'Existing evidence differs: {path}')
        else:
            write_json(path, value)


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def contract(project):
    if project in ('dom1', 'form'):
        harness = ARTIFACTS / 'interface-blind-harness' / project
        runtime = ROOT / 'studies/webbench_dna/harness'
    elif project in ('calculator', 'table', 'bom'):
        harness = ARTIFACTS / 'webbench-expand-harness-157' / project
        runtime = ARTIFACTS / 'webbench-expand-runtime-157'
    elif project == 'expression-editor':
        harness = ARTIFACTS / 'expression-editor-sources-20261123/harness/157-expression-editor'
        runtime = ARTIFACTS / 'expression-editor-runtime-20261123'
    elif project in ('flex', 'canvas'):
        harness = ARTIFACTS / f'matched-{project}-20261118/harness/157-{project}'
        runtime = ARTIFACTS / 'webbench-expand-runtime-157'
    elif project in VITE:
        name = ('svg-chart-sources-20261121/harness' if project == 'svg-chart'
                else 'webbench-draw-eval-20261117/harness/projects/draw')
        harness = ARTIFACTS / name
        runtime = ARTIFACTS / 'webbench-draw-runtime-20261117'
    else:
        raise ValueError(f'Unknown Web-Bench project {project}')
    config = 'run.config.js' if project == 'svg-chart' else 'playwright.config.cjs'
    return harness, runtime, config


def verify_contract(project):
    harness, runtime, config = contract(project)
    source = UPSTREAM / 'projects' / project
    if (UPSTREAM / '.git').exists():
        rev = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
        changed = subprocess.check_output(['git', '-C', str(UPSTREAM), 'status', '--porcelain', '--',
                                           f'projects/{project}/test', f'projects/{project}/src', f'projects/{project}/assets'])
        if changed:
            raise ValueError(f'{project}: local upstream controls or original test sources changed')
    else:
        rev = read(UPSTREAM / 'REPLAY-UPSTREAM.json')['commit']
    if rev != UPSTREAM_COMMIT:
        raise ValueError(f'{project}: unexpected upstream commit {rev}')
    tests = tree(source / 'test')
    if tree(harness / 'test') != tests or not all(f'task-{n}.spec.js' in tests for n in TASKS):
        raise ValueError(f'{project}: official harness or twenty task files differ from upstream')
    local_package = harness / 'package.json'
    local_type = read(local_package).get('type', 'commonjs') if local_package.exists() else 'commonjs'
    if local_type != read(source / 'package.json').get('type', 'commonjs'):
        raise ValueError(f'{project}: harness JavaScript module mode differs from upstream')
    modules = runtime / 'node_modules'
    if project == 'draw':
        linked = harness.parents[1] / 'libraries/test-util'
        if linked.resolve() != (modules / '@web-bench/test-util').resolve():
            raise ValueError('Wrong draw test utility')
    config_files = [harness / config, runtime / 'package-lock.json', modules / 'playwright-core/browsers.json']
    if project in VITE:
        config_files.append(ROOT / 'studies/webbench_draw/server.mjs')
    if project == 'svg-chart':
        config_files.extend((harness / 'package.json', harness / 'playwright.config.js'))
        for name in ('package.json', 'playwright.config.js'):
            if sha(harness / name) != sha(source / name):
                raise ValueError(f'{project}: original {name} changed')
    version = read(modules / '@playwright/test/package.json')['version']
    expected = '1.63.0' if project in ('dom1', 'form') else '1.57.0'
    if version != expected:
        raise ValueError(f'{project}: expected Playwright {expected}, found {version}')
    return {'project': project, 'playwright': version, 'node': subprocess.check_output(['node', '--version'], text=True).strip(),
            'harness': str(harness.relative_to(ROOT)), 'runtime': str(runtime.relative_to(ROOT)),
            'server': 'vite' if project in VITE else 'static', 'tests_sha256': tests,
            'assets_sha256': tree(source / 'assets'), 'test_utility_sha256': tree(modules / '@web-bench/test-util'),
            'configuration_sha256': {str(p.relative_to(ROOT)): sha(p) for p in config_files}}


@contextmanager
def browser_slot():
    """Throttle simultaneous public loads, calibration and sealed scoring across processes."""
    folder = Path(tempfile.gettempdir()) / f'gui-dna-transfer-browser-{os.getuid()}'
    folder.mkdir(exist_ok=True)

    def available_memory():
        return next(int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()
                    if line.startswith('MemAvailable:'))

    def reserve(slot):
        stream = (folder / str(slot)).open('a')
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            stream.close()
            return None
        return stream

    with ExitStack() as reservation:
        extra = reserve(4) if available_memory() >= 3_000_000 else None
        if extra:
            with extra:
                yield
            return
        with lock(folder / 'admission.lock'):
            while True:
                available = available_memory()
                acquired = False
                for i, headroom in enumerate((400_000, 1_200_000, 1_900_000, 2_800_000, 3_000_000)):
                    if available < headroom:
                        break
                    stream = reserve(i)
                    if stream is None:
                        continue
                    reservation.enter_context(stream)
                    acquired = True
                    break
                if acquired:
                    break
                time.sleep(.25)
        yield


@contextmanager
def serve(project, page):
    with browser_slot():
        if project in VITE:
            with ViteServer(page) as server:
                yield server.url
        else:
            server = Server(page)
            original_handler = server.httpd.handle_error

            def on_server_error(request, address):
                if not isinstance(sys.exception(), (BrokenPipeError, ConnectionResetError)):
                    original_handler(request, address)

            server.httpd.handle_error = on_server_error
            try:
                yield f'http://127.0.0.1:{server.port}'
            finally:
                server.close()
                server.httpd.server_close()


def verify_page(page, files, project):
    if not page.is_dir() or tree(page) != files or 'index.html' not in files:
        raise ValueError(f'{project}: candidate differs from sealed file manifest at {page}')
    if any(p.is_symlink() for p in page.rglob('*')):
        raise ValueError(f'{project}: materialize symlinks into sealed pages')
    for name, expected in tree(UPSTREAM / 'projects' / project / 'assets').items():
        if files.get(f'assets/{name}') != expected:
            raise ValueError(f'{project}: public asset {name} differs from upstream')


def served_page(root, project, page, files):
    if project not in VITE:
        return page
    _, runtime, _ = contract(project)
    folder = root / 'browser' / 'vite' / project
    copy = folder / digest(files)
    with lock(folder / '.lock'):
        modules = folder / 'node_modules'
        if not modules.exists():
            modules.symlink_to(runtime / 'node_modules', target_is_directory=True)
        if modules.resolve() != (runtime / 'node_modules').resolve():
            raise ValueError(f'{project}: wrong Vite dependencies')
        if project == 'svg-chart':
            package = UPSTREAM / 'projects/svg-chart/package.json'
            dest = folder / 'package.json'
            if not dest.exists():
                shutil.copy2(package, dest)
            if sha(package) != sha(dest):
                raise ValueError('svg-chart: missing official ESM context')
        if not copy.exists():
            with tempfile.TemporaryDirectory(dir=folder) as temporary:
                staging = Path(temporary) / 'page'
                shutil.copytree(page, staging)
                staging.rename(copy)
        verify_page(copy, files, project)
    return copy


def public_load(project, page):
    """Open the public entry point once without reading test files or scoring behavior."""
    page = Path(page).resolve()
    files = tree(page)
    verify_page(page, files, project)
    page = served_page(OUT, project, page, files)
    _, runtime, _ = contract(project)
    script = """
const {chromium} = require(process.argv[1]);
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', err => errors.push(String(err).slice(0, 1200)));
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text().slice(0, 1200));
    });
    try {
      const response = await page.goto(process.argv[2] + '/index.html',
        {waitUntil: 'networkidle', timeout: 20000});
      if (!response || !response.ok()) errors.push('index.html could not be loaded');
      await page.waitForTimeout(300);
    } catch (err) { errors.push(String(err).slice(0, 1200)); }
    process.stdout.write(JSON.stringify(errors.slice(0, 12)));
  } finally { await browser.close(); }
})().catch(err => { console.error(err); process.exit(1); });
"""
    with serve(project, page) as url:
        run = subprocess.run(['node', '-e', script, str(runtime / 'node_modules/@playwright/test'), url],
                             env=browser_env(), capture_output=True, text=True, timeout=60, check=True)
    return json.loads(run.stdout)


def verdict(report, rc, task):
    errors = [e for e in report.get('errors', []) if 'maximum allowed failures' not in e.get('message', '')]
    cases = cases_by_file(report)
    if errors or set(cases) != {f'task-{task}'}:
        raise RuntimeError(f'Invalid official report for task {task}: {errors}')
    system_failures = ("Executable doesn't exist at", 'Host system is missing dependencies to run browsers',
                       'pthread_create: Resource temporarily unavailable', 'browserType.launch: Failed to launch',
                       'spawn /usr/bin/node EAGAIN', 'Cannot allocate memory')
    for suite in report.get('suites', []):
        if any(marker in json.dumps(suite) for marker in system_failures):
            raise RuntimeError(f'Browser infrastructure failed on task {task}; preserve the attempt log')
    outcomes = cases[f'task-{task}']
    if outcomes and all(case['passed'] for case in outcomes) and rc == 0:
        return True
    if rc == 1 and any(s in ('failed', 'timedOut') for c in outcomes for s in c['statuses']):
        return False
    raise RuntimeError(f'Incomplete official result for task {task}, process exit {rc}')


def verify_receipt(root, path, expected):
    value = read(path)
    raw = root / value['report']
    if (any(value[k] != v for k, v in expected.items()) or sha(raw) != value['report_sha256']
            or verdict(read(raw), value['exit_code'], expected['task']) != value['passed']):
        raise ValueError(f'Cached score mismatch: {path}')
    if value.get('source_receipt'):
        original = ROOT / value['source_receipt']
        if sha(original) != value['source_receipt_sha256'] or sha(ROOT / value['source_report']) != value['report_sha256']:
            raise ValueError(f'Cached source receipt changed: {original}')
    return value


def run_one(root, project, task, page, files, protocol):
    verify_page(page, files, project)
    page = served_page(root, project, page, files)
    relative = Path('browser/scores') / project / f'task-{task}' / digest(files)
    folder = root / relative
    receipt = folder / 'score.json'
    expected = {'project': project, 'task': task, 'files_digest': digest(files), 'contract_digest': digest(protocol)}
    scopes = (OUT, *(ARTIFACTS / f'public-library-transfer-{name}-20261123'
                     for name in ('remote', 'remote-milestones', 'holdout', 'prompt', 'delivery', 'open', 'boolean', 'table-space')))
    peers = [p for p in scopes if p != root] if root in scopes else []
    with lock(OUT / 'browser/content-locks' / project / f'task-{task}' / digest(files)), lock(folder / '.lock'):
        if receipt.exists():
            return verify_receipt(root, receipt, expected)
        for peer in peers:
            previous = peer / relative / 'score.json'
            if previous.exists():
                source = verify_receipt(peer, previous, expected)
                raw = folder / 'reused/report.json'
                raw.parent.mkdir(exist_ok=True)
                shutil.copyfile(peer / source['report'], raw)
                value = dict(source, report=str(raw.relative_to(root)), source_receipt=str(previous.relative_to(ROOT)),
                             source_receipt_sha256=sha(previous), source_report=str((peer / source['report']).relative_to(ROOT)))
                write_json(receipt, value)
                return verify_receipt(root, receipt, expected)
        attempt = folder / f'attempt-{len(list(folder.glob("attempt-*"))) + 1}'
        attempt.mkdir()
        raw = attempt / 'report.json'
        harness, runtime, config = contract(project)
        with serve(project, page) as url, (attempt / 'console.log').open('w') as output:
            env = dict(browser_env(), CI='1', CANDIDATE_URL=url, EVAL_PROJECT_ROOT=str(page), REPORT_FILE=str(raw))
            if project == 'svg-chart':
                env['IS_EVAL_PRODUCTION'] = '1'
            command = ['node', str(runtime / 'node_modules/@playwright/test/cli.js'), 'test', '--config', config,
                       f'test/task-{task}.spec.js', '--workers=1', '--max-failures=1', '--output', str(attempt / 'output')]
            rc = subprocess.run(command, cwd=harness, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=600).returncode
        if not raw.exists():
            raise RuntimeError(f'No Playwright report, inspect {attempt}')
        report = read(raw)
        passed = verdict(report, rc, task)
        verify_page(page, files, project)
        value = dict(expected, passed=passed, report=str(raw.relative_to(root)), report_sha256=sha(raw), exit_code=rc)
        write_json(receipt, value)
        return value


def evaluate(rows, root, protocols, workers):
    jobs = {}
    for row in rows:
        if row['status'] != 'valid':
            continue
        page = (ROOT / row['page']).resolve()
        if not page.is_relative_to(ARTIFACTS) or not isinstance(row['files'], dict):
            raise ValueError('Expected an artifact page with a sealed file manifest')
        project, task = row['project'], row['task']
        if project not in PROJECTS or type(task) is not int or task not in TASKS:
            raise ValueError(f'Invalid scoring target {project}/{task}')
        verify_page(page, row['files'], project)
        jobs.setdefault((project, task, digest(row['files'])), (root, project, task, page, row['files'], protocols[project]))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        values = dict(zip(jobs, pool.map(lambda args: run_one(*args), jobs.values())))
    result = []
    for row in rows:
        receipt = None
        if row['status'] == 'valid':
            receipt = values[(row['project'], row['task'], digest(row['files']))]
        elif row['status'] not in ('invalid', 'missing', 'build_failed') or row.get('page') or row.get('files'):
            raise ValueError(f'Unexpected nonvalid row: {row}')
        value = {**row, 'passed': None if receipt is None else receipt['passed'],
                 'report': None if receipt is None else receipt['report'],
                 'report_sha256': None if receipt is None else receipt['report_sha256']}
        if receipt and receipt.get('source_report'):
            value.update(reused_from=receipt['source_report'], source_receipt_sha256=receipt['source_receipt_sha256'])
        result.append(value)
    return result


def calibration_evidence(root, projects):
    records = []
    for project in projects:
        current = {}
        contract_hash = digest(verify_contract(project))
        for path in sorted((root / 'browser/calibration' / project).glob('*.json')):
            data = read(path)
            if digest(data['contract']) != contract_hash:
                raise ValueError(f'Calibration harness changed: {path}')
            for row in data['rows']:
                key = row['arm'], row['task']
                fingerprint = digest(row['files'])
                receipt = root / 'browser/scores' / project / f'task-{row["task"]}' / fingerprint / 'score.json'
                expected = {'project': project, 'task': row['task'], 'files_digest': fingerprint, 'contract_digest': contract_hash}
                value = verify_receipt(root, receipt, expected)
                if any(row[k] != value[k] for k in ('report', 'report_sha256', 'passed')):
                    raise ValueError(f'Calibration claim differs from the Playwright report: {receipt}')
                if key in current and current[key] != row:
                    raise ValueError(f'Conflicting calibration: {project}/{key}')
                current[key] = row
        tasks = [task for task in TASKS if ('reference', task) in current and ('blank', task) in current]
        records.append({'project': project, 'tested_tasks': tasks,
                        'reference_failed': [n for n in tasks if not current['reference', n]['passed']],
                        'blank_passed': [n for n in tasks if current['blank', n]['passed']],
                        'reports': {f'{arm}/{n}': {'path': r['report'], 'sha256': r['report_sha256']}
                                    for (arm, n), r in current.items()}})
    return records


def controls(root, projects, tasks, workers):
    rows = []
    protocols = {p: verify_contract(p) for p in projects}
    for project in projects:
        source = UPSTREAM / 'projects' / project
        for control in ('reference', 'blank'):
            page = root / 'browser/controls' / project / control
            with lock(page.parent / '.lock'):
                if not page.exists():
                    with tempfile.TemporaryDirectory(dir=page.parent) as temp:
                        stage = Path(temp) / 'page'
                        if control == 'reference':
                            shutil.copytree(source / 'src', stage)
                        else:
                            stage.mkdir()
                            (stage / 'index.html').write_text(BLANK)
                        if (source / 'assets').exists():
                            shutil.copytree(source / 'assets', stage / 'assets', dirs_exist_ok=True)
                        stage.rename(page)
            files = tree(page)
            expected = tree(source / 'src') if control == 'reference' else {'index.html': hashlib.sha256(BLANK.encode()).hexdigest()}
            expected.update({f'assets/{name}': value for name, value in tree(source / 'assets').items()})
            if files != expected:
                raise ValueError(f'Calibration page differs from the nominated control: {page}')
            for task in tasks:
                rows.append({'project': project, 'task': task, 'arm': control, 'status': 'valid',
                             'page': str(page.relative_to(ROOT)), 'files': files})
    result = evaluate(rows, root, protocols, workers)
    for project in projects:
        selected = [r for r in result if r['project'] == project]
        preserve_json(root / 'browser/calibration' / project / ('tasks-' + '-'.join(map(str, tasks)) + '.json'),
                      {'contract': protocols[project], 'rows': selected})


def publish_calibration(root):
    rows = calibration_evidence(root, PROJECTS)
    if any(r['tested_tasks'] != list(TASKS) for r in rows):
        raise ValueError('Complete all 20 reference and blank controls for all ten projects')
    value = {'upstream_commit': UPSTREAM_COMMIT, 'artifacts': str(root.relative_to(ROOT)),
             'definition': 'Each unchanged current-task file runs separately on the final upstream reference and on blank HTML with the original public assets.',
             'projects': rows}
    study, date = root.name.rsplit('-', 1)
    dest = ROOT / 'studies/results' / f'{study}-calibration-{date}.json'
    if dest.exists() and read(dest) != value:
        raise ValueError(f'Published calibration differs: {dest}')
    write_json(dest, value)


def monitor(root, workers):
    from .report import score
    priority = ('table', 'svg-chart', *(p for p in PROJECTS if p not in ('table', 'svg-chart')))
    with lock(root / 'browser/monitor.lock'):
        while True:
            for project in priority:
                if ((root / 'project-seals' / f'{project}.json').exists()
                        and not (root / 'browser/project-scores' / f'{project}.json').exists()):
                    print(f'Scoring sealed project {project}', flush=True)
                    score(root, project, workers)
                    break
            else:
                if (root / 'generation-sealed.json').exists():
                    break
                time.sleep(4)
        score(root, None, workers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'calibrate', 'calibration-report', 'score', 'monitor', 'audit'])
    parser.add_argument('--root', type=Path, default=OUT)
    parser.add_argument('--project', choices=PROJECTS)
    parser.add_argument('--tasks', type=int, nargs='+', default=list(TASKS))
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    root = args.root.resolve()
    projects = (args.project,) if args.project else PROJECTS
    if not root.is_relative_to(ARTIFACTS) or not 1 <= args.workers <= 6:
        parser.error('Use a study artifact directory and one to six workers')
    if set(args.tasks) - set(TASKS) or len(args.tasks) != len(set(args.tasks)):
        parser.error('Use distinct official tasks from 1 to 20')
    if args.action == 'calibrate':
        controls(root, projects, args.tasks, args.workers)
    elif args.action == 'calibration-report':
        publish_calibration(root)
    elif args.action == 'monitor':
        if args.project or args.tasks != list(TASKS):
            parser.error('Monitor scores exactly the enrolled projects and targets')
        monitor(root, args.workers)
    elif args.action == 'audit':
        from .report import audit
        print('Verified sealed rows and unique browser reports:', *audit(root))
    elif args.action == 'verify':
        for project in projects:
            print(project, digest(verify_contract(project)))
    else:
        if args.tasks != list(TASKS):
            parser.error('Score every target in the sealed manifest')
        from .report import score
        score(root, args.project, args.workers)


if __name__ == '__main__':
    main()
