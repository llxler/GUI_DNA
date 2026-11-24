"""Score sealed candidates with the official current-task files and audit receipts."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from studies.ledger_read import calls, totals
from studies.public_library_transfer import browser
from studies.study_io import ROOT, read, sha
from .run import ARMS, MODELS, OUT, PROJECTS, TASKS, save, verify

OUTPUT = ROOT / "studies/results/backbone-matrix-20261124.json"


def score_model(tag):
    seal = read(OUT / tag / "seal.json")
    assert seal["registration"] == sha(OUT / "registered.json")
    protocols = {p: read(OUT / "inputs" / p / "browser.json") for p in PROJECTS}
    assert all(browser.verify_contract(p) == protocols[p] for p in PROJECTS)
    rows = list(seal["rows"])
    expected = len(PROJECTS) * len(TASKS) * len(ARMS)
    assert len(rows) == len(set((r["project"], r["task"], r["arm"]) for r in rows)) == expected
    for p, state in seal["builds"].items():
        if state["status"] == "valid":
            page = ROOT / state["fixed"]
            pkg = read(OUT / tag / p / "build/package.json")
            assert sha(OUT / tag / p / "build/package.json") == state["package_sha256"]
            assert pkg["examples"][0]["plan"] is not None
            files = browser.tree(page)
        for n in TASKS:
            row = {
                "project": p,
                "task": n,
                "model": MODELS[tag][0],
                "arm": "fixed",
                "status": state["status"],
            }
            if state["status"] == "valid":
                row.update(page=state["fixed"], files=files)
            rows.append(row)

    def one(row):
        p, n, arm, state = (row[k] for k in ("project", "task", "arm", "status"))
        result = {k: row[k] for k in ("project", "task", "arm", "status")}
        result["passed"] = None if state == "missing" else False
        if "response_sha256" in row:
            response = OUT / tag / p / arm / str(n) / "call/response.json"
            assert sha(response) == row["response_sha256"]
            result["response_sha256"] = row["response_sha256"]
        if state == "valid":
            receipt = browser.run_one(OUT, p, n, ROOT / row["page"], row["files"], protocols[p])
            result.update(
                passed=receipt["passed"],
                report_sha256=receipt["report_sha256"],
                files_digest=receipt["files_digest"],
            )
        elif state not in ("missing", "invalid", "build_failed"):
            raise ValueError(f"Unexpected candidate state {state}")
        return result

    with ThreadPoolExecutor(max_workers=5) as pool:
        outcomes = list(pool.map(one, rows))
    save(OUT / tag / "scores.json", {"seal_sha256": sha(OUT / tag / "seal.json"), "rows": outcomes})
    print(tag, "scored", len(outcomes), flush=True)


def report():
    verify()
    registry = read(OUT / "registered.json")
    result = {
        "registered_utc": registry["utc"],
        "generation_deadline": registry["end"],
        "registration_sha256": sha(OUT / "registered.json"),
        "projects": list(PROJECTS),
        "target_ids": list(TASKS),
        "upstream_commit": browser.UPSTREAM_COMMIT,
        "registration_inputs": registry["files"],
        "models": {},
    }
    for tag, (model, *_) in MODELS.items():
        scores = read(OUT / tag / "scores.json")
        seal = read(OUT / tag / "seal.json")
        assert scores["seal_sha256"] == sha(OUT / tag / "seal.json")
        observed = scores["rows"]
        expected = len(PROJECTS) * len(TASKS) * (len(ARMS) + 1)
        assert len(observed) == len({(r["project"], r["task"], r["arm"]) for r in observed}) == expected
        costs = totals(OUT / tag / "budget.sqlite3")
        by_method = defaultdict(lambda: {"calls": 0, "settled_microusd": 0, "exposure_microusd": 0})
        for req in calls(OUT / tag / "budget.sqlite3"):
            parts = req["purpose"].split("/")
            key = "/".join(parts[:2] if parts[0] == "build" else parts[:3])
            b = by_method[key]
            b["calls"] += 1
            b["settled_microusd"] += req["actual"] or 0
            b["exposure_microusd"] += req["actual"] if req["actual"] is not None else req["reserved"]
        assert round(costs["exposure_usd"] * 1e6) == sum(x["exposure_microusd"] for x in by_method.values())
        result["models"][model] = {
            "seal_sha256": scores["seal_sha256"],
            "ledger": costs,
            "cost_by_project_method": dict(by_method),
            "builds": seal["builds"],
            "model_stop": read(OUT / tag / "route-closed.json")
            if (OUT / tag / "route-closed.json").exists()
            else None,
            "status_counts": dict(Counter(r["status"] for r in observed)),
            "rows": observed,
        }
    result["budget"] = {
        k: round(sum(v["ledger"][k] for v in result["models"].values()), 6)
        for k in ("calls", "settled_usd", "exposure_usd", "unsettled_calls", "cap_usd")
    }
    assert result["budget"]["exposure_usd"] <= result["budget"]["cap_usd"] <= 20
    save(OUTPUT, result)
    print(result["budget"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("score", "report"))
    parser.add_argument("model", nargs="?", choices=MODELS)
    args = parser.parse_args()
    if args.action == "score":
        score_model(args.model)
    else:
        report()
