"""Shared JSON, provenance and Playwright-report helpers; no experiment scheduler."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / 'artifacts/web-bench'


def now():
    return datetime.now(timezone.utc).isoformat()

def read(path):
    return json.loads(Path(path).read_text())

def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def cases_by_file(report):
    result = {}
    def walk(suite):
        for spec in suite.get('specs', []):
            name = Path(spec['file']).name.removesuffix('.spec.js')
            for test in spec.get('tests', []):
                statuses = [r['status'] for r in test.get('results', [])]
                result.setdefault(name, []).append({'title': spec['title'], 'statuses': statuses,
                    'passed': bool(statuses) and all(s == 'passed' for s in statuses)})
        for child in suite.get('suites', []):
            walk(child)
    for suite in report.get('suites', []):
        walk(suite)
    return result

def source_files(page, expert=False):
    if expert:
        names = ['index.html']
        if (page / 'candidate.js').exists():
            names.append('candidate.js')
        return {n: sha(page / n) for n in names}
    manifest = page / 'source-manifest.json'
    if manifest.exists():
        files = read(manifest)['files_sha256']
    else:
        files = {p.relative_to(page).as_posix(): sha(p) for p in page.rglob('*') if p.is_file()}
    assert all(sha(page / n) == h for n, h in files.items()), str(page)
    return files
