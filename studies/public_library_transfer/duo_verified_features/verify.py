"""Audit local registered inputs and original Jest reports for the public Duo result."""

from collections import Counter, defaultdict
from pathlib import Path

from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha
from . import report

ART = ROOT / "artifacts"
REGISTRATIONS = {
    report.FIRST: "duo-verified-features",
    report.CONTRACT: "duo-feature-contract",
    report.ROUTES: "duo-feature-routes",
    report.FINAL: "duo-field-bindings",
    report.ROUTER: "duo-router-compatibility",
    report.ENTRIES: "duo-official-entries",
    **{receipt: name for name, receipt in report.STAGES.values()},
}


def verify():
    registrations = {}
    for receipt, folder in REGISTRATIONS.items():
        path = ART / (folder + "-20261128") / "registration.json"
        assert sha(path) == read(receipt)["registration"]
        reg = read(path)
        sources = next(reg[k] for k in ("sources", "inputs", "source") if k in reg)
        for name, fingerprint in sources.items():
            assert sha(ROOT / name) == fingerprint, name
        registrations[folder] = dict(registration=sha(path), checked_files=len(sources))

    files = [*ART.glob("backbone-suites-20261124/*/scores/*/direct/jest.json")]
    for folder in (
        "duo-react-callbacks-20261126",
        "duo-field-bindings-20261128",
        "duo-form-config-20261128",
        "duo-unseen-pairs-20261128",
        "duo-router-compatibility-20261128",
        "duo-official-entries-20261128",
    ):
        files.extend((ART / folder).glob("scores/*/*/jest.json"))
    by_hash = {sha(f): f for f in files}

    def check(row):
        if not row.get("report_sha256"):
            assert row["status"] == "invalid" and row["passed"] is False
            return "invalid delivery"
        (suite,) = read(by_hash[row["report_sha256"]])["testResults"]
        assert Path(suite["name"]).name == row["task"] + ".test.js"
        cases = [a["status"] for a in suite["assertionResults"]]
        assert row["passed"] is (cases == ["passed"] * 4)
        if not cases:
            assert suite["status"] == "failed" and suite["message"]
            return "suite load failure"
        assert len(cases) == 4
        return "executed all four"

    comparisons = {}
    matrix = read(ROOT / "studies/results/paper-performance-matrix.json")
    for model, record in matrix.items():
        if "duo_feature_bindings" not in record:
            continue
        group = record["duo_feature_bindings"]
        tallies = comparisons[model] = {}
        for arm, name in group["implementation_sources"].items():
            rows = read(ROOT / name)["models"][model]
            if isinstance(rows, dict):
                rows = rows["rows"]
            checked = report.observations(rows, arm, group["targets"])
            tallies[arm] = dict(Counter(check(r) for r in checked.values()))

    independent = {}
    for phase, rows in read(report.ENTRIES)["phases"].items():
        independent[phase] = dict(Counter(check(row) for row in rows))
        assert independent[phase] == {"executed all four": 50}

    deliveries = {}
    for stage, (folder, receipt) in report.STAGES.items():
        groups = defaultdict(Counter)
        for file in (ART / (folder + "-20261128")).rglob("response.json"):
            response = read(file)
            request = read(file.with_name("request.json"))
            assert request["body"]["model"] == response["model"], file
            groups[response["model"]][response["provider"]] += 1
        totals = read(receipt)["cost"]
        assert (
            sum(sum(g.values()) for g in groups.values())
            == totals["calls"] - totals["unsettled_calls"]
        )
        deliveries[stage] = {k: dict(v) for k, v in groups.items()}
    return dict(
        registrations=registrations,
        original_pairs=comparisons,
        independent_pairs=independent,
        delivered_responses_by_model_and_provider=deliveries,
    )


if __name__ == "__main__":
    result = verify()
    core.save(report.HERE / "verification.json", result)
    print(result["independent_pairs"])
