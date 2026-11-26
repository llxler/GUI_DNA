"""Pair the repaired Flash pilot and the independent repeat with their original targets."""
from pathlib import Path

from studies.public_library_transfer.self_refinement.prospective_panel import paired_rows
from studies.study_io import ROOT, read, sha

HERE = Path(__file__).resolve().parent
PILOT = HERE / "result.json"
REPAIR = HERE / "contract_repair/result.json"
CONFIRMATION = HERE / "confirmation/result.json"
FILE_REPAIR = HERE / "file_repair/result.json"
COMPLETION = HERE / "transport_completion/result.json"
SOURCES = (PILOT, REPAIR, CONFIRMATION, FILE_REPAIR, COMPLETION)
MODEL = "deepseek/deepseek-v4-flash"
FINAL_PROTOCOL = "File-level checks"


def _row(label, first, second, *, admitted_only=False):
    groups, direct = {}, None
    for rep, branch in (("a", first), ("b", second)):
        if admitted_only and branch["build"]["status"] != "valid":
            continue
        trials = branch["rows"]
        assert len(trials) == 20 and {r["task"] for r in trials} == set(range(1, 21))
        columns = {arm: {r["task"]: r[arm]["passed"] for r in trials}
                   for arm in ("direct", "self", "fixed", "human", "gpt5-library", "original-self")}
        for arm, n in (("direct", 4), ("human", 17), ("gpt5-library", 13), ("original-self", 0)):
            assert sum(columns[arm].values()) == n
        if direct is None:
            direct = columns["direct"]
        assert columns["direct"] == direct
        groups[rep] = columns["self"], columns["fixed"]
    return paired_rows("Question form", "DeepSeek V4 Flash", label, direct or {}, groups, admitted_only=admitted_only)


def rows():
    pilot, repair, fresh, original, final = (read(p) for p in SOURCES)
    assert {p["model"] for p in (pilot, repair, fresh, original, final)} == {MODEL}
    assert repair["primary_result_sha256"] == sha(PILOT)
    assert final["file_repair_result_sha256"] == sha(FILE_REPAIR)
    assert final["original_confirmation"] == original["confirmation"]
    return (_row("Whole package", fresh["branches"]["fresh-a"], fresh["branches"]["fresh-b"], admitted_only=True)
            + _row(FINAL_PROTOCOL, final["branches"]["file-a"], final["branches"]["file-b"], admitted_only=True))


def panel_a_self(original_arms):
    """Report the first registered build. Panel D reports both independent builds."""
    final = read(COMPLETION)
    assert final["model"] == MODEL and final["project"] == "form"
    library = "file-a"
    rows = final["branches"][library]["rows"]
    assert [r["task"] for r in rows] == final["tasks"]
    for arm in ("direct", "human", "gpt5-library", "self"):
        source_arm = "original-self" if arm == "self" else arm
        assert {r["task"]: r[source_arm]["passed"] for r in rows} == original_arms[arm]
    passes = [r["self"]["passed"] for r in rows]
    assert all(type(result) is bool for result in passes)
    return {"protocol": FINAL_PROTOCOL, "library": library, "targets": final["tasks"], "passed": {"self": sum(passes)},
            "source": str(COMPLETION.relative_to(ROOT)), "source_sha256": sha(COMPLETION)}
