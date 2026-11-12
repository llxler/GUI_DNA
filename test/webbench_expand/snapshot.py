"""Hash complete candidate observations before any hidden scoring."""
from __future__ import annotations
import hashlib
import json
from .core import ROOT, dump


def main():
    for name in ('webbench-expand-run', 'webbench-expand-frontier-2'):
        stage = ROOT / 'artifacts' / name
        barrier = stage / 'generation-complete.json'
        assert json.loads(barrier.read_text())['transport_incomplete'] == 0
        target = stage / 'candidate-files-sha256.json'
        if target.exists():
            saved = json.loads(target.read_text())
            assert hashlib.sha256(barrier.read_bytes()).hexdigest() == saved['generation_sha256']
            for path, sha in saved['files'].items():
                assert hashlib.sha256((stage / path).read_bytes()).hexdigest() == sha, path
        else:
            assert not (stage / 'grading-started.json').exists(), 'Cannot retrospectively claim a pre-grading snapshot'
            files = {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((stage / 'runs').rglob('*')) if p.is_file()}
            dump(target, {'generation_sha256': hashlib.sha256(barrier.read_bytes()).hexdigest(),
                'scope': 'Complete used candidate files, including requests/responses and public outputs, hashed before hidden grading.', 'files': files})
            saved = json.loads(target.read_text())
        print(name, 'snapshot verified', len(saved['files']), flush=True)


if __name__ == '__main__':
    main()
