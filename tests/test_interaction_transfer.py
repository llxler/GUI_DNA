"""Input isolation and deterministic-control invariants for the new study."""
import pytest
from test.interaction_transfer import core,domain
from test.interaction_transfer.controls import merge


def test_builder_never_reads_target(monkeypatch):
    monkeypatch.setattr(core,'target',lambda _: (_ for _ in ()).throw(AssertionError('target leaked')))
    for project in domain.PROJECTS:
        for condition in core.CONDITIONS:
            content=str(core.builder_messages(project,condition))
            assert 'heldout-' not in content
            assert 'full-application' not in content
            assert 'public_cases' in content


def test_same_library_user_messages_identical():
    package={'example':'same bytes'}
    for project in domain.PROJECTS:
        assert core.messages_for(project,'plan',package)[1]==core.messages_for(project,'free_lib',package)[1]


def test_fixed_merge_preserves_inputs_and_rejects_conflicts():
    first={'ops':['create'],'shared':{'key':'id'}}
    second={'ops':['create','delete'],'shared':{'key':'id'}}
    assert merge(first,second)=={'ops':['create','delete'],'shared':{'key':'id'}}
    assert first['ops']==['create']
    with pytest.raises(ValueError):merge({'key':'id'},{'key':'index'})
    with pytest.raises(ValueError):merge(True,1)
