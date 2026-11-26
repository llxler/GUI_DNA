"""Resume an interrupted preparation using its sealed public feedback and requests."""
import json
from pathlib import Path
from unittest.mock import patch

from studies.public_library_transfer import browser, core
from studies.study_io import now, read, sha
from . import run as reducers
from .typed_events.run import observe as reserved_probe

if __name__ == '__main__':
    prior = reducers.prior
    original = prior.BASE.request
    def request(ledger, case, dest, messages, stage, limit):
        f = dest / 'transmission-1/request.json'
        if f.exists():
            saved = read(f)['body']['messages']
            assert messages[:2] == saved[:2]
            messages = saved
        return original(ledger, case, dest, messages, stage, limit)

    def observe(candidate):
        from studies.study_io import ROOT
        page = ROOT / candidate['page']
        if page.parent.name == '0':
            following = page.parent.parent / '1/call/transmission-1/request.json'
            if following.exists():
                msg = read(following)['body']['messages'][-1]['content']
                report = msg.split('Public interaction report: ', 1)[-1]
                try:
                    observation = json.loads(report)
                    if isinstance(observation, dict) and observation.get('browser'):
                        return observation['browser']
                except ValueError:
                    pass
        return reserved_probe(candidate)
    with browser.lock(reducers.OUT / 'run.lock'):
        receipt = reducers.OUT / 'capacity-recovery.json'
        if not receipt.exists():
            core.save(receipt, dict(utc=now(), registration=sha(reducers.OUT/'registration.json'),
                                  source=sha(Path(__file__)), reason='Process exited with signal 15 before sealing. Retain existing responses, public feedback and outstanding reservations; acquire the browser before timing.'))
        with patch.object(prior.BASE, 'request', request), patch.object(prior, 'observe', observe):
            reducers.generate()
            reducers.score()
