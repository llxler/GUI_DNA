"""Reconcile the red-box comparisons and the complete paid exposure from immutable receipts."""
import argparse
from collections import Counter,defaultdict

from studies import ledger_read, paper_component_followup as studies
from studies.public_library_transfer import core
from studies.public_library_transfer.compact_todomvc import run as small
from studies.public_library_transfer.compact_todomvc.event_functions import run as events,delivery
from studies.study_io import ROOT,read,sha
from studies.webbench.compact_planning import run as menu
from studies.webbench.compact_planning.visible_decoding import run as visible
from studies.webbench.typed_components import run as typed,integration,svg_admission,entrypoints
from studies.webbench.typed_components.unavailable import run as absent
from studies.webbench.transport_completion import run as restore,extend
from studies.webbench.table_interactions import run as profiles
from studies.webbench.table.event_modules import run as handlers,source_recovery,focused
from studies.webbench.form.flash_self_build.visible_targets import run as flash,schema_transfer

OUTPUT=ROOT/'studies/results/component-followup-20261125.json'
PAID=((menu,studies.COMPACT),(visible,studies.VISIBLE),(small,studies.SMALL),(events,studies.EVENTS),
      (delivery,studies.DELIVERY),(typed,studies.TYPED),(absent,studies.ABSENT),(integration,studies.INTEGRATION),
      (svg_admission,studies.SVG_ADMISSION),(entrypoints,studies.ENTRYPOINT),(restore,studies.RESTORED),(extend,studies.EXTENSION),
      (profiles,profiles.RESULT),(handlers,handlers.RESULT),(source_recovery,source_recovery.RESULT),
      (focused,focused.RESULT),(flash,flash.RESULT),(schema_transfer,schema_transfer.RESULT))


def spending():
    batches={}
    total=Counter()
    for mod,summary in PAID:
        ledger=mod.OUT/'budget.sqlite3'
        actual=ledger_read.totals(ledger)
        assert read(summary)['cost']==actual
        by_model=defaultdict(lambda:defaultdict(Counter))
        for c in ledger_read.calls(ledger):
            kind=c['purpose'].split('/')[0]
            assert kind in ('plan','build')
            unit=dict(calls=1,settled_microusd=c['actual'] or 0,maximum_microusd=c['actual'] if c['actual'] is not None else c['reserved'],unresolved=int(c['actual'] is None))
            by_model[c['model']][kind].update(unit)
            total.update(unit)
        batches[str(summary.relative_to(ROOT))]=dict(result_sha256=sha(summary),registration_sha256=sha(mod.OUT/'registration.json'),charges=actual,by_model=by_model)
    assert total['maximum_microusd']<=10_000_000
    return dict(total=dict(total),batches=batches)


def snapshot(rows,arm):
    use=[r for r in rows if r['arm']==arm]
    passed=studies.outcomes(use,arm)
    return dict(passed=sum(v is True for v in passed.values()),observed=sum(v is not None for v in passed.values()),
                passed_targets=sorted(n for n,v in passed.items() if v is True),delivery=dict(Counter(r['status'] for r in use)))


