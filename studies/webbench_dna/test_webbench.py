"""Offline checks for the Web-Bench dom1 stage (no API, no browser).  Run: uv run pytest test/webbench_dna -q"""
import hashlib
import json

import pytest

from test.webbench_dna import domain, evaluate
from test.webbench_dna.library import FEATURES, SLOTS, library

LIB = library()


def test_tasks_follow_the_official_ladder():
    tasks = domain.tasks()
    assert [t['id'] for t in tasks] == [f'task-{k}' for k in range(1, 21)]
    assert tasks[-1]['features'] == FEATURES and len(tasks[4]['descriptions']) == 5
    official = domain.official_tasks()
    assert all(official[t['id']]['description'] in t['descriptions'][-1] for t in tasks)


def test_official_specs_are_verbatim_copies():
    specs = sorted((evaluate.HARNESS / 'dom1-tests').glob('*.spec.js'))
    assert len(specs) == 21
    upstream = domain.ROOT / 'artifacts/web-bench/projects/dom1/test'
    if upstream.exists():
        for spec in specs:
            assert hashlib.sha256(spec.read_bytes()).hexdigest() == hashlib.sha256((upstream / spec.name).read_bytes()).hexdigest()


def test_reference_plan_compiles_for_every_task_and_rule_differs_where_variants_matter():
    for task in domain.tasks():
        ref = domain.compile_plan(domain.reference_plan(task['features']), task['features'], LIB)
        rule = domain.compile_plan(domain.rule_plan(task['features']), task['features'], LIB)
        assert 'toolsInit(' in ref and 'toolsInit(' in rule
        if task['k'] >= 4:
            assert ref != rule
    k1 = domain.compile_plan(domain.reference_plan(FEATURES[:1]), FEATURES[:1], LIB)
    assert 'menuInit' not in k1 and 'fileAdd' not in k1 and json.dumps(['file', 'dir', 'del']) in k1


def test_checked_compiler_reports_missing_coverage_and_drops_disabled_items():
    features = FEATURES[:7]  # up to menuEntry
    plan = domain.reference_plan(features)
    missing = {**plan, 'menu': {**plan['menu'], 'dir': ['add file', 'add dir']}}
    with pytest.raises(ValueError, match="needs menu command\\(s\\) \\['delete'\\] for dir"):
        domain.compile_plan(missing, features, LIB)
    with pytest.raises(ValueError, match='needs "delete" set to one of'):
        domain.compile_plan({k: v for k, v in plan.items() if k != 'delete'}, features, LIB)
    with pytest.raises(ValueError, match='not an allowed variant'):
        domain.compile_plan({**plan, 'drag': 'fileAdd'}, features, LIB)
    code = domain.compile_plan(plan, features, LIB)   # shortcuts / resizer / filter belong to later tasks: dropped silently
    assert 'shortcutsInit' not in code and 'resizerShow' not in code and 'filterContains' not in code and '"entries": []' not in code
    assert '"entries"' not in json.loads(code.split('const MENU = ')[1].split(';')[0])


def test_prompts_never_mention_tests_and_variants_are_sorted():
    for task in domain.tasks()[::5]:
        text = '\n'.join(m['content'] for m in domain.messages_for(task, 'dna', LIB))
        assert 'spec.js' not in text and 'reference_plan' not in text and 'toHaveClass' not in text
        assert task['descriptions'][-1] in text
    for options in SLOTS.values():
        assert options == sorted(options) and len(options) == 2
