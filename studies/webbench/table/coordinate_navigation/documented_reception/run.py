"""Replay the two settled replies with the existing outer-fence decoder, without an API call."""
from pathlib import Path
from unittest.mock import patch

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.table.coordinate_navigation import run as study

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/table-coordinate-reception-20261128'


def main():
    source = study.OUT
    oldreg = read(source/'registration.json')
    oldseal = read(source/'seal.json')
    receipts = {}
    paths = [Path(__file__), HERE/'PROTOCOL.md', Path(study.__file__), source/'registration.json', source/'seal.json']
    for rep in ('1','2'):
        assert oldseal['trials'][rep]['status']=='invalid'
        settled, = (source/rep/'call').glob('*/settled.json')
        req, reply = settled.with_name('request.json'), settled.with_name('response.json')
        assert sha(reply)==read(settled)['response_sha256']
        receipts[rep] = read(req)['body'], read(reply)['choices'][0]['message']['content']
        paths += [req,reply,settled]
    sums = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    path = OUT/'registration.json'
    if not path.exists():
        core.save(path,dict(utc=now(),sources=sums,seeds=oldreg['seeds'],new=oldreg['new'],paid_calls=0))
    assert read(path)['sources']==sums
    receive = study.receive
    base = study.previous.mode.prior.base
    def replay(ledger, case, folder, messages, phase, max_tokens):
        original, raw = receipts[folder.parent.name]
        current = base.template(case[0],case[1],phase)
        assert original == dict(current,messages=messages,max_tokens=max_tokens)
        return raw
    with patch.multiple(study, OUT=OUT, HERE=HERE, receive=lambda raw: receive(base.uncode(raw))), patch.object(base, 'request', replay):
        study.generate(read(path))
        study.score()


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        main()
