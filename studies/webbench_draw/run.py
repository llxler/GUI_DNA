"""Generate all public-only inputs before hidden scoring, with fixed stage caps."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from test.streaming_provider_v2 import StreamingOpenRouter
from test.review_stage import freeze
from studies.study_io import now, read, sha
from .core import (ROOT, HERE, BUILDERS, PLANNERS, MILESTONES, BUILD, STAGES, SEED,
    builder_messages, planner_messages, config, output_files, validate_package,
    write_source, public_check, dump, digest, slug)
from .browser import OUT as EVAL, RUNTIME, link_runtime


class BoundedProvider(StreamingOpenRouter):
    # Avoid five-minute transport retries in a two-hour study; retain reservations.
    RATE_LIMIT_TRIES = 1

    def call(self, *args, **kwargs):
        if datetime.now(timezone.utc) >= datetime(2026,11,17,3,0,tzinfo=timezone.utc):
            raise BudgetStop('Predeclared new-request time boundary')
        return super().call(*args, **kwargs)


def freeze_inputs(out, cfg):
    calibration = read(EVAL / 'calibration.json')
    assert calibration['valid'], 'Reference/blank calibration must precede any paid call'
    files = [str(p.relative_to(ROOT)) for p in HERE.iterdir() if p.suffix in ('.py','.mjs','.cjs') and p.name != 'analyze.py']
    files += ['test/webbench_draw/PROTOCOL.md', 'test/interface_blind/core.py',
        'test/interface_blind/compile.cjs','test/webbench_expand/core.py','test/webbench_expand/schema.py',
        'test/webbench_expand/generate.py','test/webbench_expand/free_build.cjs',
        'test/webbench_expand/run.py','test/webbench_expand/resume.py',
        'studies/study_io.py', 'studies/browser_jobs.py','test/provider_ext.py','test/streaming_provider_v2.py',
        'src/gui_dna/provider.py','src/gui_dna/budget.py','pyproject.toml','uv.lock',
        'artifacts/review-20261117/budget-plan.json',
        str((RUNTIME / 'package-lock.json').relative_to(ROOT)), str((EVAL / 'calibration.json').relative_to(ROOT))]
    for base in (ROOT / 'artifacts/web-bench/projects/draw', ROOT / 'artifacts/web-bench/libraries/test-util/src'):
        files += [str(p.relative_to(ROOT)) for p in base.rglob('*') if p.is_file()]
    files += [str(p.relative_to(ROOT)) for p in (EVAL / 'calibration').rglob('*.json')]
    freeze(out, cfg, sorted(set(files)), {'project':'draw', 'builders':BUILDERS, 'planners':PLANNERS,
        'milestones':MILESTONES, 'created_before_generation':True})


def one(client, out, model, builder=None, method=None, k=None, package=None):
    building = method is None
    folder = (out / 'libraries' / slug(model) if building else
        out / 'runs' / (slug(builder) if builder else 'no_library') / method / f'task-{k}')
    target = folder / 'record.json'
    if target.exists():
        return read(target)
    messages = builder_messages() if building else planner_messages(k, method, package)
    dump(folder / 'messages.json', messages)
    record = {'project':'draw', 'builder':model if building else builder, 'model':model,
        'method':'build' if building else method, 'task':None if building else f'task-{k}',
        'attempts':[], 'status':'failed' if building else 'complete', 'started_utc':now(),
        'package_sha256':digest(package) if package else None, 'manual_edits':[]}
    for attempt in range(3):
        try:
            raw = client.call(model, messages, folder / f'call-{attempt}',
                'webbench-draw:' + record['method'], seed=SEED)
        except (BudgetStop, ProviderError) as error:
            record.update(status='budget_incomplete' if isinstance(error, BudgetStop) else 'transport_incomplete', error=str(error))
            break
        dump(folder / f'output-{attempt}.json', {'text':raw})
        version = None
        try:
            parsed = parse_json(raw)
            if building:
                feedback = validate_package(parsed, folder / f'validation-{attempt}')
            else:
                files = output_files(method, package, parsed)
                version = f'version-{attempt}'
                write_source(folder / version, files)
                feedback = public_check(folder / version)
        except (ValueError, KeyError, TypeError, RuntimeError, TimeoutError, subprocess.TimeoutExpired) as error:
            feedback = [str(error)[:1600]]
            if not building and not (folder / f'version-{attempt}/source-manifest.json').exists():
                version = None
        record['attempts'].append({'attempt':attempt, 'feedback':feedback, 'version':version})
        dump(target, record)
        if not feedback:
            if building:
                dump(folder / 'package.json', parsed)
                record.update(status='frozen', package_sha256=digest(parsed), selected_attempt=attempt)
            break
        messages += [{'role':'assistant','content':raw}, {'role':'user','content':
            'Public format/compiler/load feedback:\n' + '\n'.join(feedback) +
            '\nReturn the full corrected JSON. No behavioral tests were run.'}]
    record['finished_utc'] = now()
    dump(target, record)
    print(f"{model} {builder or ''} {record['method']} {k}: {record['status']} {len(record['attempts'])} attempts", flush=True)
    return record


def execute(kind):
    out = BUILD if kind == 'build' else STAGES[PLANNERS[0 if kind == 'oss' else 1]]
    cfg = config(kind)
    freeze_inputs(out, cfg)
    link_runtime(out)
    ledger = Ledger(out / 'budget.sqlite3', cfg['budget_usd'], cfg['stop_new_requests_usd'])
    try:
        client = BoundedProvider(cfg, ledger)
        if kind == 'build':
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda model:one(client, out, model), BUILDERS))
        else:
            model = cfg['models'][0]
            jobs = [(None,'free',k,None) for k in MILESTONES]
            for builder in BUILDERS:
                folder = BUILD / 'libraries' / slug(builder)
                record = read(folder / 'record.json')
                if record['status'] != 'frozen':
                    continue
                package = read(folder / 'package.json')
                assert digest(package) == record['package_sha256']
                for k in MILESTONES:
                    for method in ('plan','free_lib'):
                        jobs.append((builder,method,k,package))
            dump(out / 'planned-jobs.json', [{'builder':b,'method':m,'task':f'task-{k}',
                'package_sha256':digest(p) if p else None} for b,m,k,p in jobs])
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda job:one(client, out, model, *job), jobs))
        dump(out / 'generation-complete.json', {'finished_utc':now(), 'records':len(results),
            'statuses':{status:sum(r['status']==status for r in results) for status in sorted({r['status'] for r in results})}})
    finally:
        Ledger(out / 'budget.sqlite3', cfg['budget_usd'], 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['build','oss','frontier'])
    execute(parser.parse_args().kind)
