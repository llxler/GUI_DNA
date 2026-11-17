"""Posthoc blank-page environment probe; does not rerun any benchmark page.

After the fixed 19-page replay, BOM reference task-17 differed on its default
online indicator. Freeze both Docker network modes before probing navigator's
default flag on a data URL. No external navigation or connectivity claim.
"""
import json
import os
from pathlib import Path
import subprocess

from test.history_replay.run import ROOT, now, read, dump, sha

OUT = ROOT / 'artifacts/container-network-probe-20261115'
CODE = """const {chromium}=require('/opt/replay/node_modules/playwright');
(async()=>{const browser=await chromium.launch();const page=await browser.newPage();
await page.goto('data:text/html,<title>environment probe</title>');
console.log(JSON.stringify({navigator_online:await page.evaluate(()=>navigator.onLine),
chromium:browser.version(),url:page.url()}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});"""


def main():
    assert not OUT.exists(), 'Preserve observations, no overwrite'
    assert (ROOT / 'artifacts/container-replay-20261115-uid/outputs/complete.json').exists()
    image_path = ROOT / 'artifacts/container-replay-20261115/image.json'
    image = read(image_path)['Id']
    inputs = {'posthoc': True, 'image_id': image, 'uid': os.getuid(), 'gid': os.getgid(),
              'network_modes': ['none', 'bridge'], 'program': CODE,
              'scope': 'Blank data URL only, no external navigation, no benchmark scoring. navigator.onLine is an environment hint, not proof of Internet connectivity.'}
    dump(OUT / 'inputs.json', inputs)
    paths = [Path(__file__).resolve(), OUT / 'inputs.json', image_path]
    dump(OUT / 'snapshot.json', {'frozen_utc': now(), 'sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths}})
    rows = []
    for mode in inputs['network_modes']:
        args = ['docker', 'run', '--rm', '--init', '--user', f'{inputs["uid"]}:{inputs["gid"]}',
                '--network', mode, '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--read-only', '--shm-size', '1g', '--tmpfs', '/tmp:rw,nosuid,size=1g', image, 'node', '-e', CODE]
        done = subprocess.run(args, capture_output=True, text=True, timeout=60)
        raw = {'command': args, 'exit_code': done.returncode, 'stdout': done.stdout, 'stderr': done.stderr}
        dump(OUT / f'{mode}.json', raw)
        assert done.returncode == 0, raw
        rows.append({'network': mode, **json.loads(done.stdout)})
    result = {**inputs, 'observations': rows, 'benchmark_pages_reexecuted': 0}
    dump(ROOT / 'test/results/container-network-probe.json', result)
    dump(OUT / 'complete.json', {'finished_utc': now(), 'observations': len(rows)})
    print(rows)


if __name__ == '__main__': main()
