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
