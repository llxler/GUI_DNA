"""Select a previously delivered operation that really updates logical selection."""
from pathlib import Path
import json
import subprocess

HERE=Path(__file__).resolve().parent


def logical_winner(name,functions):
    best=None
    for fn in functions:
        try:
            check=subprocess.run(['node',str(HERE/'state.cjs')],input=json.dumps(dict(name=name,fn=fn)),text=True,
                                 capture_output=True,timeout=7)
            value=int(check.stdout) if not check.returncode else -1
        except (subprocess.TimeoutExpired,ValueError):value=-1
        if best is None or value>best[0]:best=(value,fn)
    return best[1]
