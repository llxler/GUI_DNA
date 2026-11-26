"""Use the original scoring contract on the separately sealed source-delivery study."""
from unittest.mock import patch
from .. import run as base, score
from . import run

if __name__=='__main__':
    with patch.object(base,'OUT',run.OUT),patch.object(score,'RESULT',run.HERE/'result.json'):
        score.main()
