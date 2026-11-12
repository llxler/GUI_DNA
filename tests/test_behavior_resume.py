"""Recover the frozen manifest comparison without allowing real input changes."""
import pytest
from test.behavior_feedback_resume import canonical_protocol
from test.review_stage import freeze


def test_resume_accepts_json_equivalence_but_rejects_changed_inputs(tmp_path):
    config = {'models': ['example/model'], 'max_tokens': 12000}
    protocol = {'milestones': (4, 8, 12, 16, 20), 'methods': ['free_lib', 'plan']}
    freeze(tmp_path, config, [], protocol)
    saved = (tmp_path / 'review-manifest.json').read_bytes()
    with pytest.raises(ValueError, match='generation inputs changed'):
        freeze(tmp_path, config, [], protocol)
    freeze(tmp_path, config, [], canonical_protocol(protocol))
    assert (tmp_path / 'review-manifest.json').read_bytes() == saved
    assert isinstance(protocol['milestones'], tuple)
    with pytest.raises(ValueError, match='generation inputs changed'):
        freeze(tmp_path, {**config, 'max_tokens': 24000}, [], canonical_protocol(protocol))
    with pytest.raises(ValueError, match='generation inputs changed'):
        freeze(tmp_path, config, [], canonical_protocol({**protocol, 'milestones': (4, 8, 12)}))
