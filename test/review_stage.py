"""Freeze review-stage generation inputs without changing the original experiments."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def provider_for(config, ledger, extra_ledgers=()):
    """Replay settled calls across stages while reserving new calls only in the new ledger."""
    from test.ledger_read import calls
    from test.provider_ext import ReasoningAwareOpenRouter

    older = [c for path in extra_ledgers for c in calls(path)]

    class ReplayLedger:
        def __getattr__(self, name):
            return getattr(ledger, name)

        def summary(self):
            current = ledger.summary()
            return {**current, 'calls': current['calls'] + older}

    return ReasoningAwareOpenRouter(config, ReplayLedger())


def freeze(out, config, files, protocol):
    paths = [Path(__file__).relative_to(ROOT).as_posix(), *files]
    value = {'config': config, 'protocol': protocol, 'sha256': {
        p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}}
    target = Path(out) / 'review-manifest.json'
    if target.exists():
        if json.loads(target.read_text()) != value:
            raise ValueError(f'{target}: generation inputs changed; use a new stage')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
