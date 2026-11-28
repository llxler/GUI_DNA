"""Compose matching pieces from the same author's already delivered public candidates."""

from datetime import datetime
from itertools import product
from pathlib import Path
from unittest.mock import patch
import json
import time

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as base
from ..event_routing import run as routing
from ..command_delivery import run as commands

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-self-core-recovery-20261128pm"
CAP = 1.50
PARENT = commands.OUT


def register():
    files = [Path(__file__), HERE/"PROTOCOL.md", Path(commands.__file__), Path(base.__file__),
             Path(routing.__file__), base.OUT/"seal.json", routing.OUT/"seal.json", commands.OUT/"registration.json"]
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in files}
    path = OUT/"registration.json"
    if not path.exists():
        exposure = sum(ledger_read.totals(p/"budget.sqlite3")["exposure_usd"] for p in (base.OUT,routing.OUT))
        assert exposure + commands.CAP + CAP <= 10 and read(OUT/"credits.json")["effective_remaining_usd"] >= CAP
        core.save(path,read(commands.OUT/"registration.json") | dict(utc=now(),cap=CAP,sources=hashes,closed_exposure=exposure))
    reg = read(path)
    assert reg["sources"] == hashes
    return reg


def cores(tag, filename):
    found = {}
    for stage in (PARENT,routing.OUT):
        for revision in ("assembled","repaired"):
            path = stage/"libraries"/tag/"core"/revision/"page/common"/filename
            if path.exists():
                found.setdefault(sha(path),path)
    return list(found.values())


def shell_for(menu):
    start = "  const items = "
    items = json.loads(menu.split(start,1)[1].split(";\n  const actions = ",1)[0])
    return routing.menu_source(items,{})


def prepare(tag,pub,ledger):
    dst = OUT/"libraries"/tag/"library.json"
    if dst.exists():
        return read(dst)
    root = dst.parent
    tables,menus = cores(tag,"table.js"),cores(tag,"menu.js")
    previous = PARENT/"libraries"/tag/"library.json"
    assert read(previous)["status"]=="build_failed"
    history = []
    parts = {}
    shell = None
    status = "build_failed"

    def probe(selector, menu, source, directory):
        trial = {"table":selector.read_text(),"menu":menu}
        observed = base.observe(pub,trial,directory)
        history.append(dict(step="core composition",selector=str(selector.relative_to(ROOT)),selector_sha256=sha(selector),
                            menu=source,public=observed,admitted=base.admitted(observed)))
        return trial,observed

    try:
        for i,(selector,menu) in enumerate(product(tables,menus)):
            parts,check = probe(selector,menu.read_text(),dict(file=str(menu.relative_to(ROOT)),sha256=sha(menu)),root/"pairs"/str(i))
            if base.admitted(check):
                status = "valid"
                break
        if status!="valid" and menus:
            menu = menus[0]
            original = menu.read_text()
            feedback = None
            for revision in (1,2):
                folder = root/"insert"/str(revision)
                request = dict(action="Insert a new tbody row just ABOVE row, with columns blank td cells.",
                               parameters="section is an actual HTMLTableSectionElement (tbody). row is its actual HTMLTableRowElement child. columns is an integer. Use the section's insertRow method with a SECTION-relative index and the returned row's insertCell method. Only section, row, columns exist. Do not register listeners, find other elements or create a menu.",
                               public_feedback=feedback)
                code = commands.short(tag,ledger,folder/"call","insertAbove","section,row,columns",request,54)
                replacement = ("  actions['menu-item-insert-row-above']=function(table,cell){const row=cell.parentElement;"
                               "return function(section,row,columns){\n"+code+"\n}(row.parentElement,row,row.cells.length);};\n")
                marker = "  let menu = null;"
                assert original.count(marker)==1
                revised = original.replace(marker,replacement+marker)
                for idx,selector in enumerate(tables):
                    parts,check = probe(selector,revised,dict(file=str(menu.relative_to(ROOT)),sha256=sha(menu),insert_revision=revision),
                                        folder/str(idx))
                    if base.admitted(check):
                        status = "valid"
                        break
                    feedback = check
                if status=="valid":
                    break
        if status=="valid":
            shell = shell_for(parts["menu"])
            parts,check = commands.keyboard(tag,pub,parts,check,ledger,root/"keys",history)
            for name in list(base.MODULES)[3:]:
                folder = root/"extensions"/name
                try:
                    proposal = parts | {name:base.author(tag,name,pub,ledger,folder/"answer",55)}
                    obs = base.observe(pub,proposal,folder)
                    keep = not obs["errors"] and base.passed(check)<=base.passed(obs)
                    history.append(dict(step=name,retained=keep,public=obs))
                    if keep:
                        parts,check = proposal,obs
                except ValueError as exc:
                    history.append(dict(step=name,retained=False,error=str(exc)))
    except (*base.MISSING,ValueError,KeyError,TypeError) as exc:
        history.append(dict(step="delivery",error=str(exc)))
        if status!="valid" and isinstance(exc,base.MISSING):
            status = "missing"
    profiles = []
    if status=="valid":
        for n in range(2,len(parts)+1):
            selected = dict(list(parts.items())[:n])
            obs = base.observe(pub,selected,root/"profiles"/str(n))
            profiles.append(dict(count=n,modules=list(selected),checks=sorted(base.passed(obs))))
    result = dict(status=status,parts=parts,profiles=profiles,shell=shell,history=history,changed=status=="valid",
                  parent_status="build_failed",parent_library=sha(previous))
    core.save(dst,result)
    print("Core recovery",tag,status,flush=True)
    return result


if __name__=="__main__":
    with browser.lock(OUT/"study.lock"):
        reg = register()
        while not (commands.OUT/"seal.json").exists():
            if datetime.now(base.timezone.utc)>=base.END:
                raise TimeoutError("Parent not sealed before deadline")
            time.sleep(3)
        eligible = {t:m for t,m in reg["models"].items() if read(commands.OUT/"libraries"/t/"library.json")["status"]=="build_failed"}
        if not eligible:
            raise SystemExit("All registered builds already admitted")
        selected = reg | {"models":eligible}
        if not (OUT/"seal.json").exists():
            parent = commands.OUT
            with patch.multiple(commands,OUT=OUT,SECOND=parent,CAP=CAP,prepare=prepare),patch.object(base,"TAGS",tuple(eligible)):
                commands.generate(selected)
        if not (HERE/"result.json").exists():
            with patch.multiple(base,OUT=OUT,HERE=HERE):
                base.score(selected)
