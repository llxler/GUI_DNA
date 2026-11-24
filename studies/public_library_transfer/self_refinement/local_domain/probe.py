"""Observe seeded public button interactions and score a predeclared separate fixed component page."""
import json
from pathlib import Path
import subprocess
import sys

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.todomvc_dna.evaluate import browser_env
from .run import HERE, OUT, SEEDS, TASKS, row
from .templates import assemble


def freeze():
    contract = {"protocol": sha(HERE / "PROBE.md"), "code": sha(Path(__file__)),
                "primary_contract": sha(OUT / "registered.json")}
    target = OUT / "probe" / "registered.json"
    if target.exists():
        assert read(target)["contract"] == contract
    else:
        core.save(target, {"registered": now(), "contract": contract})


def observe(page, labels):
    _, runtime, _ = browser.contract("calculator")
    script = """
const { chromium } = require(process.argv[1]);
(async () => {
 const browser = await chromium.launch();
 try {
  const result = {};
  for (const key of [null, ...JSON.parse(process.argv[3])]) {
   const errors = [];
   const page = await browser.newPage();
   page.on('pageerror', error => errors.push(String(error).slice(0,260)));
   await page.goto(process.argv[2] + '/index.html', {waitUntil:'load'});
   const obs = await page.evaluate(label => {
    const buttons = () => Array.from(document.querySelectorAll('button'));
    const byLabel = label => buttons().find(b => b.textContent.trim() === label);
    byLabel('4')?.click();
    const display = document.querySelector('#display');
    const before = display?.value ?? null;
    if (label !== null) byLabel(label)?.click();
    const after = display?.value ?? null;
    const states = buttons().map(b => {
       const s=getComputedStyle(b);
       return [b.id,b.textContent.trim(),b.disabled,s.display,s.visibility,s.backgroundColor,s.gridColumn,s.position];
    });
    return {before, after, states, bg:getComputedStyle(document.body).backgroundColor};
   }, key);
   result[JSON.stringify(key)]={...obs,errors};
   await page.close();
  }
  process.stdout.write(JSON.stringify(result));
 } finally {await browser.close();}
})().catch(err=>{console.error(err);process.exit(1)});
"""
    with browser.serve("calculator", page) as url:
        output = subprocess.check_output(["node", "-e", script, str(runtime / "node_modules/@playwright/test"),
                                          url, json.dumps(labels)], env=browser_env(), timeout=120)
    return json.loads(output)


def run():
    freeze()
    seal = read(OUT / "generation-seal.json")
    for name, digest in seal["files_sha256"].items():
        if sha(OUT / name) != digest:
            raise ValueError(f"Sealed file changed: {name}")
    public = read(OUT / "public.json")
    rows = []
    for tag in SEEDS:
        pkg = read(OUT / "builds" / tag / "library.json")
        page = OUT / "probe" / tag / "components"
        html = assemble(public["starter"]["index.html"], pkg["actions"], pkg["panels"], "")
        manifest = core.emit("calculator", {"index.html": html}, page)
        endpoint = {"page": str(page.relative_to(ROOT)), "files": manifest}
        rows.extend(row(task, "fixed-components", tag, endpoint) for task in TASKS)
        endpoints = {"components": endpoint} | read(OUT / "builds" / tag / "endpoints.json")
        for name, value in endpoints.items():
            target = OUT / "probe" / tag / f"observed-{name}.json"
            if not target.exists():
                obs = observe(ROOT / value["page"], list(pkg["actions"]))
                core.save(target, {"files": value["files"], "observations": obs})
    core.save(OUT / "probe" / "seal.json", {"rows": rows, "generation": sha(OUT / "generation-seal.json")})
    protocol = browser.verify_contract("calculator")
    scores = browser.evaluate(rows, OUT, {"calculator": protocol}, 3)
    core.save(OUT / "probe" / "scores.json", {"rows": scores, "seal": sha(OUT / "probe" / "seal.json")})


if __name__ == "__main__":
    {"freeze": freeze, "run": run}[sys.argv[1]]()
