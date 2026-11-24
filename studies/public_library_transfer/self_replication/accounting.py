"""Combine distinct read-only trial ledgers with the preceding same-day matrix."""

import argparse
from decimal import Decimal

from studies import ledger_read
from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha

RESULTS = ROOT / "studies/results"
EARLIER = RESULTS / "backbone-overview-20261124.json"
STRONG = ROOT / "studies/public_library_transfer/strong_builder/result.json"
DEST = RESULTS / "self-construction-accounting-20261124.json"
FIELDS = ("calls", "unsettled_calls", "settled_usd", "exposure_usd")


def combine(records):
    return {
        k: (int if k in ("calls", "unsettled_calls") else float)(
            sum(Decimal(str(v[k])) for v in records)
        )
        for k in FIELDS
    }


def validate(data):
    old = {k: read(EARLIER)[k] for k in FIELDS}
    assert data["prior_matrix_sha256"] == sha(EARLIER) and old == data["prior_matrix"]
    assert data["subscription_source_sha256"] == sha(STRONG)
    assert combine(data["additional_ledgers"].values()) == data["additional"]
    assert combine([old, data["additional"]]) == data["day"]
    assert data["day"]["settled_usd"] <= data["day"]["exposure_usd"] <= 20
    print("Additional", data["additional"], "same day", data["day"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check-local", "check"))
    args = parser.parse_args()
    if args.action == "check":
        validate(read(DEST))
        return
    artifacts = ROOT / "artifacts"
    stages = set()
    for pattern in (
        "self-*-20261124",
        "*incremental-self-*-20261124",
        "coherent-linker-20261124",
        "executable-self-options-20261124",
        "todomvc-executable-options-20261124",
        "strong-builder*-20261124",
    ):
        stages.update(artifacts.glob(pattern))
    ledgers = sorted(
        {p.resolve() for stage in stages for p in stage.rglob("budget.sqlite3")}
    )
    records = {str(p.relative_to(artifacts)): ledger_read.totals(p) for p in ledgers}
    earlier = {k: read(EARLIER)[k] for k in FIELDS}
    subscription = {
        k: v["subscription_usage"] for k, v in read(STRONG)["sources"].items()
    }
    extra = combine(records.values())
    data = {
        "prior_matrix_sha256": sha(EARLIER),
        "prior_matrix": earlier,
        "additional_ledgers": records,
        "additional": extra,
        "day": combine([earlier, extra]),
        "approved_usd": 20,
        "subscription_source_sha256": sha(STRONG),
        "gpt6_subscription_tokens": subscription,
    }
    validate(data)
    if args.action == "write":
        core.save(DEST, data)
    else:
        assert data == read(DEST)


if __name__ == "__main__":
    main()
