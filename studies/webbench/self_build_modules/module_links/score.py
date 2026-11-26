"""Rebuild the final first-admitted view after the dependency-only recovery stage."""
from unittest.mock import patch
from ..observed_options import run as previous, score as report
from . import run

if __name__=='__main__':
    with patch.multiple(report,run=run,entry=previous,RESULT=run.HERE/'result.json',PRIOR_LABEL='observed options',
                        LABEL='module links',HASH_FIELD='options_result_sha256',METADATA=('version','prior_package_sha256')):
        report.main()
