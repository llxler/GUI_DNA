"""Pair the local calculator and TodoMVC workflows using their original task receipts."""
from pathlib import Path

from studies.study_io import read

HERE = Path(__file__).resolve().parent
CALCULATOR = HERE / "local_domain/typed_keys/result.json"
TODOMVC = HERE / "todomvc/event_modules/result.json"
SOURCES = (CALCULATOR, TODOMVC)
DIAGNOSTICS = (HERE / "form_registry/result.json", HERE / "target_selection/result.json",
               HERE / "todomvc/event_modules/feedback/result.json")


def column(records, targets, **filters):
    selected = [r for r in records if all(r[key] == value for key, value in filters.items())]
    assert len(selected) == len(targets) and {r["task"] for r in selected} == set(targets)
    values = {}
    for row in selected:
        if row["status"] == "valid":
            assert type(row["passed"]) is bool and len(row["report_sha256"]) == 64
            values[row["task"]] = row["passed"]
        else:
            # A returned but unusable page fails this workflow; absence is never scored as failure.
            assert row["status"] == "invalid" and row["passed"] in (False, None) and not row.get("report_sha256")
            values[row["task"]] = False
    return values


def rows():
    calc, todo = (read(path) for path in SOURCES)
    assert calc["model"] == todo["model"] == "Qwen/Qwen2.5-0.5B-Instruct"
    assert calc["revision"] == todo["revision"]
    groups = []
    for project, data, records, targets, group_field, endpoints in (
        ("Calculator", calc, calc["target_rows"], tuple(range(1, 21)), "rep", ("fixed-A", "fixed-B")),
        ("TodoMVC", todo, todo["rows"], tuple(f"todo-{i:02}" for i in range(1, 9)), "group", ("fixed_on", "fixed_off")),
    ):
        columns = {"direct": column(records, targets, arm="direct")}
        if project == "Calculator":
            assert tuple(data["targets"]) == targets
            columns["rules"] = column(records, targets, arm="linker", rep="A")
            assert columns["rules"] == column(records, targets, arm="linker", rep="B")
            assert {r["task"]: r["report_sha256"] for r in records if r["arm"] == "linker" and r["rep"] == "A"} == {
                r["task"]: r["report_sha256"] for r in records if r["arm"] == "linker" and r["rep"] == "B"}
        for group in ("A", "B"):
            for label, arm in zip(("plan", "first", "second"), ("self", *endpoints), strict=True):
                observed = column(records, targets, arm=arm, **{group_field: group})
                passed = [t for t in targets if observed[t]]
                official_ids = (data["summary"]["builds"][group]["passed"][arm] if project == "Calculator"
                                else data["paired"][group]["passed"][arm])
                assert passed == official_ids
                columns[f"{group}_{label}"] = observed
        groups.append({"project": project, "targets": targets, "n": len(targets),
                       "passed": {key: sum(value.values()) for key, value in columns.items()}})
    return groups
