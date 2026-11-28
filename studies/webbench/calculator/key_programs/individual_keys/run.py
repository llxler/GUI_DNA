"""Recover a builder's own key programs and freeze the same target decisions."""

import ast
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as keys

base = keys.base
HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/calculator-individual-keys-20261128"
CAP = 0.70
BASIC = set("0123456789+-*/.=") | {"clear", "Clear"}


def register():
    dst = OUT / "registration.json"
    parent = read(keys.OUT / "registration.json")
    tags = [
        t
        for t in parent["models"]
        if sum(read(keys.OUT / "libraries" / t / "library.json")["checks"].values()) * 2
        < len(base.EXPECTED)
    ]
    assert set(tags) == {"gemma", "qwen9"}
    paths = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(keys.__file__),
        keys.OUT / "registration.json",
    ]
    for tag in tags:
        folder = keys.OUT / "libraries" / tag
        paths.append(folder / "library.json")
        for group in keys.KEYS:
            paths.extend(
                (folder / "programs" / group / "0" / "0").glob(
                    "transmission-*/settled.json"
                )
            )
    sums = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not dst.exists():
        prior = (
            parent["prior_exposure"]
            + ledger_read.totals(keys.increment.OUT / "budget.sqlite3")["exposure_usd"]
        )
        upper = prior + keys.structured.CAP + keys.CAP + CAP
        assert upper <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        core.save(
            dst,
            dict(
                utc=now(),
                cap=CAP,
                upper=upper,
                deadline=parent["deadline"],
                models={t: parent["models"][t] for t in tags},
                balance=balance,
                sources=sums,
            ),
        )
    assert read(dst)["sources"] == sums
    return read(dst)


def order(values, labels):
    if not isinstance(values, list):
        raise ValueError("Expected an ordered list of labels")
    result = []
    for item in values:
        label = item[0] if isinstance(item, list) and item else item
        if not isinstance(label, str):
            raise ValueError("Missing label")
        if label not in BASIC:
            if label not in labels or label in result:
                raise ValueError("Unexpected or repeated extension label")
            result.append(label)
    return result


def pair(value):
    if isinstance(value, str):
        value = ast.literal_eval(value)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Expected a pair of expressions")
    return [keys.expression(expr) for expr in value]


def archived(tag, group):
    folder = keys.OUT / "libraries" / tag / "programs" / group / "0" / "0"
    receipts = sorted(folder.glob("transmission-*/settled.json"))
    if not receipts:
        raise ValueError("No original settled answer")
    response = receipts[0].with_name("response.json")
    assert sha(response) == read(receipts[0])["response_sha256"]
    obj = json.loads(
        base.calc.base.uncode(read(response)["choices"][0]["message"]["content"])
    )
    labels = keys.KEYS[group]
    spec = dict(
        early=order(obj["early"], labels),
        full=order(obj["full"], labels),
        actions={k: pair(obj["actions"][k]) for k in labels},
        panel=obj.get("panel"),
    )
    return keys.parse(json.dumps(spec), group)


def ask(tag, folder, system, payload, ledger, trial, parse):
    messages = core.messages(system, payload)
    for turn in range(2):
        raw = base.request(
            ledger, tag, folder / str(turn), messages, "build", 650, trial + 37
        )
        try:
            return parse(json.loads(base.calc.base.uncode(raw)))
        except (SyntaxError, ValueError, TypeError, KeyError) as exc:
            if turn:
                raise ValueError(str(exc)) from exc
            messages.extend(
                [
                    dict(role="assistant", content=raw),
                    dict(
                        role="user",
                        content=f"Format check: {exc}. Return only the requested JSON.",
                    ),
                ]
            )
    raise AssertionError("unreachable")


def individual(tag, group, folder, pub, ledger, trial):
    labels = keys.KEYS[group]
    brief = [pub["requirements"][i - 1]["description"] for i in base.GROUPS[group][0]]

    def layout(obj):
        early = order(obj["early"], labels)
        full = order(obj["full"], labels)
        if not early or set(full) != set(labels):
            raise ValueError(
                "Supply the extension labels in order, including every extension in full"
            )
        return dict(early=early, full=full, panel=obj.get("panel"))

    spec = ask(
        tag,
        folder / "order",
        "Choose the order of the extension buttons only. The starter owns all ordinary digits and arithmetic. Return a JSON object with early and full arrays of extension labels in your order. For memory also supply panel, the public id of the memory display.",
        dict(public_changes=brief, extension_labels=labels),
        ledger,
        trial,
        layout,
    )
    actions = {}
    for i, label in enumerate(labels):
        actions[label] = ask(
            tag,
            folder / str(i),
            "Implement the one named calculator key. Return only a JSON array of two short JavaScript expression strings: the new display and the new memory register. Variables are d (display text), x (display as number), and m (numeric memory). Unchanged display or memory may be returned directly. Use plain JavaScript Math, Number, String and arithmetic; no statements. Do not describe the entire keyboard.",
            dict(public_changes=brief, key=label),
            ledger,
            trial,
            pair,
        )
    return keys.parse(json.dumps(spec | dict(actions=actions)), group)


