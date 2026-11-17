"""Audit every listed test, preserving historical incompatibilities without exclusions."""
import hashlib
from pathlib import Path
from .run import OUT, ROOT, read, dump, digest, verify


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
    walk(report)
    return result


def main():
    inputs = verify()
    assert read(OUT / 'evaluation-complete.json')['inputs_sha256'] == digest(inputs)
    assert read(OUT / 'initial-layout-complete.json')['protocol_sha256'] == digest(read(OUT / 'initial-layout-extension.json'))
    assert hashlib.sha256(Path(__file__).with_name('init_extension.py').read_bytes()).hexdigest() == read(OUT / 'initial-layout-extension.json')['source_sha256']
    rows = []
    for prefix in inputs['rows']:
        folders = [(OUT / 'scores' / f'prefix-{prefix["prefix"]}', prefix['specs'])]
        if prefix['prefix']:
            folders.append((OUT / 'initial-layout-scores' / f'prefix-{prefix["prefix"]}', ['init']))
        for folder, expected in folders:
            report = folder / 'report.json'
            assert hashlib.sha256(report.read_bytes()).hexdigest() == read(folder / 'receipt.json')['report_sha256']
            cases = cases_by_file(read(report))
            assert set(cases) == set(expected), (prefix['prefix'], cases.keys(), expected)
            for name in expected:
                rows.append({'prefix': prefix['prefix'], 'spec': name, 'tests': cases[name],
                    'passed': all(c['passed'] for c in cases[name]), 'report': str(report.relative_to(ROOT))})
    assert len(rows) == 210
    result = {'scope': 'Twenty input pages, init plus all applicable earlier task files; original reference-prefix pages, no model calls. '
        'All raw assertions retained with no posthoc exclusions; this verifies these assertions, not all natural-language behavior.',
        'pairs': len(rows), 'passed_pairs': sum(r['passed'] for r in rows),
        'tests': sum(len(r['tests']) for r in rows), 'passed_tests': sum(c['passed'] for r in rows for c in r['tests']),
        'prefixes': [{'prefix': k, 'all_passed': all(r['passed'] for r in rows if r['prefix'] == k)} for k in range(20)],
        'rows': rows, 'unique_raw_reports': len({r['report'] for r in rows}),
        'playwright_version': inputs['playwright_version']}
    dump(ROOT / 'test/results/prefix-history-audit.json', result)
    print({k: v for k, v in result.items() if k not in ('rows', 'prefixes')})


if __name__ == '__main__':
    main()
