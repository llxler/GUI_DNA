"""Run the preselected container cohort under the artifact owner's UID/GID."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

from test.container_replay.run import ROOT, OUT as PARENT, verify as verify_parent
from test.history_replay.run import now, read, dump, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/container-replay-20261115-uid'


def prepare():
    verify_parent()
    assert not list((PARENT / 'outputs').iterdir()), 'Recovery is only authorized before any page observation'
    assert not (OUT / 'snapshot.json').exists() and not (OUT / 'inputs').exists()
    preflight = read(OUT / 'preflight/result.json')
    assert preflight['returncode'] == 0 and (OUT / 'preflight/write-test.txt').read_text() == 'ok'
    shutil.copytree(PARENT / 'inputs', OUT / 'inputs')
    shutil.copy2(PARENT / 'image.json', OUT / 'image.json')
    shutil.copy2(ROOT / 'artifacts/review-20261115/container-pipeline.log', OUT / 'parent-failure.txt')
    recovery = {'frozen_utc': now(), 'parent': str(PARENT.relative_to(ROOT)), 'original_pages_scored': 0,
                'reason': 'EACCES writing environment.json before the page loop; default root has no DAC override capabilities.',
                'uid': os.getuid(), 'gid': os.getgid(), 'image_id': read(OUT / 'image.json')['Id'],
                'inputs_sha256': sha(OUT / 'inputs/inputs.json'), 'parent_inputs_sha256': sha(PARENT / 'inputs/inputs.json')}
    assert recovery['inputs_sha256'] == recovery['parent_inputs_sha256']
    dump(OUT / 'recovery.json', recovery)
    paths = [HERE / n for n in ('run.py', '__init__.py', 'PROTOCOL.md')]
    paths += [OUT / n for n in ('recovery.json', 'image.json', 'parent-failure.txt', 'preflight/result.json')]
    paths += [PARENT / n for n in ('snapshot.json', 'launch.json')]
    paths += [p for p in (OUT / 'inputs').rglob('*') if p.is_file()]
    dump(OUT / 'snapshot.json', {'frozen_utc': now(), 'files': {str(p.relative_to(ROOT)): sha(p) for p in paths}})
    print('Frozen identical 19-page recovery with UID/GID', recovery['uid'], recovery['gid'], flush=True)


def verify():
    verify_parent()
    for path, value in read(OUT / 'snapshot.json')['files'].items():
        assert sha(ROOT / path) == value, path


def run():
    verify()
    assert not (OUT / 'outputs').exists(), 'Preserve observations, no overwriting'
    (OUT / 'outputs').mkdir()
    recovery = read(OUT / 'recovery.json')
    name = 'gui-dna-replay-20261115-uid'
    args = ['docker', 'run', '--name', name, '--rm', '--init', '--user', f'{recovery["uid"]}:{recovery["gid"]}',
            '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--shm-size', '1g',
            '--read-only', '--tmpfs', '/tmp:rw,nosuid,size=1g',
            '-v', str(OUT / 'inputs') + ':/inputs:ro', '-v', str(OUT / 'outputs') + ':/outputs:rw', recovery['image_id']]
    dump(OUT / 'launch.json', {'command': args, 'scope': 'Same fixed image and inputs; output-owner UID/GID only.'})
    try:
        subprocess.run(args, check=True, timeout=1200)
    except subprocess.TimeoutExpired:
        subprocess.run(['docker', 'stop', '--time', '10', name], check=False, timeout=30)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'run'])
    globals()[parser.parse_args().action]()
