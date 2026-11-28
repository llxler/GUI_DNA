"""Ask each failed table builder for exact edits using a public DOM-event trace."""

import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, Error
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.key_programs.individual_keys import run as individuals
from .. import run as table
from ..structured_design import run as structured

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-self-public-trace-20261128"
CAP = 1.10
SNAPSHOT = """() => {
  const visible = x => !!(x.getClientRects().length && getComputedStyle(x).visibility!=='hidden');
  const menu = [...document.querySelectorAll('[class*="menu" i], [role=menu], [role=menuitem]')].slice(0,35);
  return {menus:menu.map(x=>({tag:x.tagName,cls:x.className,text:x.textContent.trim().slice(0,65),visible:visible(x)})),
    selected:[...document.querySelectorAll('td.selected,th.selected')].map(c=>[c.parentNode.rowIndex,c.cellIndex]),
    rows:document.querySelector('tbody')?.rows.length, events:window.publicMenuEvents.slice(-14)};
}"""


def register():
    dest = OUT / "registration.json"
    prior = read(individuals.OUT / "registration.json")
    paths = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(structured.__file__),
        Path(table.__file__),
        Path(table.probes.__file__),
        structured.OUT / "registration.json",
        individuals.OUT / "registration.json",
    ]
    sums = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not dest.exists():
        upper = prior["upper"] + CAP
        assert upper <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        previous = read(structured.OUT / "registration.json")
        core.save(
            dest,
            dict(
                utc=now(),
                deadline=prior["deadline"],
                cap=CAP,
                upper=upper,
                models=previous["models"],
                contract=previous["contract"],
                balance=balance,
                sources=sums,
            ),
        )
    assert read(dest)["sources"] == sums
    return read(dest)


def trace(candidate):
    directory = browser.served_page(
        OUT, "table", ROOT / candidate["page"], candidate["files"]
    )
    with (
        browser.serve("table", directory) as url,
        sync_playwright() as pw,
        pw.chromium.launch(env=browser.browser_env()) as engine,
    ):
        tab = engine.new_page(service_workers="block")
        tab.set_default_timeout(2000)
        tab.route(
            "**/*",
            lambda r: (
                r.continue_()
                if urlsplit(r.request.url).netloc == urlsplit(url).netloc
                else r.abort()
            ),
        )
        errors = []
        tab.on("pageerror", lambda e: errors.append(str(e)[:180]))
        tab.goto(url + "/index.html", timeout=8000)
        tab.evaluate("""() => {
          window.publicMenuEvents=[];
          for (const type of ['click','contextmenu']) {
            for (const target of [document, document.querySelector('table')]) {
              for (const capture of [true,false]) target.addEventListener(type,e=>{
                window.publicMenuEvents.push([type,target.nodeName,capture,e.target.nodeName,e.target.className,
                 [...document.querySelectorAll('[class*="menu" i]')].filter(x=>x.getClientRects().length).length]);
              },capture);
            }
          }
        }""")
        cell = tab.locator("tbody td").first
        steps = {}
        for name in (
            "right click body cell",
            "click visible Insert Row Above",
            "right click body cell again",
            "right click outside table",
            "left click body cell",
        ):
            try:
                if name.startswith("right click body"):
                    cell.click(button="right")
                elif name.startswith("click visible"):
                    item = tab.locator(".menu-item-insert-row-above:visible").first
                    if item.count():
                        item.click()
                elif name.startswith("right click outside"):
                    tab.locator("body").evaluate(
                        "e=>e.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,button:2}))"
                    )
                else:
                    cell.click()
            except Error as exc:
                errors.append(str(exc).splitlines()[0][:150])
            steps[name] = tab.evaluate(SNAPSHOT)
        return {"steps": steps, "errors": errors[:8]}


def edits(raw, source):
    obj = json.loads(table.model_api.calc.base.uncode(raw))
    items = obj["edits"]
    if not isinstance(items, list) or not 1 <= len(items) <= 8:
        raise ValueError("Return one to eight exact edits")
    files = dict(source)
    for edit in items:
        f, old, new = (edit[k] for k in ("file", "before", "after"))
        if (
            f not in files
            or not isinstance(old, str)
            or not old.strip()
            or not isinstance(new, str)
            or files[f].count(old) != 1
        ):
            raise ValueError(
                "Each before string must occur exactly once in its named original file"
            )
        files[f] = files[f].replace(old, new, 1)
    for f in {item["file"] for item in items}:
        table.source(files[f])
    return files, items


