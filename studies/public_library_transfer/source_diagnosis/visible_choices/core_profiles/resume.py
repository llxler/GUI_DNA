"""Serialize writes to the one fixed page shared by all eight target workers."""
from unittest.mock import patch
from studies.public_library_transfer import browser,core
from studies.browser_worker import reentrant_slots
from studies.study_io import now,sha
from . import run


def main():
    write=core.save
    def save(path,value):
        if path.parent.name=='fixed-core' and path.name=='files.json':
            with browser.lock(path.parent/'write.lock'):
                return write(path,value)
        return write(path,value)
    with browser.lock(run.OUT/'run.lock'),patch.object(browser,'browser_slot',reentrant_slots(browser.browser_slot)):
        reg=run.register()
        write(run.OUT/'shared-file-recovery.json',dict(registration=sha(run.OUT/'registration.json'),worker=sha(__file__),
              change='Serialize concurrent identical writes to the single fixed teaching example; keep page bytes, model requests and scoring unchanged.'))
        with patch.object(core,'save',save):run.generate()
        run.score(reg)


if __name__=='__main__':main()
