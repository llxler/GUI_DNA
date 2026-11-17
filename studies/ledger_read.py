"""Read a stage ledger without touching it.

    uv run python -m test.ledger_read artifacts/<stage>/budget.sqlite3 [...]

`gui_dna.budget.Ledger(path, cap, stop)` writes min(old, new) caps back on open ("a restarted process may tighten, never
raise, a persisted limit").  Opening the ledger of a RUNNING stage with small caps just to look at it therefore stops
that stage (this happened on 2026-11-11).  Use this module for looking; it opens the database read-only.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def calls(path):
    """Rows of the calls table as dicts (purpose, model, status, reserved, actual in micro-dollars)."""
    path = Path(path).resolve()
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=30)
    try:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute('SELECT id, purpose, model, status, reserved, actual, created FROM calls')]
    finally:
        db.close()


def totals(path):
    rows = calls(path)
    db = sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True, timeout=30)
    try:
        cap, stop, halted = db.execute('SELECT cap, stop, halted FROM policy WHERE id=1').fetchone()
    finally:
        db.close()
    return {'calls': len(rows), 'settled_usd': sum(r['actual'] or 0 for r in rows) / 1e6,
            'exposure_usd': sum(r['actual'] if r['actual'] is not None else r['reserved'] for r in rows) / 1e6,
            'unsettled_calls': sum(r['actual'] is None for r in rows), 'cap_usd': cap / 1e6, 'stop_usd': stop / 1e6, 'halted': halted}


class ReadOnlyLedger:
    """Reporting adapter: never creates a database or changes its policy."""
    def __init__(self, path):
        self.path = Path(path)

    def summary(self):
        rows = calls(self.path) if self.path.exists() else []
        return {'calls': rows, 'actual_usd': sum(r['actual'] or 0 for r in rows) / 1e6,
                'unsettled_calls': sum(r['actual'] is None for r in rows)}


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        print(arg, totals(arg))
