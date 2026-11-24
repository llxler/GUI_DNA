"""Cache existing official reports for identical sealed controllers on identical tasks."""
import fcntl
import os

from studies.public_library_transfer.backbone_suites.run import inputs
from studies.study_io import read,sha
from .run import OUT,base,save


def reuse():
    source_seal=read(base.OUT/'seal.json')
    matched_seal=read(OUT/'seal.json')
    assert sha(base.OUT/'seal.json')==read(OUT/'registration.json')['contract']['files'][str((base.OUT/'seal.json').relative_to(base.ROOT))]
    orig={(r['task'],r['files_sha256']):r for r in source_seal['rows'] if r['status']=='valid'}
    tasks,_=inputs()
    count=0
    for row in matched_seal['rows']:
        if row['status']!='valid' or (row['task'],row['files_sha256']) not in orig:
            continue
        task,digest=row['task'],row['files_sha256']
        old=orig[task,digest]
        before=base.OUT/old['group']/old['arm']/task/'files.json'
        after=OUT/'candidates'/row['group']/row['arm']/task/'files.json'
        assert sha(before)==sha(after)==digest and before.read_bytes()==after.read_bytes()
        src=base.OUT/'scores'/task/digest
        dest=OUT/'scores'/task/digest
        if (dest/'verdict.json').exists() or not (src/'verdict.json').exists():
            continue
        proof=base.binding.official(src,tasks[task],row)
        dest.mkdir(parents=True,exist_ok=True)
        with (dest/'.lock').open('a') as lock:
            try:
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            if (dest/'verdict.json').exists() or (dest/'playwright.json').exists():
                continue
            os.link(src/'playwright.json',dest/'playwright.json')
            assert sha(dest/'playwright.json')==proof['report_sha256']
            save(dest/'reused.json',{'task':task,'files_sha256':digest,'origin_stage':base.OUT.name,
                'origin_seal_sha256':sha(base.OUT/'seal.json'),'origin_verdict_sha256':sha(src/'verdict.json'),
                'report_sha256':proof['report_sha256']})
            os.link(src/'verdict.json',dest/'verdict.json')
            count+=1
    print('verified matching official reports reused',count)


if __name__=='__main__':
    reuse()
