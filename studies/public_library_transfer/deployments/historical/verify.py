"""Verify frozen provider requests, receipts, independent budgets and target denominators offline."""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING

from studies.ledger_read import calls, totals
from studies.study_io import ROOT, read, sha
from studies.public_library_transfer import core
from studies.public_library_transfer.browser import verify_page
from studies.public_library_transfer.report import enrolled_tasks, validate_rows
from . import milestones, run, supplement


def micro(v):
    return int((Decimal(str(v))*1_000_000).to_integral_value(rounding=ROUND_CEILING))


def receipts():
    by_id={}
    model_calls={m:calls(run.OUT/m/'budget.sqlite3') for m in run.MODELS}
    for m,entries in model_calls.items():
        for entry in entries:
            if entry['id'] in by_id or entry['model']!=run.MODELS[m]:
                raise ValueError('Duplicate admission or model mismatch')
            by_id[entry['id']]=entry
    seen=set()
    for root in (run.OUT/'runs',supplement.SUP/'runs',milestones.OUT/'runs'):
        if not root.exists():continue
        for path in root.rglob('request.json'):
            request=read(path)
            body=request['body']
            call_id=request['call_id']
            entry=by_id[call_id]
            if (call_id in seen or entry['model']!=body['model'] or micro(request['reserved_usd'])!=entry['reserved']
                    or body['response_format']['type']!='json_schema' or body['response_format']['json_schema']['strict'] is not True
                    or body['provider']['max_price']!=run.PRICES):
                raise ValueError(f'Admission mismatch: {path}')
            seen.add(call_id)
            settled=path.parent/'settled.json'
            if settled.exists():
                value=read(settled)
                response=read(path.parent/'response.json')
                if (entry['actual']!=micro(response['usage']['cost']) or response['usage']['cost']!=value['billed_usd']
                        or value['call_id']!=call_id or entry['actual']>entry['reserved']):
                    raise ValueError(f'Provider charge mismatch: {path}')
            elif entry['actual'] is not None:
                raise ValueError(f'Unexpected charge without receipt: {path}')
    if set(by_id)!=seen:
        raise ValueError('Ledger has an admission without archived request')
    for m,entries in model_calls.items():
        ledger=run.OUT/m/'budget.sqlite3'
        value=totals(ledger)
        if value['cap_usd']!=run.CAP or value['stop_usd']!=run.CAP or value['exposure_usd']>run.CAP:
            raise ValueError(f'Unexpected policy/exposure for {m}')
        if milestones.BASE_BILL.exists():
            previous=read(milestones.BASE_BILL)['models'][run.MODELS[m]]['totals']
            filtered=[r for r in entries if not r['purpose'].startswith('milestones/')]
            if (previous['calls']!=len(filtered) or micro(previous['settled_usd'])!=sum(r['actual'] or 0 for r in filtered)
                    or micro(previous['exposure_usd'])!=sum(r['actual'] if r['actual'] is not None else r['reserved'] for r in filtered)):
                raise ValueError(f'Eight-project ledger slice differs: {m}')
        if milestones.BILL.exists() and read(milestones.BILL)['deployment'][run.MODELS[m]]['whole_shared_ledger']!=value:
            raise ValueError(f'Milestone accounting differs: {m}')
    return len(seen)


def expected(root):
    result=defaultdict(set)
    if root==run.OUT:
        original=run.scheduled()
        for p,m,n,arm in original:
            builder=None if arm=='direct' else run.BUILDERS[arm]
            result[p,'direct' if arm=='direct' else 'plan',builder,0 if arm=='direct' else 1,run.MODELS[m]].add(n)
            if arm!='direct':result[p,'fixed',builder,1,None].add(n)
    else:
        for p,m,n,tag in milestones.targets():
            if tag=='direct':
                result[p,'direct',None,0,run.MODELS[m]].add(n)
    grid=supplement.scheduled() if root==run.OUT else (t for t in milestones.targets() if t[3]!='direct')
    for p,m,n,tag in grid:
        result[p,'plan',core.BUILDERS[tag],int(tag[-1]),run.MODELS[m]].add(n)
        result[p,'fixed',core.BUILDERS[tag],int(tag[-1]),None].add(n)
    return dict(result)


def generated(root):
    sealed=root/'generation-sealed.json'
    rows=read(sealed)['rows']
    validate_rows(rows,enrolled_tasks(root,{r['project'] for r in rows}))
    matches=defaultdict(set)
    for r in rows:
        group=tuple(r[key] for key in ('project','arm','builder','rep','planner'))
        matches[group].add(r['task'])
        if r['status']=='valid':
            verify_page(ROOT/r['page'],r['files'],r['project'])
        else:
            if r['files'] or r['page']:raise ValueError('Absent or invalid pipeline output has a page')
        if r['arm']=='plan' and r['builder'] in run.BUILDERS.values() and r['status']=='missing':
            tag=next(k for k,v in run.BUILDERS.items() if v==r['builder'])
            if sha(run.MAIN/'builds'/r['project']/tag/'status.json')!=r['build_status_sha256']:
                raise ValueError('Missing preparation source differs from its seal')
    if matches!=expected(root):raise ValueError(f'Registered design differs from output at {root}')
    return len(rows),len(matches)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--require-seals',action='store_true')
    args=parser.parse_args()
    roots=(run.OUT,milestones.OUT)
    unfinished=[p.name for p in roots if not (p/'generation-sealed.json').exists()]
    if unfinished:
        message='Ledger admissions are still mutable; offline reconciliation starts after both acquisition seals: '+', '.join(unfinished)
        if args.require_seals:
            raise SystemExit(message)
        print(message)
    else:
        audited=receipts()
        print(f'{audited} reservations reconciled with their individual request files.')
        for path in roots:
            rows,groups=generated(path)
            print(f'{path.name}: {rows} registrations across {groups} correctly matched groups.')