def build(tag, pub, ledger):
    root = OUT / "libraries" / tag
    dest = root / "library.json"
    if dest.exists():
        return read(dest)
    parent = read(keys.OUT / "libraries" / tag / "library.json")
    parts, neutral = dict(parent["parts"]), dict(parent["neutral"])
    checks = parent["checks"]
    trials = {}
    for group in keys.KEYS:
        trials[group] = []
        if all(checks[k] for k in base.GROUPS[group][1]):
            continue
        for n in range(3):
            folder = root / group / str(n)
            item = dict(
                attempt=n + 1,
                source="archived" if n == 0 else "individual",
                accepted=False,
            )
            try:
                spec = (
                    archived(tag, group)
                    if n == 0
                    else individual(tag, group, folder, pub, ledger, n)
                )
                proposed = parts | {group: keys.module(spec)}
                page = base.compile_page(
                    pub["starter"]["index.html"], proposed, base.FULL, folder / "page"
                )
                observed = base.probe(page)
                item.update(spec=spec, checks=observed)
                if all(not v or observed[k] for k, v in checks.items()) and sum(
                    observed.values()
                ) > sum(checks.values()):
                    item["accepted"] = True
                    parts, checks = proposed, observed
                    neutral[group] = keys.module(spec, True)
            except (
                SyntaxError,
                ValueError,
                TypeError,
                KeyError,
                *base.calc.action.typed.MISSING,
            ) as exc:
                item["error"] = str(exc)
            trials[group].append(item)
            if item["accepted"]:
                break
    core.save(
        dest,
        dict(
            status="valid",
            initial=parent["checks"],
            checks=checks,
            history=trials,
            parts=parts,
            neutral=neutral,
        ),
    )
    return read(dest)


def run(reg):
    tags = list(reg["models"])
    pub = read(base.calc.OUT / "public.json")
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    with (
        patch.multiple(base.calc.base, OUT=OUT, END=base.END, template=base.settings),
        ThreadPoolExecutor(max_workers=len(tags)) as pool,
    ):
        libs = dict(
            zip(tags, pool.map(lambda t: build(t, pub, ledger), tags), strict=True)
        )
    parent_seal = keys.OUT / "seal.json"
    if not parent_seal.exists():
        return
    dst = OUT / "seal.json"
    if not dst.exists():
        seal = read(parent_seal)
        all_rows = []
        for tag in tags:
            parent_lib = read(keys.OUT / "libraries" / tag / "library.json")
            choices = [
                r for r in seal["rows"] if r["tag"] == tag and r["arm"] == "self"
            ]
            assert len(choices) == 20
            for choice in choices:
                for arm, parts, levels in [
                    ("self", libs[tag]["parts"], choice["levels"]),
                    ("old-code-same-choice", parent_lib["parts"], choice["levels"]),
                    ("fixed-self", libs[tag]["parts"], base.FULL),
                    ("fixed-old", parent_lib["parts"], base.FULL),
                    ("neutral-key-effects", libs[tag]["neutral"], base.FULL),
                    ("binding-only", {}, base.NONE),
                ]:
                    candidate = (
                        dict(status=choice["status"])
                        if levels is None
                        else base.compile_page(
                            pub["starter"]["index.html"],
                            parts,
                            levels,
                            OUT / "pages" / tag / arm / "".join(map(str, levels)),
                        )
                    )
                    all_rows.append(
                        dict(
                            project="calculator",
                            tag=tag,
                            arm=arm,
                            task=choice["task"],
                            levels=levels,
                            **candidate,
                        )
                    )
        core.save(
            dst,
            dict(
                registration=sha(OUT / "registration.json"),
                parent_seal=sha(parent_seal),
                additive_seal=seal["additive_seal"],
                catalogs={t: seal["catalogs"][t] for t in tags},
                libraries={
                    t: {k: v for k, v in lib.items() if k not in ("parts", "neutral")}
                    for t, lib in libs.items()
                },
                rows=all_rows,
            ),
        )
    if not (HERE / "result.json").exists():
        with (
            patch.multiple(keys, OUT=OUT, HERE=HERE),
            patch.object(base, "TARGETS", tags),
        ):
            keys.score(reg)
        # The inherited scorer verifies the common environment and writes compact per-task receipts.
        result = read(HERE / "result.json")
        core.save(HERE / "result.json", result | {"parent_seal": sha(parent_seal)})


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        run(register())
