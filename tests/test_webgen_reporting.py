from studies.webgen_bench.report import ARMS, matched, table_summary


def test_functional_scores_separate_start_failure_partial_and_unevaluated():
    cases = {
        'direct':[('judged','YES'),('start_failed',None),('judged','NO')],
        'human':[('judged','PARTIAL'),('judged','YES'),('missing',None)],
        'gpt5-library':[('missing',None)]*3,
        'self':[('build_failed',None)]*3,
    }
    rows=[dict(site='s',check=i,arm=a,status=status,verdict=v)
          for a in ARMS for i,(status,v) in enumerate(cases[a])]
    result=matched(rows)
    assert result['targets']==['s/0','s/1']
    assert result['methods']['direct']['points']==1
    assert result['methods']['direct']['start_failed_in_common']==1
    assert result['methods']['human']['points']==1.5
    assert 'points' not in result['methods']['self']
    assert 'points' not in result['methods']['gpt5-library']


def test_table_replay_retains_both_directions_of_disagreement():
    rows=[dict(task=i,arm=arm,passed=i in passes)
          for arm,passes in {'direct':set(),'self-a':{1,3},'fixed-a':{1,7}}.items()
          for i in range(1,21)]
    result=table_summary(dict(rows=rows,libraries={'a':dict(status='valid',checks=['selection'])}))
    assert result['libraries']['a']['planned_only']==[3]
    assert result['libraries']['a']['fixed_only']==[7]


def test_svg_row_retains_both_frozen_library_and_self_interventions():
    from studies.public_library_transfer.source_diagnosis import report
    from studies.study_io import ROOT, read

    model = 'qwen/qwen3.5-9b'
    data = read(report.OUTPUT)
    displayed = read(ROOT/'studies/results/paper-performance-matrix.json')[model]['source_diagnosis']['svg-chart']
    frozen = data['web']['svg-chart']
    own = data['svg_attributes'][model]
    assert set(displayed['targets']) == set(frozen['targets']) == set(own['targets'])
    assert displayed['passed']['gpt5-library'] == len(frozen['arms']['gpt5-library']['passes']) == 15
    assert displayed['passed']['self'] == len(own['arms']['planned']['passes'])
    assert len(data['initial_visible_reversals']) == 12


def test_qwen_holdout_keeps_startup_failures_and_jointly_runnable_scores():
    from studies.lookup import MATRIX, find_cell
    from studies.study_io import ROOT, read

    matrix = read(ROOT / MATRIX)
    model = 'qwen/qwen3.5-9b'
    for arm, points in [('direct', 6.5), ('human', 8.5), ('self', 10.5)]:
        cell = find_cell(matrix, 'webgen-bench/heldout', model, arm)
        assert (cell['score'], cell['denominator']) == (points, 21)
        assert cell['jointly_runnable'] == {'score': 6.5, 'denominator': 14}
        assert cell['startup_failures'] == (7 if arm == 'direct' else 0)


def test_native_html_sensitivity_keeps_unjudged_checks_out_of_the_comparison(tmp_path, monkeypatch):
    from studies.study_io import dump, sha
    from studies.webgen_bench.component_contracts import report

    monkeypatch.setattr(report, 'NATIVE_HTML', tmp_path)
    dump(tmp_path/'candidates.json', {'records': {'holdout': {'site': 'b'}}})
    digest = sha(tmp_path/'candidates.json')
    dump(tmp_path/'browser.json', {'candidates': digest, 'observations': {'holdout': [{}]}})
    changes = [dict(batch='holdout', site='b', check=0, status='judged', verdict='PARTIAL'),
               dict(batch='holdout', site='b', check=1, status='missing', verdict=None)]
    dump(tmp_path/'judgments.json', dict(candidates=digest, model='judge', rows=changes))
    group = {'n': 3, 'methods': {'direct': {'points': 1}}}
    web = {'judge': 'judge', 'cohorts': {'holdout': {'qwen/qwen3.5-9b': group}}}
    original = []
    for site, check, direct_status, own_verdict in [('a',0,'judged','YES'), ('b',0,'start_failed','NO'),
                                                     ('b',1,'start_failed','YES')]:
        shared = dict(batch='holdout', model='qwen9', site=site, check=check)
        original.extend([dict(**shared, arm='direct', status=direct_status),
                         dict(**shared, arm='self', status='judged', verdict=own_verdict)])
    result = report.native_direct_scores(web, original)['holdout']
    assert (result['direct'], result['self'], result['matched_n']) == (1.5, 1, 2)
    assert result['direct_bounds'] == [1.5, 2.5] and result['full_n'] == 3


