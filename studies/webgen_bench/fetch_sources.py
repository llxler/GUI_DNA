"""Fetch the exact public dataset, evaluator and browser SDK used by the pilot."""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

from studies.study_io import ROOT, read, sha


HERE = Path(__file__).resolve().parent
DEST = ROOT / 'artifacts/webgen-bench'
SDK_VERSION = '6.13.0'
SDK_INTEGRITY = 'KRE5e6dfnaVyoBagrgSl8lcW7OsZcTAzVx0EVCInpayMsuiorO44LABMRhTvi9IBk9DhjzgczBKj6frnQ4pJsQ=='


def verified_download(url, dest, algorithm, expected):
    dest.parent.mkdir(parents=True, exist_ok=True)

    def digest(file):
        with file.open('rb') as stream:
            return hashlib.file_digest(stream, algorithm).digest()

    if dest.exists():
        if digest(dest) != expected:
            raise ValueError(f'Existing file has a different digest: {dest}')
        return
    with NamedTemporaryFile(dir=dest.parent, delete=False) as tmp:
        incoming = Path(tmp.name)
    try:
        with urlopen(url, timeout=90) as response, incoming.open('wb') as out:
            shutil.copyfileobj(response, out)
        if digest(incoming) != expected:
            raise ValueError(f'Download hash mismatch: {url}')
        incoming.replace(dest)
    finally:
        incoming.unlink(missing_ok=True)


def prepare():
    spec = read(HERE / 'protocol.json')
    verified_download(spec['source'].replace('/tree/', '/resolve/') + '/' + spec['file'],
                      DEST / 'test.parquet', 'sha256', bytes.fromhex(spec['sha256']))
    upstream, commit = spec['evaluation'].split('/tree/')
    checkout = DEST / 'evaluator'
    if not checkout.exists():
        subprocess.run(['git', 'clone', '--no-checkout', upstream, str(checkout)], check=True)
        subprocess.run(['git', '-C', str(checkout), 'checkout', '--detach', commit], check=True)
    git = ['git', '-C', str(checkout)]
    if subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip() != commit:
        raise ValueError('Existing upstream checkout has a different revision')
    subprocess.run(git + ['diff', '--quiet', 'HEAD', '--', 'src', 'webvoyager'], check=True)
    tarball = DEST / 'packages' / f'amis-{SDK_VERSION}.tgz'
    verified_download(f'https://registry.npmjs.org/amis/-/amis-{SDK_VERSION}.tgz', tarball,
                      'sha512', base64.b64decode(SDK_INTEGRITY))
    folder = tarball.with_suffix('')
    with tarfile.open(tarball) as archive:
        for member in archive:
            relative = Path(member.name).relative_to('package')
            if not member.isfile() or not relative.parts or '..' in relative.parts:
                continue
            if relative.parts[0] != 'sdk' and relative != Path('package.json'):
                continue
            target = folder / relative
            if not target.resolve().is_relative_to(folder.resolve()):
                raise ValueError(f'Invalid extraction target {relative}')
            data = archive.extractfile(member).read()
            if target.exists():
                if target.read_bytes() != data:
                    raise ValueError(f'Existing SDK file differs: {target}')
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
    return dict(dataset=sha(DEST / 'test.parquet'), evaluator=commit, sdk=sha(folder / 'sdk/sdk.js'))


if __name__ == '__main__':
    print(json.dumps(prepare(), indent=2))
