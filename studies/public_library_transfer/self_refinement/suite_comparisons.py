"""Pair deterministic deployment of archived libraries with format-matched direct code."""

from collections import defaultdict
from pathlib import Path

from studies.study_io import ROOT, dump, read, sha

HERE = Path(__file__).resolve().parent
TODO = HERE / "todomvc/source_binding/result.json"
DUO = HERE / "duo_composition/result.json"
DIRECT = HERE / "duo_composition/declaration-result.json"
SOURCES = (TODO, DUO, DIRECT, HERE / "duo_composition/direct-result.json", HERE / "duo_composition/single-result.json")
OUTPUT = ROOT / "studies/results/library-domain-replay-20261124.json"


def comparison(arms):
    targets = sorted(next(iter(arms.values())))
    assert all(set(values) == set(targets) for values in arms.values())
    common = [t for t in targets if all(values[t] is not None for values in arms.values())]
    return {"targets": common, "n": len(common), "passed": {a: sum(v[t] for t in common) for a, v in arms.items()},
            "bound_only": [t for t in common if arms["bound"][t] and not arms["direct"][t]],
            "direct_only": [t for t in common if arms["direct"][t] and not arms["bound"][t]]}


def evidence():
    todo = defaultdict(lambda: defaultdict(dict))
    for row in read(TODO)["rows"]:
        todo[row["model"]][row["arm"]][row["task"]] = row["passed"]
    duo = read(DUO)["rows"]
    adjusted = read(DIRECT)["rows"]
    assert set(todo) == set(duo) == set(adjusted)
    models = {}
    for model in todo:
        # Panel B shares a direct column only when each individual verdict agrees.
        assert todo[model]["direct"] == todo[model]["strict_direct"]
        assert todo[model]["bound"] == todo[model]["fixed"]
        tasks = duo[model]
        arms = {key: {t: r[old]["passed"] for t, r in tasks.items()} for key, old in
                (("bound", "matched"), ("fixed", "fixed"), ("strict_self", "self"), ("strict_direct", "direct"))}
        arms["direct"] = {t: r["after"] for t, r in adjusted[model].items()}
        models[model] = {"todomvc": comparison(todo[model]), "duo": comparison(arms)}
    return {"kind": "Offline deterministic deployment of previously model-written source",
            "direct": {"todomvc": "same source extraction as construction", "duo": "source extraction and default-export declaration repair"},
            "models": models, "sources_sha256": {str(p.relative_to(ROOT)): sha(p) for p in SOURCES}}


def verify_or_publish(write=False):
    result = evidence()
    if write:
        dump(OUTPUT, result)
    else:
        assert result == read(OUTPUT)


if __name__ == "__main__":
    verify_or_publish()
