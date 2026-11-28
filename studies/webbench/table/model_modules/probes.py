"""Browser-only observations on the public starter and the generated library."""

import sys
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, Error
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read
from pathlib import Path

KEYS = (
    "menu",
    "insert",
    "outside",
    "click",
    "right",
    "tab",
    "reverse",
    "edit",
    "clear",
)


def observe(spec, heldout):
    flags = dict.fromkeys(KEYS, False)
    page = browser.served_page(
        ROOT / "artifacts/table-model-modules-20261128",
        "table",
        ROOT / spec["page"],
        spec["files"],
    )
    errors = []
    with (
        browser.serve("table", page) as url,
        sync_playwright() as pw,
        pw.chromium.launch(env=browser.browser_env()) as engine,
    ):
        tab = engine.new_page(service_workers="block")
        tab.set_default_timeout(1800)
        tab.route(
            "**/*",
            lambda r: (
                r.continue_()
                if urlsplit(r.request.url).netloc == urlsplit(url).netloc
                else r.abort()
            ),
        )
        tab.on("pageerror", lambda exc: errors.append(str(exc)[:160]))

        def reset():
            tab.goto(url + "/index.html", timeout=6000)

        def marked():
            return tab.locator(".table td.selected,.table th.selected").evaluate_all(
                "xs=>xs.map(x=>[x.parentElement.rowIndex,x.cellIndex])"
            )

        def selected_at(cell):
            return cell.evaluate("c=>c.classList.contains('selected')")

        try:
            reset()
            row = 1 if heldout else 0
            target = (
                tab.locator("tbody tr").nth(row).locator("td").nth(1 if heldout else 0)
            )
            target.click(button="right")
            menu = tab.locator(".menu:visible").first
            flags["menu"] = menu.count() > 0
            before = tab.locator("tbody tr").count()
            insert = menu.locator(".menu-item-insert-row-above")
            if insert.count():
                insert.first.click()
            flags["insert"] = tab.locator("tbody tr").count() == before + 1
            target.click(button="right")
            visible = menu.count() > 0
            tab.locator("body").evaluate(
                "e=>e.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,button:2}))"
            )
            flags["outside"] = visible and menu.count() == 0
        except Error as e:
            errors.append(str(e).splitlines()[0][:120])
        try:
            reset()
            tr = tab.locator("tbody tr").nth(1 if heldout else 0)
            c0, c1, c2 = [tr.locator("td").nth(i) for i in range(3)]
            c0.click()
            flags["click"] = selected_at(c0)
            tab.keyboard.press("ArrowRight")
            flags["right"] = selected_at(c1)
            tab.keyboard.press("Tab")
            flags["tab"] = selected_at(c2)
            tab.keyboard.press("Shift+Tab")
            flags["reverse"] = selected_at(c1)
            tab.keyboard.press("Enter")
            editing = c1.evaluate("c=>c.isContentEditable")
            tab.keyboard.press("Escape")
            flags["edit"] = (
                editing
                and not c1.evaluate("c=>c.isContentEditable")
                and selected_at(c1)
            )
            c2.click()
            before = c2.text_content()
            tab.keyboard.press("Delete")
            flags["clear"] = bool(before.strip()) and c2.text_content().strip() == ""
            observed = marked()
        except Error as e:
            observed = []
            errors.append(str(e).splitlines()[0][:120])
    return dict(checks=flags, errors=errors[:6], final_selection=observed)


if __name__ == "__main__":
    source, destination, held = sys.argv[1:]
    core.save(Path(destination), observe(read(Path(source)), held == "heldout"))
