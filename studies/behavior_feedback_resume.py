"""Resume unchanged repairs after normalizing tuple/list JSON representation.

The frozen runner passes TASKS as a Python tuple to freeze(); its saved JSON is
necessarily a list. The generic freeze function compares Python objects and
therefore rejects a second invocation despite identical serialized inputs. This
adapter preserves every source hash, config value and serialized protocol value.
It does not replace the historical manifest or change messages, tasks or budget.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from test import behavior_feedback as runner
from test.interface_blind.core import dump


def canonical_protocol(protocol):
    return json.loads(json.dumps(protocol))


def main():
    manifest = runner.OUT / 'review-manifest.json'
    original = json.loads(manifest.read_text())
    for name, expected in original['sha256'].items():
        assert hashlib.sha256((runner.ROOT / name).read_bytes()).hexdigest() == expected, name
    receipt = runner.OUT / 'resume-serialization.json'
    value = {'change': 'Normalize protocol to its existing JSON representation before equality comparison. Tuple and list serialize identically; model inputs and original source hashes unchanged.',
             'adapter': str(Path(__file__).relative_to(runner.ROOT)),
             'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'original_manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()}
    if receipt.exists():
        assert json.loads(receipt.read_text()) == value, 'Recovery adapter changed'
    else:
        dump(receipt, value)
    original_freeze = runner.freeze

    def checked_freeze(out, config, files, protocol):
        normalized = canonical_protocol(protocol)
        assert normalized == original['protocol'], 'Serialized protocol changed'
        assert config == original['config'], 'Model configuration changed'
        return original_freeze(out, config, files, normalized)

    runner.freeze = checked_freeze
    try:
        runner.main()
    finally:
        runner.freeze = original_freeze


if __name__ == '__main__':
    main()
