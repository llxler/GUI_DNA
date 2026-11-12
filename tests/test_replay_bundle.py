import hashlib
import json
from gui_dna.budget import Ledger
from test.export_replay_bundle import pseudonym, sanitize_ledger, transform


def test_expanded_export_includes_saved_modules_and_unusual_source_extensions(tmp_path, monkeypatch):
    import json
    from test import export_replay_bundle as exporter
    stage = tmp_path / 'artifacts/webbench-expand-run'
    page = stage / 'runs/project/model/task/version-0'
    page.mkdir(parents=True)
    (page / 'module.mjs').write_text('export const value = 1;')
    (page / 'generated.payload').write_text('saved source')
    (page / 'source-manifest.json').write_text(json.dumps({'files_sha256': {'module.mjs': 'hash', 'generated.payload': 'hash'}}))
    monkeypatch.setattr(exporter, 'ROOT', tmp_path)
    monkeypatch.setattr(exporter.subprocess, 'check_output', lambda *args, **kwargs: b'')
    selected = set(exporter.selected_files(expanded=True))
    assert page / 'module.mjs' in selected
    assert page / 'generated.payload' in selected
from test.ledger_read import calls, totals


def test_anonymous_ledger_preserves_costs_without_modifying_original(tmp_path):
    original, exported = tmp_path / 'original.sqlite3', tmp_path / 'exported.sqlite3'
    ledger = Ledger(original, .1, .09)
    call_id = ledger.reserve(.01, 'test /home/alice/example', 'model')
    ledger.settle(call_id, .004123, generation_id='gen-original-response')
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    sanitize_ledger(original, exported)
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    assert totals(original) == totals(exported)
    assert calls(exported)[0]['id'] == pseudonym(call_id)
    assert b'alice' not in exported.read_bytes()
    receipt = transform({'call_id': call_id, 'id': 'gen-original-response', 'path': '/home/alice/example'}, {call_id})
    assert receipt['call_id'] == calls(exported)[0]['id']
    assert 'alice' not in str(receipt)


def test_redaction_preserves_regex_literals_and_exported_utility(tmp_path):
    from pathlib import Path
    from test.export_replay_bundle import scrub, has_identity
    source = Path(__file__).resolve().parents[1] / 'test/export_replay_bundle.py'
    exported = scrub(source.read_text())
    assert not has_identity(exported.encode())
    namespace = {'__name__': 'anonymous_export_probe', '__file__': str(tmp_path / 'test/export_replay_bundle.py')}
    exec(compile(exported, 'anonymous_export.py', 'exec'), namespace)
    sample_home = '/' + 'home' + '/example-user/cache'
    assert namespace['scrub'](sample_home) == '/home/anonymous/cache'
    assert not namespace['has_identity'](b"assert '/home/' not in error")
    assert not namespace['has_identity'](b'/home/anonymous/cache')
    assert has_identity(sample_home.encode())
    assert not has_identity(b"re.compile(r'/home/[A-Za-z_][A-Za-z0-9_.-]*')")
