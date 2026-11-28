"""Pair both original-author repairs with the sealed plans and the old GPT-5 results."""

from collections import Counter
from pathlib import Path

from studies.study_io import ROOT, read, sha

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
ORIGINAL = ROOT / "studies/webbench/table_interactions/result.json"
METHOD = "gpt5-library"


def reconstruct(path=RESULT):
    data = read(path)
    assert data["model"] == "openai/gpt-5" and data["original"] == sha(ORIGINAL)
    old = {group["tag"]: group for group in read(ORIGINAL)["cells"]}
    assert set(old) == set(data["generators"]) and len(old) == 5
    summaries = {}
    for rep, library in data["libraries"].items():
        rows = [v for v in data["rows"] if v["rep"] == rep]
        if library["status"] != "valid":
            assert not rows
            continue
        assert len(library["checks"]) == 4 and all(len(c) == 3 and all(c.values()) for c in library["checks"])
        assert len(rows) == 180
        grouped = {}
        for arm, tags in [("planned", old), ("fixed", map(str, range(4)))]:
            for tag in tags:
                group = [v for v in rows if v["tag"] == tag and v["arm"] == arm]
                assert sorted(v["task"] for v in group) == list(range(1, 21))
                assert all(type(v["passed"]) is bool for v in group)
                passed = {v["task"] for v in group if v["passed"]}
                bucket = dict(passed=sorted(passed), status=dict(Counter(v["status"] for v in group)))
                if arm == "planned":
                    original = {v["task"]: v["passed"] for v in old[tag]["rows"] if v["arm"] == METHOD}
                    assert all(v["original"] is original[v["task"]] for v in group)
                    earlier = {task for task, outcome in original.items() if outcome}
                    bucket.update(
                        original=sorted(earlier),
                        gained=sorted(passed - earlier),
                        lost=sorted(earlier - passed),
                    )
                grouped.setdefault(arm, {})[tag] = bucket
        summaries[rep] = grouped
    return summaries


if __name__ == "__main__":
    for rep, groups in reconstruct().items():
        print(rep, {t: len(v["passed"]) for t, v in groups["planned"].items()})
