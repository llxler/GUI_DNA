"""Use a verified lower provider price ceiling before any native HTML judgment."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import time
from unittest.mock import patch

import httpx
from studies.public_library_transfer import browser, core
from studies.study_io import now, read, sha
from . import run


def judge():
    if run.RESULT.exists():
        return
    dest = run.OUT/'price-registration.json'
    if not dest.exists():
        assert not (run.OUT/'judge-registration.json').exists()
        model = run.first.api.ALTERNATE
        try:
            answer = httpx.get('https://openrouter.ai/api/v1/models/'+model+'/endpoints', timeout=20)
            answer.raise_for_status()
            allowed = [e for e in answer.json()['data']['endpoints']
                       if e.get('status') == 0 and 0 < e['context_length'] <= 262144
                       and Decimal(e['pricing']['prompt']) <= Decimal('0.00000015')
                       and Decimal(e['pricing']['completion']) <= Decimal('0.00000060')
                       and not any(Decimal(e['pricing'].get(k) or 0) for k in ('request','image'))]
        except (httpx.HTTPError, ValueError, KeyError):
            allowed = []
        core.save(dest, dict(utc=now(), model=model, candidates=sha(run.PAGES), source=sha(Path(__file__)),
                            protocol=sha(run.HERE/'PRICE.md'), endpoints=allowed))
    registration = read(dest)
    assert registration['candidates'] == sha(run.PAGES) and registration['source'] == sha(Path(__file__))
    price = (.15,.60) if registration['endpoints'] else run.first.api.PRICES[run.first.api.ALTERNATE]
    with patch.dict(run.first.api.PRICES,{run.first.api.ALTERNATE:price}), patch.object(run,'ThreadPoolExecutor',lambda **_: ThreadPoolExecutor(max_workers=1)):
        run.score()


if __name__ == '__main__':
    with browser.lock(run.OUT/'run.lock'):
        while not (run.HERE.parent/'secondary-completion.json').exists():
            if datetime.now(timezone.utc) >= run.first.run.END:
                raise TimeoutError('Independent judge did not close before the round deadline')
            time.sleep(8)
        judge()
