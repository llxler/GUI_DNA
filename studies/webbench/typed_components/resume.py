"""Resume sealed SVG source deliveries with the registered observer's actual function name."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from studies.study_io import ROOT,read,sha,now
from studies.public_library_transfer import core
from . import run
from .unavailable import run as missing


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('cohort',choices=('red','absent'))
    parser.add_argument('tag',nargs='?')
    args=parser.parse_args()
    cohort=run if args.cohort=='red' else missing
    data=cohort.register()
    cases=[c for c in data['cases'] if c['project']=='svg-chart']
    record=cohort.OUT/'observer-entrypoint.json'
    files=[Path(__file__),Path(run.charts.observe.__file__),Path(run.__file__),cohort.OUT/'registration.json']
    hashes={str(f.relative_to(ROOT)):sha(f) for f in files}
    if not record.exists():
        core.save(record,dict(utc=now(),sources=hashes,change='Call observe(out,page,files), the registered public SVG observer.'))
    assert read(record)['sources']==hashes
    if args.tag:
        case=next(c for c in cases if c['builder']==args.tag)
        with patch.object(run.charts.observe,'public',run.charts.observe.observe,create=True),patch.multiple(run,OUT=cohort.OUT,CAP=cohort.CAP):
            run.generate(case)
    else:
        def child(c):
            subprocess.run([sys.executable,'-m','studies.webbench.typed_components.resume',args.cohort,c['builder']],check=True)
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(child,cases))


if __name__=='__main__':main()
