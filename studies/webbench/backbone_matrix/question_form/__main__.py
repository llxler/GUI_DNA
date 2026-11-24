"""Run the seven available routes on the registered full question-form schedule."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.ledger_read import totals
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha
from studies.webbench.backbone_matrix import run
from studies.webbench.backbone_matrix import report as reporting

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/backbone-form-20261124"
OLD = ROOT / "artifacts/form-library-sources-20261121"
PARENTS = [ROOT / "artifacts" / f"backbone-{group}-20261124" for group in ("matrix", "extension", "suites")]
CAPS = {
    "gemma": 0.65,
    "qwen9": 0.7,
    "mistral": 0.75,
    "qwen": 0.75,
    "oss": 0.75,
    "deepseek-flash": 1.1,
    "deepseek-pro": 2.3,
}
PUBLIC = ROOT / "studies/results/backbone-form-20261124.json"


def register():
    if (OUT / "registered.json").is_file():
        run.verify()
        return
    registry = {}
    parameters = {}
    liability = {}
    for parent in PARENTS:
        saved = read(parent / "registered.json")
        parameters.update(saved["parameters"])
        for tag, (model, cap, pin, pout) in saved["models"].items():
            if tag in CAPS:
                registry[tag] = (model, CAPS[tag], pin, pout)
            base = parent / tag
            liability[f"{parent.name}/{tag}"] = (
                totals(base / "budget.sqlite3")["exposure_usd"] if (base / "seal.json").is_file() else cap
            )
    assert registry.keys() == CAPS.keys()
    cap = sum(Decimal(str(v)) for v in CAPS.values())
    assert cap + sum(Decimal(str(v)) for v in liability.values()) <= Decimal(20)
    balance = check_credits(float(cap))
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient account credit")
    dest = OUT / "inputs/form"
    private_inputs = [
        HERE / "PROTOCOL.md",
        Path(__file__),
        Path(run.__file__),
        Path(reporting.__file__),
        Path(core.__file__),
        Path(browser.__file__),
        ROOT / "studies/interface_blind/core.py",
        ROOT / "studies/interface_blind/compile.cjs",
        ROOT / "src/gui_dna/budget.py",
    ]
    project = core.public_input("form")
    core.save(dest / "public.json", project)
    core.save(dest / "browser.json", browser.verify_contract("form"))
    calibration = read(ROOT / "studies/results/public-library-transfer-calibration-20261123.json")
    (current,) = browser.calibration_evidence(ROOT / calibration["artifacts"], ("form",))
    assert current in calibration["projects"] and current["tested_tasks"] == list(run.TASKS)
    core.save(dest / "calibration.json", current)
    for arm, archived in [("human", "reference"), ("gpt5-library", "ai"), ("direct", "direct")]:
        if arm != "direct":
            package = OLD / (archived + "-package.json")
            private_inputs.append(package)
            core.save(dest / (arm + ".json"), read(package))
        for task in run.TASKS:
            source = OLD / archived / f"task-{task}" / "call/request.json"
            private_inputs.append(source)
            messages = read(source)["body"]["messages"]
            messages[-1]["content"] += "\n\nPublic starter files, provided to all workflows:\n" + json.dumps(
                project["starter"], ensure_ascii=False
            )
            core.save(dest / arm / f"{task}.json", messages)
    private_inputs.extend(p for p in dest.rglob("*") if p.is_file())
    core.save(
        OUT / "registered.json",
        dict(
            utc=core.now(),
            end=run.END.isoformat(),
            models=registry,
            parameters={m: parameters[m] for m, *_ in registry.values()},
            budget_usd=float(cap),
            balance=balance,
            parent_registry_sha256={p.name: sha(p / "registered.json") for p in PARENTS},
            prior_liability=liability,
            files={str(p.relative_to(ROOT)): sha(p) for p in private_inputs},
        ),
    )


def generate(tag):
    with browser.lock(OUT / tag / ".run.lock"):
        if (OUT / tag / "seal.json").is_file():
            return
        run.verify()
        ledger = Ledger(OUT / tag / "budget.sqlite3", CAPS[tag], CAPS[tag])
        run.target(tag, "form", "direct", 1, ledger)
        state = run.build(tag, "form", ledger)
        jobs = [(task, arm) for task in run.TASKS for arm in run.ARMS]
        with ThreadPoolExecutor(max_workers=3) as workers:
            rows = list(workers.map(lambda job: run.target(tag, "form", job[1], job[0], ledger), jobs))
        core.save(
            OUT / tag / "seal.json",
            dict(
                utc=core.now(), registration=sha(OUT / "registered.json"), rows=rows, builds={"form": state}
            ),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "generate", "score", "report"))
    parser.add_argument("tag", nargs="?", choices=CAPS)
    args = parser.parse_args()
    run.OUT = reporting.OUT = browser.OUT = OUT
    if args.action == "register":
        register()
        return
    reg = read(OUT / "registered.json")
    run.MODELS = reporting.MODELS = reg["models"]
    run.PROJECTS = reporting.PROJECTS = ("form",)
    reporting.OUTPUT = PUBLIC
    if args.action in ("generate", "score") and args.tag is None:
        parser.error("Choose a registered model")
    if args.action == "generate":
        generate(args.tag)
    elif args.action == "score":
        reporting.score_model(args.tag)
    else:
        reporting.report()


if __name__ == "__main__":
    main()
