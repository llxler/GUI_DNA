"""Join the registered November 25 follow-ups to their original target-level controls."""
from collections import defaultdict
from copy import deepcopy
from studies.study_io import ROOT, read

WEB = ROOT/'studies/webbench'
SUITE = ROOT/'studies/public_library_transfer/compact_todomvc'
COMPACT = WEB/'compact_planning/result.json'
VISIBLE = COMPACT.parent/'visible_decoding/result.json'
TYPED = WEB/'typed_components/result.json'
ABSENT = TYPED.parent/'unavailable/result.json'
INTEGRATION = TYPED.parent/'integration-result.json'
SVG_ADMISSION = TYPED.parent/'svg-admission-result.json'
ENTRYPOINT = TYPED.parent/'entrypoint-result.json'
RESTORED = WEB/'transport_completion/result.json'
SMALL = SUITE/'result.json'
EVENTS = SUITE/'event_functions/result.json'
DELIVERY = EVENTS.parent/'delivery-result.json'
PLANNED = ROOT/'studies/webgen_bench/protocol.json'
EXTENSION = RESTORED.parent/'extension-result.json'
SOURCES = (COMPACT, VISIBLE, TYPED, ABSENT, INTEGRATION, SVG_ADMISSION, ENTRYPOINT, RESTORED, SMALL, EVENTS, DELIVERY, PLANNED)
LABELS = {'google/gemma-3-4b-it':'Gemma 3 4B', 'meta-llama/llama-3.2-3b-instruct':'Llama 3.2 3B',
          'mistralai/ministral-3b-2512':'Ministral 3B'}
GEMMA = 'google/gemma-3-12b-it'
QWEN9 = 'qwen/qwen3.5-9b'
FLASH = 'deepseek/deepseek-v4-flash'
TODO_ROSTER = (*LABELS,GEMMA,QWEN9,FLASH)


def outcomes(rows, arm):
    values={}
    for row in rows:
        if row['arm']!=arm:continue
        target=row['task']
        assert target not in values
        state=row['status']
        if state=='valid':
            assert type(row['passed']) is bool and len(row['report_sha256'])==64
            values[target]=row['passed']
        elif state=='invalid':
            assert row['passed'] is False
            values[target]=False
        else:
            assert state in ('build_failed','missing')
            values[target]=None
    return values


def attach(matrix):
    from studies.paper_performance import current_group, joint_scores
    def working(model,project):
        entry=matrix[model]
        by_project=entry.setdefault('component_followup',{})
        if project not in by_project:
            original=current_group(entry,project)
            group=deepcopy(original)
            if group.get('rep')=='a' and 'self' in group.get('passed',{}):
                group['markers']={'self':'rebuild'}
            by_project[project]=group
        return by_project[project]
    def replace(g,arm,counts,protocol):
        g['passed'][arm]=counts
        g.setdefault('markers',{})[arm]=protocol
        if arm in g.get('excluded_build_arms',[]):
            g['excluded_build_arms'].remove(arm)
    for file,stage in ((COMPACT,'menu'),(VISIBLE,'visible')):
        for c in read(file)['cells']:
            arm=c['arm']
            g=working(c['model'],c['project'])
            assert c['targets']==g['targets'] and g['passed']['direct']==c['direct']
            values=outcomes(c['rows'],arm)
            assert sorted(values)==c['targets']
            if all(v is not None for v in values.values()):
                count=sum(values.values())
                assert count==c[arm+'_passes']
                replace(g,arm,count,stage)
    for file in (TYPED,ABSENT,INTEGRATION,SVG_ADMISSION,ENTRYPOINT):
        for c in read(file)['cases']:
            for tag,d in c['deploy'].items():
                arm=c['arm']
                g=working(d['model'],c['project'])
                assert d['targets']==g['targets'] and g['passed']['direct']==d['direct']
                g.setdefault('build_attempts',{})[arm]=c['status']
                if c['status']!='valid':
                    if c['status']=='build_failed' and arm not in g['passed'] and arm not in g.get('excluded_build_arms',[]):
                        g.setdefault('excluded_build_arms',[]).append(arm)
                    continue
                vals=outcomes([r for r in c['rows'] if r['tag']==tag],'planned')
                assert sorted(vals)==d['targets']
                if all(v is not None for v in vals.values()):
                    replace(g,arm,sum(vals.values()),'typed')
                    g.setdefault('implementation_sources',{})[arm]=str(file.relative_to(ROOT))
    smaller=read(SMALL)['models']
    event=read(EVENTS)['models']
    delivery=read(DELIVERY)
    for model,data in smaller.items():
        if model not in LABELS:
            g=working(model,'todomvc')
            gpt=outcomes(data['rows'],'gpt5-library')
            assert set(g['targets'])==gpt.keys() and all(v is not None for v in gpt.values())
            replace(g,'gpt5-library',sum(gpt.values()),'blind')
            if model in event and event[model]['libraries']['a']=='valid':
                vals=outcomes(event[model]['rows'],'a')
                if all(vals[t] is not None for t in g['targets']):replace(g,'self',sum(vals.values()),'events')
            continue
        entry=matrix.setdefault(model,dict(current={},supplied={},sources={},retrospective={}))
        new=event[model]
        last=delivery['results'] if model==delivery['model'] else None
        arms={}
        for a in ('direct','human','gpt5-library'):
            vals=outcomes(data['rows'],a)
            for t,v in outcomes(new['rows'],a).items():
                assert vals[t] is None
                vals[t]=v
            if last:
                for t,v in outcomes(last['rows'],a).items():
                    assert vals[t] is None
                    vals[t]=v
            arms[a]=vals
        latest=last or new
        first=next((r for r in (latest,new,data) if r['libraries']['a']=='valid'),latest)
        if first['libraries']['a']=='valid':
            arms['self']=outcomes(first['rows'],'a')
        group=joint_scores(arms,allow_direct_only=True)
        if group is None:
            group=dict(targets=[],n=0,passed={})
        group['build_attempts']={'self':latest['libraries']['a']}
        if first['libraries']['a']=='build_failed':group['excluded_build_arms']=['self']
        group['markers']={'self':'events'} if 'self' in group['passed'] and first is not data else {}
        entry.setdefault('component_followup',{})['todomvc']=group
    return matrix


def extend(matrix):
    """An extra target counts only if all displayed methods produced an observation."""
    from studies.paper_performance import current_group
    grouped=defaultdict(dict)
    for row in read(EXTENSION)['records']:
        pair=(row['model'],row['project'])
        assert row['arm'] not in grouped[pair]
        grouped[pair][row['arm']]=row
    for (model,project),arms in grouped.items():
        entry=matrix[model]
        initial=entry.get('component_followup',{}).get(project,current_group(entry,project))
        assert set(initial['passed'])==set(arms)
        requested=sorted(set(range(1,21))-set(initial['targets']))
        eligible=[n for n in requested if all(type(row['observations'][str(n)]) is bool for row in arms.values())]
        group=deepcopy(initial)
        for a,r in arms.items():
            assert initial['targets']==r['initial_targets'] and initial['passed'][a]==r['initial_passes']
            assert requested==r['targets'] and {int(k) for k in r['observations']}==set(requested)
            group['passed'][a]+=sum(r['observations'][str(n)] for n in eligible)
        group.update(targets=sorted(initial['targets']+eligible),n=initial['n']+len(eligible),
                     original_targets=initial['targets'],additional_targets=eligible)
        entry.setdefault('extended_targets',{})[project]=group
