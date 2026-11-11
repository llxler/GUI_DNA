"""Set aside records whose attempt loop ended in a transport failure (HTTP 429 after the client's retries, dropped
connection, interrupted request), so that the stage runner regenerates them with the same seed.  Zero API itself.

    uv run python -m test.rerun_failed --stage artifacts/webbench-dna-6 --suite webbench [--apply]
    uv run python -m test.rerun_failed --stage artifacts/todomvc-dna-5 --suite todomvc [--apply]

Policy (applied uniformly to every model and method):
  * a record is affected when any attempt carries a `ProviderError` (the call never produced a model output);
  * affected records are moved to <stage>/discarded-transport/<n>/<model>/<arm>/<task...> together with their hidden grades;
  * in sequential Web-Bench methods (`free`, `free_lib`, `dna_inc`) every later task is moved too,
    because it starts from the previous page or plan; `free_clean`, fresh plans and TodoMVC samples are independent.
Without --apply the script only lists what would move.  After moving, run the stage runner again with the same
arguments: it skips existing records and regenerates the missing ones (new ledger reservations, same seed), then
grades.  Repeat until the listing is empty.  The discarded folders stay on disk for audit.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

SEQUENTIAL = {'webbench': {'free', 'free_lib', 'dna_inc'}, 'todomvc': set()}


def task_number(name):
    return int(name.split('-')[1]) if name.startswith('task-') else None


def affected(stage, suite):
    out = []
    for record in sorted(stage.glob('runs/*/*/**/record.json')):
        r = json.loads(record.read_text())
        errors = [a['compile_error'] for a in r.get('attempts', []) if (a.get('compile_error') or '').startswith('ProviderError')]
        if not errors:
            continue
        rel = record.parent.relative_to(stage / 'runs')
        model, arm = rel.parts[0], rel.parts[1]
        out.append((model, arm, record.parent, errors[-1][:80]))
    moves = []
    for model, arm, folder, error in out:
        moves.append((folder, error))
        if arm in SEQUENTIAL[suite]:
            k = task_number(folder.name)
            for sibling in sorted(folder.parent.iterdir()):
                n = task_number(sibling.name)
                if n is not None and n > k and (sibling / 'record.json').exists() and sibling not in [m[0] for m in moves]:
                    moves.append((sibling, f'after {folder.name} in sequential arm'))
    seen, unique = set(), []
    for folder, why in moves:
        if folder not in seen:
            seen.add(folder)
            unique.append((folder, why))
    return unique


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--suite', choices=['webbench', 'todomvc'], required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    stage = args.stage.resolve()
    moves = affected(stage, args.suite)
    if not moves:
        print('no record ended in a transport failure')
        return
    existing = sorted(int(p.name) for p in (stage / 'discarded-transport').glob('[0-9]*')) if (stage / 'discarded-transport').exists() else []
    batch = stage / 'discarded-transport' / str((existing[-1] + 1) if existing else 1)
    for folder, why in moves:
        rel = folder.relative_to(stage / 'runs')
        print(f'{"move" if args.apply else "would move"} {rel}  ({why})')
        if args.apply:
            target = batch / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(folder), str(target))
    if args.apply:
        (batch / 'README.md').write_text('Records set aside by test/rerun_failed.py because an attempt ended in a transport failure; '
                                         'the stage runner regenerated them with the same seed.\n' +
                                         '\n'.join(f'- {f.relative_to(stage / "runs")}: {w}' for f, w in moves) + '\n')
        print(f'{len(moves)} record folders moved to {batch}')
    models = sorted({str(f.relative_to(stage / 'runs').parts[0]).replace('__', '/') for f, _ in moves})
    arms = sorted({f.relative_to(stage / 'runs').parts[1] for f, _ in moves})
    print('re-run with: --models', ' '.join(models), '--arms', ' '.join(arms))


if __name__ == '__main__':
    main()
