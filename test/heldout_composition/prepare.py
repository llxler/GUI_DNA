"""Export development observations and calibrate references before paid calls."""
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from itertools import product
from pathlib import Path
import hashlib
import json

from test.interface_blind.core import ROOT, UPSTREAM, dump, digest, write_files
from .domain import PROJECTS, development, heldout, public_task
from .fixtures import cases
from .browser import evaluate
from .reference import files

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/heldout-composition-calibration'


def main():
    assert not (ROOT / 'artifacts/heldout-composition-build/review-manifest.json').exists(), 'Preparation is frozen once building starts'
    public = {project: [{**public_task(t), 'public_cases': cases(project, t['policy'], public=True)}
                        for t in development(project)] for project in PROJECTS}
    dump(HERE / 'public-development.json', public)
    provenance = {project: {'source': str((UPSTREAM / 'projects' / project / 'tasks.jsonl').relative_to(ROOT)),
                            'sha256': hashlib.sha256((UPSTREAM / 'projects' / project / 'tasks.jsonl').read_bytes()).hexdigest(),
                            'role': 'Application inspiration only; these policy tasks and assertions are newly authored, not official benchmark tasks.'}
                  for project in PROJECTS}
    jobs = [(project, bits) for project in PROJECTS for bits in product((0, 1), repeat=4)]

    def one(job):
        project, bits = job
        folder = OUT / project / ''.join(map(str, bits))
        write_files(folder, files(project, bits))
        target = folder / 'calibration.json'
        input_hash = digest({'files': files(project, bits), 'cases': cases(project, bits),
                             'runner': hashlib.sha256((HERE / 'browser.py').read_bytes()).hexdigest()})
        if target.exists():
            result = json.loads(target.read_text())
            assert result['calibration_input_sha256'] == input_hash, 'Archive the full obsolete calibration before changing inputs'
        else:
            result = evaluate(folder, project, cases(project, bits))
            result['calibration_input_sha256'] = input_hash
            dump(target, result)
        return {'project': project, 'policy': bits, 'result': result}

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(one, jobs))
    assert all(r['result']['all_passed'] for r in rows), 'Reference/oracle discrepancy; fix before calls'
    signatures = {project: len({digest(cases(project, bits)) for bits in product((0, 1), repeat=4)}) for project in PROJECTS}
    assert all(n == 16 for n in signatures.values()), 'Hidden observations do not distinguish every policy'
    negative = {}
    for project in PROJECTS:
        negative[project] = evaluate(OUT / project / '0000', project, cases(project, (1, 1, 1, 1)))
        assert not negative[project]['all_passed']
    summary = {'reference_rows': rows, 'wrong_policy_negatives': negative,
               'distinct_expected_hidden_signatures': signatures,
               'split': {p: {'development': len(development(p)), 'heldout': len(heldout(p))} for p in PROJECTS},
               'source_provenance': provenance, 'playwright_python': version('playwright'),
               'browser_versions': sorted({r['result']['browser_version'] for r in rows}),
               'public_json_sha256': hashlib.sha256((HERE / 'public-development.json').read_bytes()).hexdigest(),
               'scope': 'Reference calibration only, no paid calls or candidate scores. Identical action traces across configurations; each hidden policy has distinct observations. Synthetic diagnostic, not official Web-Bench or natural-language generalization.'}
    dump(OUT / 'complete.json', summary)
    dump(ROOT / 'test/results/heldout-composition-calibration.json', summary)
    print(json.dumps({key: value for key, value in summary.items() if key not in ('reference_rows', 'wrong_policy_negatives')}, indent=2))


if __name__ == '__main__':
    main()
