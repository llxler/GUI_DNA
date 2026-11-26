"""Finish sealed attempts when Chromium rejects the import used to observe the public API.

A thrown module initialization error is a failed public build. Replay received model
bodies only. This finalizer cannot transmit a new request or change a controller.
"""
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import Error as BrowserError
from studies.public_library_transfer import core
from studies.study_io import read,sha
from . import focused


def main():
    reg=focused.register()
    original_observe=focused.observe
    def observe(page):
        try:
            return original_observe(page)
        except BrowserError as error:
            reason=str(error).replace('\n',' ')
            import re
            reason=re.sub(r'http://127\.0\.0\.1:\d+/', '/',reason)
            raise ValueError('Public module import rejected: '+reason[:500]) from None
    def local_request(ledger,case,folder,messages,stage,limit):
        for reply in sorted(folder.glob('transmission-*/response.json')):
            req=read(reply.with_name('request.json'))['body']
            assert req['messages']==messages and req['max_tokens']==limit
            assert sha(reply)==read(reply.with_name('settled.json'))['response_sha256']
            first=read(reply)['choices'][0]
            if first['finish_reason']!='error':return first['message'].get('content') or ''
        raise RuntimeError('No settled prior model reply: '+str(folder))
    with patch.object(focused,'observe',observe),patch.object(focused.parent.compact.base,'request',local_request):
        focused.main('generate')
    core.save(focused.OUT/'observation-finalizer.json',dict(registration=sha(focused.OUT/'registration.json'),
        source=sha(Path(__file__)),seals={t:sha(focused.OUT/t/'seal.json') for t in reg['models']},api_calls=0))
    focused.main('score')


if __name__=='__main__':main()
