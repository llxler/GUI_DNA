"""Include initial-layout assertions on every nonempty prefix as a separate frozen extension."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import subprocess

from .run import OUT, ROOT, read, dump, digest, now, verify, evaluate


def main():
    inputs = verify()
    protocol = OUT / 'initial-layout-extension.json'
    rows = [row for row in inputs['rows'] if row['prefix'] > 0]
    value = {'scope': 'Add init.spec.js to prefixes 1..19. Original 191 pair audit is unchanged; '
                      'these 19 checks cover initial-layout obligations too. No score-based exclusions or page edits.',
             'prefixes': [r['prefix'] for r in rows], 'inputs_sha256': digest(inputs),
             'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if protocol.exists():
        saved = read(protocol)
        assert {k: v for k, v in saved.items() if k != 'frozen_utc'} == value
    else:
        dump(protocol, {**value, 'frozen_utc': now()})
    def one(row):
        target = OUT / 'initial-layout-scores' / f'prefix-{row["prefix"]}'
        if (target / 'receipt.json').exists():
            return
        target.mkdir(parents=True, exist_ok=True)
        report = target / 'report.json'
        assert not report.exists(), 'Do not overwrite an interrupted report'
        server = evaluate.Server(ROOT / row['page'])
        try:
            env = {**evaluate.browser_env(), 'REPORT_FILE': str(report), 'CI': '1', 'WORKERS': '1',
                   'CANDIDATE_URL': f'http://127.0.0.1:{server.port}'}
            done = subprocess.run(['node', str(evaluate.HARNESS / 'node_modules/@playwright/test/cli.js'),
                'test', '--config', 'playwright.config.js', '--workers=1', '--output', str(target / 'playwright-output'),
                'dom1-tests/init.spec.js'], cwd=OUT / 'harness', env=env, capture_output=True, text=True, timeout=120)
        finally:
            server.close()
        (target / 'runner.txt').write_text(done.stdout + done.stderr)
        assert report.exists() and not read(report).get('errors')
        dump(target / 'receipt.json', {'exit_code': done.returncode, 'finished_utc': now(),
             'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest()})
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one, rows))
    dump(OUT / 'initial-layout-complete.json', {'finished_utc': now(), 'pairs': len(rows), 'protocol_sha256': digest(read(protocol))})
    print('Completed 19 additional initial-layout checks', flush=True)


if __name__ == '__main__':
    main()