def build(tag, ledger, pub):
    root = OUT / "libraries" / tag
    dest = root / "library.json"
    if dest.exists():
        return read(dest)
    original = structured.OUT / "libraries" / tag
    parent = read(original / "library.json")
    assert parent["status"] == "build_failed"
    trials = []
    for t in parent["trials"]:
        i = t["attempt"]
        receipt = original / str(i) / "attempt.json"
        src = read(receipt)
        mods, parts = src["design"], src["files"]
        location = root / str(i)
        events = []
        state = src["public"]
        status = "build_failed"
        if mods and len(parts) == len(mods):
            for turn in range(2):
                page = table.emit(
                    pub, mods, parts, len(mods), location / f"before-{turn}"
                )
                state = table.inspect(page, location / f"baseline-{turn}")
                if (
                    all(state["checks"][k] for k in table.REQUIRED)
                    and not state["errors"]
                ):
                    status = "valid"
                    break
                observation = trace(page)
                folder = location / str(turn)
                core.save(folder / "trace.json", observation)
                message = core.messages(
                    "Repair the interaction in your own files. Right-click a body cell to show the public menu, use Insert Row Above, dismiss it on an outside click or contextmenu, and left-click to select the cell visibly. Match the public class names and consult the live event sequence and current files. Preserve other working behavior. Return a JSON object with edits, each with file, before, after. Before is a short unique exact literal fragment from that file. Apply at most eight replacements in order. Do not replace entire files or rely on a particular row's contents.",
                    dict(
                        public_changes=pub["requirements"][:7],
                        design=mods,
                        files=parts,
                        checks=state,
                        observations=observation,
                    ),
                )
                try:
                    revised, changes = table.ask(
                        ledger,
                        tag,
                        i + turn + 30,
                        folder / "repair",
                        message,
                        "build",
                        lambda raw: edits(raw, parts),
                        2800,
                    )
                    proposed = table.emit(
                        pub, mods, revised, len(mods), folder / "candidate"
                    )
                    after = table.inspect(proposed, folder / "probe")
                    passed, before = after["checks"], state["checks"]
                    use = all(not v or passed[k] for k, v in before.items()) and (
                        sum(passed.values()) > sum(before.values())
                        or (not after["errors"] and bool(state["errors"]))
                    )
                    events.append(
                        dict(
                            adopted=use,
                            checks=after,
                            edits=changes,
                            trace_sha256=sha(folder / "trace.json"),
                        )
                    )
                    if use:
                        parts, state = revised, after
                    if (
                        all(state["checks"][k] for k in table.REQUIRED)
                        and not state["errors"]
                    ):
                        status = "valid"
                        break
                except table.model_api.calc.action.typed.MISSING as exc:
                    events.append(dict(transport=str(exc)))
                    status = "missing"
                    break
                except ValueError as exc:
                    events.append(dict(error=str(exc)))
        trials.append(
            dict(
                attempt=i,
                status=status,
                source_sha256=sha(receipt),
                events=events,
                public=state,
            )
        )
        if status in ("valid", "missing"):
            break
    admitted = trials[-1]["status"] == "valid"
    core.save(
        dest,
        dict(
            status=trials[-1]["status"],
            attempt=i if admitted else None,
            parts=parts if admitted else {},
            design=mods if admitted else [],
            trials=trials,
        ),
    )
    return read(dest)


def run():
    reg = register()
    sealed = structured.OUT / "seal.json"
    if not sealed.exists():
        return
    parent = read(sealed)
    tags = [t for t, d in parent["libraries"].items() if d["status"] == "build_failed"]
    model_reg = reg | {"models": {t: reg["models"][t] for t in tags}}
    with patch.multiple(
        table, OUT=OUT, HERE=HERE, CAP=CAP, TAGS=tuple(tags), build=build
    ):
        table.generate(model_reg)
        if not (HERE / "result.json").exists():
            table.score(model_reg)
            core.save(
                HERE / "result.json",
                read(HERE / "result.json") | {"parent_seal": sha(sealed)},
            )


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        run()
