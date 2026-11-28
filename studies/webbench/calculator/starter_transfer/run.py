"""Apply the existing starter-module fallback on a documented public build failure."""
from pathlib import Path
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.starter_modules import run as modules
from studies.webbench.calculator.target_models import run as trial

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/calculator-starter-transfer-20261128'
CAP = .85


def register():
    sources = [Path(__file__), HERE / 'PROTOCOL.md', Path(modules.__file__), modules.HERE / 'probe.js',
               modules.HERE / 'PROTOCOL.md', trial.OUT / 'registration.json', trial.OUT / 'public.json']
    builds = {t: trial.OUT / t / 'build/a/library.json' for t in trial.MODELS}
    sums = {str(p.relative_to(ROOT)): sha(p) for p in [*sources, *builds.values()]}
    failed = [t for t, p in builds.items() if read(p)['status'] == 'build_failed']
    if failed != ['gemma'] or sha(trial.OUT / 'public.json') != sha(modules.original.OUT / 'public.json'):
        raise ValueError('Unexpected public admission or starter')
    f = OUT / 'registration.json'
    if not f.exists():
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(f, dict(utc=now(), deadline=trial.END.isoformat(), cap=CAP, balance=balance,
                          eligible=failed, sources=sums, targets=list(range(1, 21))))
    if read(f)['sources'] != sums:
        raise ValueError('Registered build changed')
    return read(f)


def main():
    with browser.lock(OUT / 'study.lock'):
        reg = register()
        with patch.multiple(modules, OUT=OUT, CAP=CAP, TAG=reg['eligible'][0], register=lambda: reg), \
                patch.object(modules.api, 'END', trial.END):
            modules.main('generate')
            if not (HERE / 'result.json').exists():
                with patch.object(modules, 'HERE', HERE):
                    modules.main('score')


if __name__ == '__main__':
    main()
