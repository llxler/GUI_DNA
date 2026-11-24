"""Reconcile consecutive API authorizations without adding released limits twice."""

from decimal import Decimal

from studies.study_io import ROOT, dump, read, sha

ORDER = ("matrix", "extension", "suites", "form")
RESULT = ROOT / "studies/results/backbone-allocations-20261124.json"


def usd(value):
    return Decimal(str(value))


def validate(stages, reports=None):
    limits = {}
    previous_time = ""
    for stage in stages:
        assert stage["registered_utc"] > previous_time
        previous_time = stage["registered_utc"]
        earlier = stage["prior_exposure_usd"]
        assert limits.keys() == earlier.keys()
        for key, value in earlier.items():
            assert 0 <= usd(value) <= usd(limits[key])
            if reports:
                name, model = key.split(":", 1)
                ledger = reports[name]["models"][model]["ledger"]
                assert usd(ledger["exposure_usd"]) <= usd(value)
        maximum = sum(map(usd, earlier.values())) + sum(map(usd, stage["new_limits_usd"].values()))
        assert maximum == usd(stage["max_total_usd"]) and maximum <= 20
        if reports:
            report = reports[stage["stage"]]
            assert (report.get("registration_sha256") or report["registered_sha256"]) == stage[
                "registration_sha256"
            ]
            assert {m: g["ledger"]["cap_usd"] for m, g in report["models"].items()} == stage["new_limits_usd"]
        limits.update(
            {stage["stage"] + ":" + model: limit for model, limit in stage["new_limits_usd"].items()}
        )


def reconstruct():
    stages = []
    prior_models = {}
    for name in ORDER:
        base = ROOT / "artifacts" / ("backbone-" + name + "-20261124")
        reg = read(base / "registered.json")
        if name == "extension":
            previous = read(base / "approval.json")["remaining_first_batch_liability"]
        else:
            previous = reg.get("prior_liability", {})
        prior_exposure = {}
        for label, value in previous.items():
            if "/" in label:
                parent, tag = label.split("/")
                parent = parent.removeprefix("backbone-").removesuffix("-20261124")
            else:
                (parent,) = (stage for stage, models in prior_models.items() if label in models)
                tag = label
            prior_exposure[parent + ":" + prior_models[parent][tag]] = value
        limits = {v[0]: v[1] for v in reg["models"].values()}
        total = sum(map(usd, prior_exposure.values())) + sum(map(usd, limits.values()))
        stages.append(
            dict(
                stage=name,
                registered_utc=reg["utc"],
                registration_sha256=sha(base / "registered.json"),
                prior_exposure_usd=prior_exposure,
                new_limits_usd=limits,
                max_total_usd=float(total),
            )
        )
        prior_models[name] = {tag: v[0] for tag, v in reg["models"].items()}
    validate(stages)
    return {"daily_cap_usd": 20, "stages": stages}


if __name__ == "__main__":
    dump(RESULT, reconstruct())
