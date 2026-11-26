"""Resume the registered run after a child evaluator was terminated during a proposed edit."""
import hashlib
import json
import os
import subprocess
from threading import Lock
from unittest.mock import patch

from studies.browser_worker import reentrant_slots
from studies.public_library_transfer import browser, core
from studies.study_io import now, sha
from . import run, todo


def main():
    run.register()
    path=run.OUT/'public-worker-resume.json'
    if not path.exists():
        core.save(path,dict(utc=now(),registration=sha(run.REG),worker=sha(__file__),
                            affected='OS terminated a Node child while evaluating a proposed TodoMVC edit',
                            handling='Serialize public probes, bound the Node heap, and reject child failures at the same public gate. Reuse settled responses.'))
    original=todo.features
    lock=Lock()
    def features(functions,enabled,spec):
        with lock:
            try:
                return original(functions,enabled,spec)
            except subprocess.CalledProcessError as exc:
                key=hashlib.sha256(json.dumps([functions,enabled],sort_keys=True).encode()).hexdigest()
                core.save(run.OUT/'public-worker-errors'/(key+'.json'),dict(input_sha256=key,returncode=exc.returncode))
                raise ValueError('Public interaction probe could not execute the proposed code') from None
    with browser.lock(run.OUT/'run.lock'), patch.object(browser,'browser_slot',reentrant_slots(browser.browser_slot)), patch.object(todo,'features',features):
        with patch.dict(os.environ,{'NODE_OPTIONS':'--max-old-space-size=192'}):
            run.generate()
        run.score()


if __name__=='__main__':
    main()