def test_full_operation_passes_match_targets_before_counting():
    from studies.webgen_bench.site_completion.report import summarize
    outcomes = {
        'direct': [('judged','YES'),('judged','PARTIAL'),('start_failed',None),('judged','YES')],
        'human': [('judged','PARTIAL'),('judged','YES'),('judged','YES'),('missing',None)],
        'gpt5-library': [('build_failed',None)]*4, 'self': [('judged','NO')]*4,
    }
    rows = [dict(site='x', check=i, arm=a, status=status, verdict=verdict)
            for a,seq in outcomes.items() for i,(status,verdict) in enumerate(seq)]
    result = summarize(rows)
    assert result['targets'] == ['x/0','x/1','x/2']
    assert result['methods']['direct']['passed'] == 1
    assert result['methods']['human']['passed'] == 2
    assert result['methods']['self']['passed'] == 0
    assert 'passed' not in result['methods']['gpt5-library']
    assert result['jointly_runnable']['passed'] == dict(direct=1,human=1,self=0)
    assert result['paired_vs_first']['human'] == {'direct_only':['x/0'],'method_only':['x/1','x/2']}


def test_sdk_layout_replaces_all_and_only_human_even_when_verdict_missing():
    import pytest
    from studies.webgen_bench.site_completion.report import replace_human
    def observation(arm,site,verdict):
        return dict(model='m',site=site,check=0,arm=arm,verdict=verdict)
    original=[observation(a,s,'YES') for a in ('direct','human','self') for s in ('a','b')]
    replacement=[observation('human','a',None),observation('human','b','NO')]
    fixed=replace_human(original,replacement)
    assert [r['verdict'] for r in fixed if r['arm']=='human']==[None,'NO']
    assert [r for r in fixed if r['arm']!='human']==[r for r in original if r['arm']!='human']
    with pytest.raises(ValueError):
        replace_human(original,replacement[:1])
    with pytest.raises(ValueError):
        replace_human(original,replacement+[replacement[0]])


def test_published_sdk_cell_uses_new_layout_and_three_unmodified_controls():
    from studies.lookup import MATRIX, find_cell
    from studies.study_io import ROOT, read
    from studies.webgen_bench.site_completion import report
    matrix=read(ROOT/MATRIX)
    model='deepseek/deepseek-v4-flash'
    fields=matrix[model]['webgen_completion']
    eligible=set(fields['targets'])
    for arm in ('direct','human','gpt5-library','self'):
        item=find_cell(matrix,'webgen-bench',model,arm)
        src=ROOT/item['method_record']
        assert src==(report.VERTICAL if arm=='human' else report.JUDGMENTS)
        if arm=='human':
            assert item['candidate_variant']=='vertical'
        sources=read(src)['rows']
        for extra in item.get('supplemental_records',[]):
            replacements={ (r['model'],r['site'],r['check'],r['arm']):r for r in read(ROOT/extra)['rows'] }
            sources=[replacements.get((r['model'],r['site'],r['check'],r['arm']),r) for r in sources]
        records=[r for r in sources if r['arm']==arm and r['model']=='deepseek-flash'
                 and r['site']+'/'+str(r['check']) in eligible]
        assert item['score']==sum(r['verdict']=='YES' for r in records)
        assert item['unit']=='fully passed operations'
        assert item['denominator']==len(records)==len(eligible)


def test_table_preserves_registered_gpt5_source_when_first_repair_fails_admission():
    from studies.lookup import MATRIX, find_cell
    from studies.paper_module_rebuilds import TABLE as COMBINED_RESULT
    from studies.study_io import ROOT, read
    from studies.webbench.table.menu_propagation.author_repair import report

    matrix=read(ROOT/MATRIX)
    original_protocol = {
        model: {key: study for key, study in entry.items() if key != "module_rebuilds"}
        for model, entry in matrix.items()
    }
    trials=report.reconstruct()
    assert set(trials)=={'b'}
    for tag,model in read(report.RESULT)['generators'].items():
        cell=find_cell(original_protocol,'web-bench/table',model,'gpt5-library')
        assert ROOT/cell['method_record']==report.ORIGINAL
        assert cell['denominator']==20 and cell['score']==len(trials['b']['planned'][tag]['original'])
        revised = find_cell(matrix, 'web-bench/table', model, 'gpt5-library')
        assert ROOT / revised['method_record'] == COMBINED_RESULT
        prior_model, prior_protocol = cell['row_keys']
        assert revised['targets'] == matrix[prior_model][prior_protocol]['targets']
