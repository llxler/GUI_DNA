from studies.schema_search.finite import population
from test.webbench_expand.schema import validate


def test_finite_population_keeps_omission_false_and_each_enum_distinct():
    schema = {'type': 'object', 'properties': {
        'theme': {'type': 'string', 'enum': ['light', 'dark']},
        'enabled': {'type': 'boolean'}}, 'required': [], 'additionalProperties': False}
    plans = population(schema)
    assert len(plans) == 9
    assert {} in plans and {'enabled': False} in plans and {'enabled': True} in plans
    for theme in ('light', 'dark'):
        assert {'theme': theme} in plans
        assert {'theme': theme, 'enabled': False} in plans
        assert {'theme': theme, 'enabled': True} in plans
    for plan in plans:
        validate(schema, plan)


def test_report_hash_requires_explicit_original_to_exported_mapping(tmp_path, monkeypatch):
    import hashlib
    import json
    import pytest
    from studies import replay_hashes as analyze
    monkeypatch.setattr(analyze, 'ROOT', tmp_path)
    report = tmp_path / 'report.json'
    original = hashlib.sha256(b'original report').hexdigest()
    report.write_bytes(b'anonymized report')
    with pytest.raises(AssertionError):
        analyze.verify_report_hash(report, original)
    mapping = {'report.json': {'original_sha256': original,
                              'exported_sha256': hashlib.sha256(report.read_bytes()).hexdigest()}}
    (tmp_path / 'REPLAY-MANIFEST.json').write_text(json.dumps(mapping))
    analyze.verify_report_hash(report, original)
    report.write_bytes(b'tampered report')
    with pytest.raises(AssertionError):
        analyze.verify_report_hash(report, original)
