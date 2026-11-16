"""Caching an export map must retain both provenance and live-file checks."""
import hashlib
import json
from pathlib import Path
import pytest
from test import replay_hashes as hashes


def digest(value):
    return hashlib.sha256(value).hexdigest()


def test_manifest_is_shared_but_modified_reports_still_fail(tmp_path,monkeypatch):
    monkeypatch.setattr(hashes,'ROOT',tmp_path)
    hashes._mapping.cache_clear()
    manifest=tmp_path/'REPLAY-MANIFEST.json'
    original=digest(b'original');exported=b'anonymous'
    mapping={}
    for name in ('one.json','two.json'):
        (tmp_path/name).write_bytes(exported)
        mapping[name]={'original_sha256':original,'exported_sha256':digest(exported)}
    manifest.write_text(json.dumps(mapping))
    reads=[];read_text=Path.read_text
    def counted(path,*args,**kwargs):
        if path==manifest:reads.append(path)
        return read_text(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',counted)
    for name in mapping:hashes.verify_report_hash(tmp_path/name,original)
    assert len(reads)==1
    (tmp_path/'one.json').write_bytes(b'changed after verification')
    with pytest.raises(AssertionError):hashes.verify_report_hash(tmp_path/'one.json',original)


def test_original_hash_is_required_and_replaced_manifest_invalidates_cache(tmp_path,monkeypatch):
    monkeypatch.setattr(hashes,'ROOT',tmp_path)
    hashes._mapping.cache_clear()
    report=tmp_path/'report.json';report.write_bytes(b'exported')
    manifest=tmp_path/'REPLAY-MANIFEST.json'
    value={'report.json':{'original_sha256':digest(b'original'),'exported_sha256':digest(b'exported')}}
    manifest.write_text(json.dumps(value))
    hashes.verify_report_hash(report,digest(b'original'))
    with pytest.raises(AssertionError):hashes.verify_report_hash(report,digest(b'wrong original'))
    value['report.json']['exported_sha256']=digest(b'incorrect export')
    replacement=tmp_path/'replacement.json';replacement.write_text(json.dumps(value));replacement.replace(manifest)
    with pytest.raises(AssertionError):hashes.verify_report_hash(report,digest(b'original'))
