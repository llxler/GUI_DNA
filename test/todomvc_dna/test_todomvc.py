"""Offline checks for the TodoMVC stage (no API, no browser).  Run: uv run pytest test/todomvc_dna -q"""
import re

import pytest

from test.todomvc_dna import domain, evaluate
from test.todomvc_dna.library import library

LIB = library()
SPEC = (evaluate.HARNESS / 'demo-todo-app.original.spec.ts').read_text()


def official_titles():
    """(describe, title) pairs parsed from the official spec file."""
    out, current = [], None
    for line in SPEC.splitlines():
        m = re.match(r"test\.describe\('([^']+)'", line)
        if m:
            current = m.group(1)
        m = re.match(r"\s+test\('([^']+)'", line)
        if m:
            out.append((current, m.group(1)))
    return out


def test_feature_map_covers_exactly_the_official_tests():
    assert set(domain.TEST_FEATURES) == set(official_titles())
    assert len(official_titles()) == 24


def test_harness_spec_differs_from_the_official_one_only_in_the_goto_line():
    original = SPEC.splitlines()
    patched = (evaluate.HARNESS / 'demo-todo-app.spec.ts').read_text().splitlines()
    diff = [(a, b) for a, b in zip(original, patched) if a != b]
    assert len(original) == len(patched) and len(diff) == 1 and 'demo.playwright.dev/todomvc' in diff[0][0] and 'CANDIDATE_URL' in diff[0][1]


def test_reference_and_rule_plans_compile_for_every_task_and_differ():
    for task in domain.tasks():
        ref = domain.compile_plan(domain.reference_plan(task['features']), task['features'], LIB)
        rule = domain.compile_plan(domain.rule_plan(task['features']), task['features'], LIB)
        assert 'window.candidate' in ref and ref != rule
        assert len(domain.hidden_subset(task['features'])) >= 4


def test_checked_compiler_rejects_missing_route_and_wrong_variant_with_public_hints():
    features = ['toggle', 'routing']
    plan = domain.reference_plan(features)
    missing = {**plan, 'handlers': {k: v for k, v in plan['handlers'].items() if k != 'route'}}
    with pytest.raises(ValueError, match='missing: \\["route"\\]'):
        domain.compile_plan(missing, features, LIB)
    wrong = {**plan, 'handlers': {**plan['handlers'], 'toggle': 'visibleAll'}}
    with pytest.raises(ValueError, match='invalid: \\["toggle"\\]'):
        domain.compile_plan(wrong, features, LIB)
    with pytest.raises(ValueError, match='unknown function'):
        domain.compile_plan({**plan, 'init': 'nope'}, features, LIB)
    # Routes for disabled events are dropped silently (feature-aware linking), unchecked mode skips coverage.
    extra = {**plan, 'handlers': {**plan['handlers'], 'clearCompleted': 'clearAll'}}
    assert "case 'clearCompleted'" not in domain.compile_plan(extra, features, LIB)
    assert 'window.candidate' in domain.compile_plan(missing, features, LIB, checked=False)


def test_prompts_never_contain_hidden_test_titles_or_the_spec_file():
    titles = [t for _, t in official_titles()]
    for task in domain.tasks():
        for method in ['free', 'dna']:
            text = '\n'.join(m['content'] for m in domain.messages_for(task, method, LIB))
            assert 'demo-todo-app' not in text and 'getByTestId' not in text
            for title in titles:
                assert title not in text
            assert 'reference_plan' not in text
    # The two arms share the requirement and the interface byte for byte.
    free = domain.messages_for(domain.tasks()[3], 'free', LIB)[1]['content']
    dna = domain.messages_for(domain.tasks()[3], 'dna', LIB)[1]['content']
    assert dna.startswith(free.split('\n\nReturn the complete')[0])


def test_library_variants_are_documented_and_rule_default_is_alphabetical():
    from test.todomvc_dna.library import AFTERS, INITS, ROUTES, VIEWS
    names = {f['name'] for f in LIB['functions']}
    for table in [*ROUTES.values(), INITS, *VIEWS.values()]:
        assert set(table) <= names and table == sorted(table)
    assert set(AFTERS) <= names
