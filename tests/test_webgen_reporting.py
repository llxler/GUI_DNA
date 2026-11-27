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