def red_cells():
    matrix=read(ROOT/'studies/results/paper-performance-matrix.json')
    cells={}
    for file,label in ((studies.COMPACT,'menu'),(studies.VISIBLE,'visible')):
        for c in read(file)['cells']:
            p,t,a=(c[k] for k in ('project','tag','arm'))
            entry=cells.setdefault((p,t,a),dict(project=p,tag=t,model=c['model'],arm=a,targets=c['targets'],
                original=c['previous'],direct=c['direct'],original_status=dict(Counter(c['old_status'].values())),stages={}))
            entry['stages'][label]=dict(selected=snapshot(c['rows'],a),fixed=snapshot(c['rows'],'fixed'))
            if entry['stages'][label]['selected']['observed']==len(c['targets']):entry['stage']=label
    for file,label in ((studies.TYPED,'typed'),(studies.INTEGRATION,'integration'),(studies.ENTRYPOINT,'entrypoint')):
        for c in read(file)['cases']:
            for t,d in c['deploy'].items():
                item=cells.get((c['project'],t,c['arm']))
                if item is None:continue
                subset=[r for r in c['rows'] if r['tag']==t]
                data=dict(build=c['status'],selected=snapshot(subset,'planned'),fixed=snapshot(subset,'fixed'))
                item['stages'][label]=data
                if c['status']=='valid' and data['selected']['observed']==len(d['targets']):
                    item['stage']=label
    for entry in cells.values():
        g=matrix[entry['model']]['component_followup'][entry['project']]
        scores=entry['stages'][entry['stage']]
        assert g['targets']==entry['targets'] and g['passed'][entry['arm']]==scores['selected']['passed']
        g=matrix[entry['model']].get('extended_targets',{}).get(entry['project'],g)
        entry['paper']=dict(passed=g['passed'][entry['arm']],targets=g['targets'])
    for path,stage,arm in ((profiles.RESULT,'profiles','gpt5-library'),(handlers.RESULT,'handlers','self'),
                           (source_recovery.RESULT,'installer','self'),(focused.RESULT,'focused','self')):
        for c in read(path)['cells' if arm=='gpt5-library' else 'cases']:
            entry=cells.get(('table',c['tag'],arm))
            if entry is None:continue
            targets=entry['targets']
            subset=[r for r in c['rows'] if r['task'] in targets]
            key=arm if arm=='gpt5-library' else 'planned'
            state=c.get('status','valid')
            entry['stages'][stage]=dict(build=state,selected=snapshot(subset,key),fixed=snapshot(subset,'fixed'))
            if state!='valid':continue
            observed=studies.outcomes(c['rows'],key)
            current=matrix[c['model']].get('table_protocol_followup',{})
            g=entry['paper']
            if all(observed.get(n) is not None for n in g['targets']):
                assert current['targets']==g['targets'] and current['passed'][arm]==sum(observed[n] for n in g['targets'])
                entry['stage']=stage
                entry['paper']=dict(passed=current['passed'][arm],targets=current['targets'])
    assert len(cells)==18
    return list(cells.values())


def flash_comparison():
    fields=('direct','human','gpt5-library','file-a','file-b')
    rows=read(flash.RESULT)['rows']
    previous=read(flash.PREVIOUS)['branches']
    outcomes={}
    for arm in fields:
        outcomes[arm]=snapshot(rows,arm)
        if arm in previous:
            fixed=previous[arm]['full_schedule']['fixed']['passed_tasks']
            assert fixed==outcomes[arm]['passed_targets']
            outcomes[arm]['fixed_passed_targets']=fixed
    for job in flash.register()['jobs']:
        received=flash.OUT/job['arm']/str(job['task'])/'call/transmission-1/request.json'
        assert read(received)['body']==dict(read(ROOT/job['request'])['body'],reasoning={'enabled':False})
    transfer=read(schema_transfer.RESULT)['cell']
    outcomes['gpt5-schema-prompt']=snapshot(transfer['rows'],'gpt5-library')
    outcomes['gpt5-fixed']=snapshot(transfer['rows'],'fixed')
    return outcomes


def report():
    restoration=read(studies.RESTORED)
    assert len(restoration['rows'])==42
    assert read(studies.EXTENSION)['restored_sha256']==sha(studies.RESTORED)
    ext=read(studies.EXTENSION)['records']
    return dict(red_cells=red_cells(),budget=spending(),flash_questionnaire=flash_comparison(),
        restored_statuses=dict(Counter(r['status'] for r in restoration['rows'])),
        extended_rows=sorted({(r['project'],r['tag']) for r in ext}),
        planned_benchmark_sha256=sha(studies.PLANNED),historical_todo_gpt5_build_usd=read(ROOT/'studies/results/blind-library.json')['builders']['openai/gpt-5']['library']['build_cost_usd'])


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    out=report()
    if args.write:core.save(OUTPUT,out)
    # JSON serializes the sorted project/tag pairs as arrays.
    import json
    assert read(OUTPUT)==json.loads(json.dumps(out))
    print(out['budget']['total'],out['restored_statuses'],len(out['red_cells']))
