"""Extend the registered calculator comparison to two additional target models."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.key_groups import run as calculator

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/calculator-target-models-20261128'
MODELS = ('gemma', 'oss')
END = datetime(2026, 11, 28, 10, 32, tzinfo=timezone.utc)
CAP = 2.50


def register():
    previous = read(calculator.OUT / 'registration.json')
    public = calculator.OUT / 'public.json'
    core.save(OUT / 'public.json', read(public))
    harness = browser.verify_contract(calculator.PROJECT)
    if harness != previous['harness'] or core.public_input(calculator.PROJECT) != read(public):
        raise ValueError('Calculator inputs differ from the original comparison')
    sources = [Path(__file__), HERE / 'PROTOCOL.md', Path(calculator.__file__),
               Path(calculator.base.__file__), Path(browser.__file__), Path(core.__file__),
               calculator.OUT / 'registration.json', public]
    fingerprints = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    for name, digest in previous['sources'].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f'Changed calculator source {name}')
    f = OUT / 'registration.json'
    if not f.exists():
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance for calculator extension')
        core.save(f, dict(utc=now(), deadline=END.isoformat(), cap=CAP, balance=balance,
                          sources=fingerprints, targets=list(range(1, 21)), harness=harness,
                          models={t: calculator.action.settings('table', t, 'plan')['model'] for t in MODELS},
                          source_costs={k: v for k, v in previous['source_costs'].items() if k != 'astra'}))
    reg = read(f)
    if reg['sources'] != fingerprints:
        raise ValueError('Registered inputs changed')
    return reg


def main():
    with browser.lock(OUT / 'study.lock'):
        reg = register()
        arms = ('direct', 'human', 'gpt5-library', 'self-a', 'self-b')
        with patch.multiple(calculator, OUT=OUT, HERE=HERE, TAGS=MODELS, ARMS=arms, ASTRA={}, CAP=CAP), \
                patch.object(calculator.action, 'END', END):
            calculator.generate(reg)
            if not (HERE / 'result.json').exists():
                calculator.score(reg)


if __name__ == '__main__':
    main()
