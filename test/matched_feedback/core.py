"""Public requirements and feedback only; no held-out test source enters prompts."""
from pathlib import Path
import json

from test.history_replay.run import ROOT, read, dump, sha, digest, now
from test.webbench_expand.core import PROJECTS, BUILDERS, UPSTREAM, ENVIRONMENT, requirements
from test.webbench_expand.generate import messages_for as original_messages, output_files
from test.interface_blind.core import validate_files, write_files, slug

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/matched-feedback-20261116'
BUILD = ROOT / 'artifacts/webbench-expand-build/libraries'
PUBLIC = ('init', 'task-4', 'task-8', 'task-12', 'task-16')
MODELS = ('openai/gpt-oss-120b',)
SEEDS = (2026111601, 2026111602)


def package_path(project, builder):
    return BUILD / project / slug(builder) / 'package.json'


def messages(project, method, package):
    result = original_messages(project, 'task-20', method, package)
    tests = {name: (UPSTREAM / 'projects' / project / 'test' / (name + '.spec.js')).read_text() for name in PUBLIC}
    result[1]['content'] += ('\nPublic behavior checks available equally to every method:\n' +
        json.dumps(tests, ensure_ascii=False) + '\nThe same complete page must satisfy all cumulative requirements. '
        'Each response is checked on these five files. You receive at most two repairs with the same public feedback. '
        'Other tests are withheld. Public pass does not establish complete behavior. '
        'Do not detect the test runner or suppress errors; implement the requested application.')
    return result


def configuration():
    return {'models': list(MODELS), 'temperature': .6, 'max_tokens': 20000, 'max_repairs': 2,
        'budget_usd': 4., 'stop_new_requests_usd': 3.7,
        'price_caps_per_million': {'prompt': .2, 'completion': .7},
        'model_price_caps': {MODELS[0]: {'prompt': .2, 'completion': .7}},
        'reasoning_effort': {MODELS[0]: 'low'}, 'provider_order': {MODELS[0]: ['Near AI']}}


def jobs():
    result = []
    for project in PROJECTS:
        for model in MODELS:
            for seed in SEEDS:
                options = [(None, 'free')]+[(b, m) for b in BUILDERS for m in ('plan', 'free_lib')]
                for builder, method in options:
                    folder = OUT / 'runs' / project / (slug(builder) if builder else 'no_library') / slug(model) / str(seed) / method
                    result.append({'project': project, 'builder': builder, 'model': model, 'seed': seed,
                        'method': method, 'folder': str(folder.relative_to(ROOT))})
    return result


def verify():
    snapshot = read(OUT / 'snapshot.json')
    for path, expected in snapshot['sha256'].items():
        assert sha(ROOT / path) == expected, path
    return snapshot
