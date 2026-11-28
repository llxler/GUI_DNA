"""Repair an author's original handlers with only concrete DOM arguments in scope."""

from pathlib import Path
import re
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as parent

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-dom-contract-20261128"
ORIGINAL = parent.OUT
CAP = 0.65


def register():
    path = OUT / "registration.json"
    paths = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(parent.__file__),
        parent.HERE / "dispatch.js",
        ORIGINAL / "registration.json",
        Path(parent.table.__file__),
        Path(parent.table.probes.__file__),
    ]
    sums = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not path.exists():
        previous = read(ORIGINAL / "registration.json")
        upper = previous["upper"] + CAP
        assert upper <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        core.save(
            path,
            dict(
                utc=now(),
                cap=CAP,
                upper=upper,
                deadline=previous["deadline"],
                balance=balance,
                sources=sums,
                contract=previous["contract"],
                models=previous["models"],
            ),
        )
    assert read(path)["sources"] == sums
    return read(path)


def dom_body(raw):
    code = parent.handler(raw)
    if re.search(
        r"\b(?:env\s*(?:\.\s*api\b|\[\s*['\"]api['\"]\s*\])|window\s*\.\s*api\b)", code
    ):
        raise ValueError(
            "There is no application API. Implement the interaction with the actual DOM node arguments."
        )
    return code


def generate_handler(
    tag, role, pub, design, library, folder, ledger, trial, feedback=None
):
    previous = read(ORIGINAL / "libraries" / tag / "library.json")
    attempt = int(folder.parent.parent.name)
    source = next((t for t in previous["trials"] if t["attempt"] == attempt), None)
    if feedback is None and source and source["events"]:
        original = source["events"][0]["hooks"][role]
        core.save(
            folder / "reused.json",
            dict(
                parent_seal=sha(ORIGINAL / "seal.json"),
                attempt=attempt,
                role=role,
                body_digest=browser.digest(original),
            ),
        )
        return original
    description, ids = parent.ROLES[role]
    msg = core.messages(
        "Write only the JavaScript statements for this one event handler. Each parameter is real: env.table is the live HTMLTableElement, env.state is your shared object, cell the original td or th, item the clicked DOM element, event a MouseEvent, menu the actual mounted HTMLElement. There is NO callable application API. Implement operations directly on the real nodes with standard browser methods and DOM properties. A prior helper name or proposed interface does not implement it. For dismissal, use the supplied menu node itself. For a row or column mutation, perform the mutation yourself. For open, return the detached element with the exact public DOM classes and items. Other handlers may remain unchanged. No listener registration, JSON, function wrapper or imports.",
        dict(
            role=role,
            task=description,
            public_requirements=[pub["requirements"][i - 1] for i in ids],
            your_existing_handlers=library,
            browser=feedback or {},
        ),
    )
    return parent.table.ask(
        ledger, tag, trial + 11, folder, msg, "build", dom_body, 2400
    )


def run():
    reg = register()
    sealed = ORIGINAL / "seal.json"
    if not sealed.exists():
        return
    tags = [
        t for t, v in read(sealed)["libraries"].items() if v["status"] == "build_failed"
    ]
    selected = reg | {"models": {t: reg["models"][t] for t in tags}}
    with (
        patch.multiple(parent, OUT=OUT, CAP=CAP, generate_handler=generate_handler),
        patch.multiple(parent.table, OUT=OUT, HERE=HERE),
    ):
        parent.generate(selected)
        if not (HERE / "result.json").exists():
            parent.table.score(selected)


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        run()
