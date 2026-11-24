"""Change only the Self builder and test both predeclared libraries with one deployer."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile

import httpx

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import parse_json
from scripts.check_openrouter_credits import check_credits
from studies.ledger_read import totals
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha
from studies.webbench.backbone_matrix import run as matrix

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/strong-builder-20261124'
PRIOR = ROOT / 'studies/results/backbone-extension-20261124.json'
RESULT = HERE / 'result.json'
BUILDER = 'gpt-6-astra'
DEPLOYER = 'qwen/qwen3.5-9b'
REPLICAS = ('replica-1', 'replica-2')
END = datetime(2026, 11, 24, 5, 18, tzinfo=timezone.utc)
CAP = 2.50
MODEL_TAG = 'qwen9'
PROJECT = 'table'
TASKS = tuple(range(1, 21))
LEDGER = OUT / 'budget.sqlite3'
REQUEST = matrix.request


def configure():
    matrix.OUT = browser.OUT = OUT
    matrix.END = END
    matrix.MODELS = {MODEL_TAG: (DEPLOYER, CAP, .35, 1.2)}
    matrix.MODELS.update({replica: (BUILDER, 0, 0, 0) for replica in REPLICAS})


def registered():
    record = read(OUT / 'registered.json')
    for name, expected in record['files'].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f'Frozen input changed: {name}')
    return record


def register():
    if (OUT / 'registered.json').exists():
        registered()
        return
    balance = check_credits(CAP)
    if not balance['sufficient']:
        raise BudgetStop('Insufficient OpenRouter balance')
    response = httpx.get('https://openrouter.ai/api/v1/models', timeout=30)
    response.raise_for_status()
    catalog = {entry['id']: entry for entry in response.json()['data']}
    selected = {model: catalog[model] for model in (DEPLOYER, 'openai/' + BUILDER)}
    codex_home = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex'))
    models = read(codex_home / 'models_cache.json')['models']
    if BUILDER not in {model['slug'] for model in models}:
        raise ValueError('Builder unavailable in authenticated subscription metadata')
    auth = read(codex_home / 'auth.json')
    if auth.get('auth_mode') != 'chatgpt' or auth.get('OPENAI_API_KEY'):
        raise ValueError('ChatGPT subscription required')
    data = core.public_input(PROJECT)
    if data != read(core.OUT / 'inputs/table.json'):
        raise ValueError('Materializer input differs from the current public starter')
    public_path = OUT / 'inputs/table/public.json'
    browser_path = OUT / 'inputs/table/browser.json'
    schema_path = OUT / 'response-schema.json'
    core.save(public_path, data)
    core.save(browser_path, browser.verify_contract(PROJECT))
    core.save(schema_path, core.SCHEMA)
    paths = [HERE/'PROTOCOL.md', Path(__file__), Path(core.__file__), Path(browser.__file__),
             Path(matrix.__file__), PRIOR, public_path, browser_path, schema_path, core.OUT/'inputs/table.json']
    for n in (1, 2):
        paths += [core.OUT/'builds/table'/f'codex-{n}'/name for name in ('package.json', 'status.json')]
    core.save(OUT/'registered.json', dict(
        utc=core.now(), builder=BUILDER, deployer=DEPLOYER, tasks=TASKS, replicas=REPLICAS,
        end=END.isoformat(), cap=CAP, inherited_exposure=6.478155, parallel_self_cap=4,
        balance=balance, supported_routes=selected, parameters={DEPLOYER: selected[DEPLOYER]['supported_parameters']},
        files={str(path.relative_to(ROOT)): sha(path) for path in paths}))


def subscription(tag, ledger, folder, messages, purpose, limit):
    if datetime.now(timezone.utc) >= END:
        raise matrix.Unavailable('Generation deadline')
    if (folder/'events.jsonl').exists():
        raise matrix.Unavailable('Previously submitted subscription request')
    core.save(folder/'messages.json', messages)
    env = {k:v for k,v in os.environ.items()
           if k not in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'OPENAI_BASE_URL')}
    with tempfile.TemporaryDirectory(prefix='strong-table-library-') as empty:
        cmd = ['codex', 'exec', '--ephemeral', '--ignore-user-config', '--ignore-rules',
               '--skip-git-repo-check', '-C', empty, '-s', 'read-only', '-m', BUILDER, '-c',
               'model_reasoning_effort="medium"', '--json', '--output-schema', str(OUT/'response-schema.json'),
               '-o', str(folder/'reply.json'), '-']
        try:
            with (folder/'events.jsonl').open('x') as out, (folder/'stderr.log').open('x') as err:
                child = subprocess.run(cmd, cwd=empty, env=env, input=json.dumps(messages, ensure_ascii=False),
                                       text=True, stdout=out, stderr=err, timeout=1200, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise matrix.Unavailable(type(exc).__name__) from None
    events = [json.loads(line) for line in (folder/'events.jsonl').read_text().splitlines()]
    completed = [event for event in events if event['type'] == 'turn.completed']
    tools = [event['item']['type'] for event in events if 'item' in event and
             event['item']['type'] not in ('agent_message', 'reasoning', 'plan')]
    if child.returncode or len(completed) != 1 or tools or not (folder/'reply.json').is_file():
        raise matrix.Unavailable(f'CLI {child.returncode}, turns {len(completed)}, tool events {len(tools)}')
    core.save(folder/'usage.json', completed[0]['usage'])
    return (folder/'reply.json').read_text()


def build():
    registered()
    with browser.lock(OUT/'builders.lock'):
        matrix.request = subscription
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda tag: matrix.build(tag, PROJECT, None), REPLICAS))
        finally:
            matrix.request = REQUEST
        responded = any(OUT.glob('replica-*/table/build/attempt-*/reply.json'))
        sources = {}
        for n, replica in enumerate(REPLICAS, 1):
            folder = OUT/replica/PROJECT/'build' if responded else core.OUT/'builds/table'/f'codex-{n}'
            status = read(folder/'status.json')
            sources[replica] = {'builder':BUILDER if responded else 'gpt-6.2-astra',
                                'archived':not responded, 'status':status['status'],
                                'folder':str(folder.relative_to(ROOT)),
                                'package_sha256':status.get('package_sha256')}
        core.save(OUT/'sources.json', sources)


def candidate(job, sources, ledger):
    replica, arm, n = job
    dest = OUT/replica/arm/str(n)
    if (dest/'row.json').exists():
        return read(dest/'row.json')
    source = sources[replica]
    row = {'project':PROJECT, 'replica':replica, 'arm':arm, 'task':n, 'status':source['status']}
    if source['status'] == 'valid':
        path = ROOT/source['folder']/'package.json'
        if sha(path) != source['package_sha256']:
            raise ValueError('Sealed library changed')
        pkg = read(path)
        try:
            if arm == 'fixed':
                plan = pkg['examples'][0]['plan']
            else:
                messages = core.plan_messages(read(OUT/'inputs/table/public.json'), n, pkg)
                raw = REQUEST(MODEL_TAG, ledger, dest/'call', messages, f'{replica}/target/{n}')
                row['response_sha256'] = sha(dest/'call/response.json')
                plan = parse_json(raw)
            page = dest/'page'
            files = core.materialize(PROJECT, pkg, plan, page)
            row.update(plan=plan, files=files, page=str(page.relative_to(ROOT)), status='valid')
        except (matrix.Unavailable, BudgetStop) as exc:
            row.update(status='missing', reason=str(exc))
        except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
            row.update(status='invalid', reason=str(exc)[:400])
    core.save(dest/'row.json', row)
    return row


def deploy():
    registered()
    with browser.lock(OUT/'deploy.lock'):
        if (OUT/'seal.json').exists():
            return
        sources = read(OUT/'sources.json')
        ledger = Ledger(LEDGER, CAP, CAP)
        jobs = [(replica, arm, n) for n in TASKS for replica in REPLICAS for arm in ('selected','fixed')]
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(lambda job: candidate(job, sources, ledger), jobs))
        core.save(OUT/'seal.json', {'rows':rows, 'sources_sha256':sha(OUT/'sources.json'), 'utc':core.now()})


def score():
    registration = registered()
    seal = read(OUT/'seal.json')
    sources = read(OUT/'sources.json')
    if sha(OUT/'sources.json') != seal['sources_sha256']:
        raise ValueError('Build manifest changed')
    protocol = read(OUT/'inputs/table/browser.json')
    if browser.verify_contract(PROJECT) != protocol:
        raise ValueError('Browser protocol changed')
    rows = browser.evaluate(seal['rows'], OUT, {PROJECT:protocol}, 4)
    for row in rows:
        if row['status'] in ('invalid','build_failed'):
            row['passed'] = False
    comparisons = {arm:[r['task'] for r in read(PRIOR)['models'][DEPLOYER]['rows']
                         if r['project']==PROJECT and r['arm']==arm and r['passed'] is True]
                   for arm in ('direct','self','human','gpt5-library')}
    summaries = {}
    for replica, source in sources.items():
        outcomes = {}
        for arm in ('selected','fixed'):
            trials = [r for r in rows if r['replica']==replica and r['arm']==arm]
            outcomes[arm] = {'passed':[r['task'] for r in trials if r['passed'] is True],
                             'missing':[r['task'] for r in trials if r['passed'] is None],
                             'invalid':[r['task'] for r in trials if r['status']=='invalid']}
        folder = ROOT/source['folder']
        usage = []
        for events in sorted(folder.glob('attempt-*/events.jsonl')):
            items = [json.loads(line) for line in events.read_text().splitlines()]
            usage.extend(i['usage'] for i in items if i['type']=='turn.completed')
        summaries[replica] = {**source, 'outcomes':outcomes, 'subscription_usage':usage}
    public_rows = [{k:v for k,v in row.items() if k in ('replica','arm','task','status','passed','report_sha256','response_sha256')}
                   for row in rows]
    core.save(RESULT, {'project':PROJECT, 'target_files':TASKS, 'upstream_commit':browser.UPSTREAM_COMMIT,
                        'builder_requested':BUILDER, 'deployer':DEPLOYER, 'registered_utc':registration['utc'],
                        'registration_sha256':sha(OUT/'registered.json'), 'seal_sha256':sha(OUT/'seal.json'),
                        'source_report_sha256':sha(PRIOR), 'comparison_passed_tasks':comparisons,
                        'target_api':totals(LEDGER), 'sources':summaries, 'rows':public_rows})
    print(json.dumps({'summaries':summaries, 'target_api':totals(LEDGER)}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('register', 'build', 'deploy', 'score'))
    args = parser.parse_args()
    configure()
    {'register':register, 'build':build, 'deploy':deploy, 'score':score}[args.command]()


if __name__ == '__main__':
    main()
