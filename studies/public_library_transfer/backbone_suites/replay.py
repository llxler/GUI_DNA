"""Recover decisive official-file outcomes when a component registers additional Jest cases."""

import argparse
from pathlib import Path

from studies.public_library_transfer.other_benchmarks import evaluate
from studies.study_io import ROOT, read, sha
from .run import OUT, MODELS, RESULT, inputs, save, score

PUBLIC_RECEIPTS = ROOT / "studies/results/backbone-suite-replays-20261124.json"


def decide(expected, assertions):
    if len(expected) != 4 or len(set(expected)) != 4:
        raise ValueError("Reference fixture must identify four distinct official cases")
    groups = {name: [r["status"] for r in assertions if r["fullName"] == name] for name in expected}
    if any(values and set(values) == {"failed"} for values in groups.values()):
        return False
    if all(values and set(values) == {"passed"} for values in groups.values()):
        return True
    return None


def recover(tag):
    restored = 0
    targets, _ = inputs()
    sealed = read(OUT / tag / "seal.json")
    for row in sealed["rows"]:
        task, arm = row["task"], row["arm"]
        where = OUT / tag / "scores" / task / arm
        raw = where / "jest.json"
        if row["group"] == "todomvc" or not raw.is_file() or (where / "verdict.json").exists():
            continue
        parsed = read(raw)["testResults"]
        if len(parsed) != 1:
            continue
        cases = parsed[0]["assertionResults"]
        if len(cases) <= 4:
            continue
        target = targets[task]
        official = ROOT / target["test"]
        stage = where / "staging/src/react" / row["group"]
        assert sha(official) == target["test_sha256"] == sha(stage / official.name)
        assert (stage / official.name).resolve() == Path(parsed[0]["name"]).resolve()
        source = OUT / tag / "targets" / task / arm / "files.json"
        assert sha(source) == row["files_sha256"]
        assert all((stage / k).read_text() == v for k, v in read(source).items())
        control = OUT / "replay-controls" / task
        control.mkdir(parents=True, exist_ok=True)
        if not (control / "verdict.json").exists():
            outcome = evaluate.jest(
                target,
                {target["public"]["module"] + ".js": "export default function Empty(){return null;}"},
                control,
            )
            save(control / "verdict.json", outcome)
        reference = read(control / "jest.json")["testResults"][0]["assertionResults"]
        names = [r["fullName"] for r in reference]
        outcome = decide(names, cases)
        if outcome is None:
            print("Ambiguous:", tag, task, arm, flush=True)
            continue
        receipt = {
            "passed": outcome,
            "official_tests": 4,
            "report_sha256": sha(raw),
            "reference_sha256": sha(control / "jest.json"),
            "official_titles": names,
            "observed_count": len(cases),
            "test_sha256": target["test_sha256"],
            "files_sha256": row["files_sha256"],
            "recovery": "duplicate registrations; unanimous evidence by official case title",
        }
        save(OUT / "replay-receipts" / tag / task / (arm + ".json"), receipt)
        save(where / "verdict.json", receipt)
        print(tag, task, arm, outcome, len(cases), flush=True)
        restored += 1
    return restored


def publish():
    """Link each recovered verdict to its released candidate and official report."""
    scores = read(RESULT)
    receipts = []
    for path in sorted((OUT / "replay-receipts").glob("*/*/*.json")):
        tag, task, filename = path.relative_to(OUT / "replay-receipts").parts
        arm = Path(filename).stem
        model = MODELS[tag][0]
        item = read(path)
        (row,) = (r for r in scores["models"][model]["rows"] if (r["task"], r["arm"]) == (task, arm))
        assert all(item[k] == row[k] for k in ("passed", "report_sha256", "files_sha256", "official_tests"))
        raw = OUT / tag / "scores" / task / arm / "jest.json"
        assert sha(raw) == item["report_sha256"]
        observations = read(raw)["testResults"][0]["assertionResults"]
        assert item["passed"] is decide(item["official_titles"], observations)
        statuses = {
            name: [a["status"] for a in observations if a["fullName"] == name]
            for name in item["official_titles"]
        }
        receipts.append(dict(model=model, task=task, arm=arm, case_statuses=statuses, **item))
    save(PUBLIC_RECEIPTS, {"suite_results_sha256": sha(RESULT), "rows": receipts})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", choices=MODELS, nargs="?")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--finish", action="store_true")
    args = parser.parse_args()
    if args.publish:
        publish()
        raise SystemExit
    if not args.tag:
        parser.error("Select a registered model or use --publish")
    recover(args.tag)
    if args.finish:
        while not (OUT / args.tag / "scores.json").exists():
            try:
                score(args.tag)
            except RuntimeError as e:
                if "Expected four official assertions" not in str(e) or not recover(args.tag):
                    raise
