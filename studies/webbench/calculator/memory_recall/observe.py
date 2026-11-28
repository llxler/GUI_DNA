"""Inspect the public requirement that recalling memory appends to an existing display."""

from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser
from studies.study_io import ROOT, UPSTREAM, read
from studies.webbench.calculator.key_programs import run as keys
from studies.webbench.calculator.key_programs.individual_keys import run as individual

ACTION = """({deposit,operand,second,deduct}) => {
 const buttons=()=>[...document.querySelectorAll('button')].filter(x=>x.getClientRects().length && getComputedStyle(x).visibility!=='hidden');
 const display=()=>String(document.querySelector('#display')?.value ?? '');
 const press=label=>{const b=buttons().find(x=>x.textContent.trim()===label); if(!b)return false;b.click();return true;};
 const sequence=(...labels)=>labels.every(press);
 const actions={};
 const memory=['MR','M+','M-','MC'];
 const labels=buttons().map(x=>x.textContent.trim());
 const first=sequence('MC','Clear',deposit,'M+','Clear',operand,'MR');
 actions.recallAppends={seen:display(),ok:first && display()===operand+deposit};
 const multiple=sequence('MC','Clear',deposit,'M+','Clear',second,'M+','Clear',operand,'MR');
 actions.multipleDeposits={seen:display(),ok:multiple && display()===operand+String(Number(deposit)+Number(second))};
 const sub=sequence('MC','Clear',deposit,'M+','Clear',deduct,'M-','Clear',operand,'MR');
 actions.subtractThenRecall={seen:display(),ok:sub && display()===operand+String(Number(deposit)-Number(deduct))};
 const reset=sequence('MC','Clear',operand,'MR');
 actions.clearRegister={seen:display(),ok:reset && display()===operand+'0'};
 const index=labels.indexOf('MR');
 actions.keyOrder={seen:labels.filter(x=>memory.includes(x)),ok:index>=0 && memory.every((label,i)=>labels[index+i]===label)};
 return actions;
}"""


def observe(folder: Path, independent=False):
    with (
        browser.serve("calculator", folder) as url,
        sync_playwright() as pw,
        pw.chromium.launch(env=browser.browser_env()) as engine,
    ):
        page = engine.new_page(service_workers="block")
        page.route(
            "**/*",
            lambda r: (
                r.continue_()
                if urlsplit(r.request.url).netloc == urlsplit(url).netloc
                else r.abort()
            ),
        )
        page.goto(url, timeout=10000)
        digits = ("7", "3", "2", "4") if independent else ("4", "2", "3", "1")
        return page.evaluate(
            ACTION,
            dict(zip(("deposit", "operand", "second", "deduct"), digits, strict=True)),
        )


def foundation(tag):
    stage = individual.OUT if tag in ("gemma", "qwen9") else keys.OUT
    seal = read(stage / "seal.json")
    page = next(r for r in seal["rows"] if r["tag"] == tag and r["arm"] == "fixed-self")
    return stage, page


if __name__ == "__main__":
    for tag in ("starter", "reference", *keys.base.TARGETS):
        page = (
            UPSTREAM
            / "projects/calculator"
            / ("src-init" if tag == "starter" else "src")
            if tag in ("starter", "reference")
            else ROOT / foundation(tag)[1]["page"]
        )
        checks = observe(page)
        print(
            tag,
            {k: v["seen"] for k, v in checks.items()},
            [k for k, v in checks.items() if v["ok"]],
        )
