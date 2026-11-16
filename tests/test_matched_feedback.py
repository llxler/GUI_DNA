"""Protocol boundary checks before any paid matched-feedback generation."""
from pathlib import Path
import json

from test.matched_feedback import core


def test_only_public_test_sources_are_read_for_prompts(monkeypatch):
    real = Path.read_text
    test_paths = []
    def guarded(path, *args, **kwargs):
        if path.name.endswith('.spec.js'):
            test_paths.append(path.name)
            assert path.name.removesuffix('.spec.js') in core.PUBLIC
        return real(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded)
    package = {'plan_schema': {'type': 'object'}, 'files': {}, 'compiler': 'stub'}
    for project in core.PROJECTS:
        a = core.messages(project, 'plan', package)
        b = core.messages(project, 'free_lib', package)
        assert a[1] == b[1]
        free = core.messages(project, 'free', None)
        assert '"compiler": "stub"' not in free[1]['content']
    assert set(test_paths) == {p + '.spec.js' for p in core.PUBLIC}


def test_independent_free_denominator_and_sampling_schedule():
    jobs = core.jobs()
    assert len(jobs) == 30 and len({j['folder'] for j in jobs}) == 30
    assert sum(j['method'] == 'free' for j in jobs) == 6
    assert sum(j['method'] == 'plan' for j in jobs) == 12
    assert sum(j['method'] == 'free_lib' for j in jobs) == 12
    for project in core.PROJECTS:
        for seed in core.SEEDS:
            group = [j for j in jobs if j['project'] == project and j['seed'] == seed]
            assert len(group) == 5 and sum(j['builder'] is None for j in group) == 1


def test_frontier_adapter_keeps_cohort_separate_and_restores_original():
    from test.matched_feedback_frontier.adapt import configured, configuration
    before = core.jobs()
    with configured():
        adapted = core.jobs()
        assert len(adapted) == 15
        assert all(j['model'] == 'openai/gpt-5' for j in adapted)
        assert all('/matched-feedback-frontier-' in j['folder'] for j in adapted)
        assert sum(j['method'] == 'free' for j in adapted) == 3
        assert configuration()['omit_params']['openai/gpt-5'] == ['temperature','seed']
    assert core.jobs() == before
