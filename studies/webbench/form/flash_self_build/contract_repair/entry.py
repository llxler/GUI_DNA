"""Place a model-authored ES module in its actual public starter entry, byte for byte."""
import argparse
from copy import deepcopy
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import re
from unittest.mock import patch

from studies.study_io import ROOT, now, read, sha
from ..run import core, browser, original
from . import run as targeted
from . import subset

TAG = "contract-entry-b"
OUT = targeted.batch.OUT / TAG
HERE = Path(__file__).resolve().parent


class ModuleTags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "script" and data.get("type") == "module" and data.get("src"):
            self.entries.append(data["src"].removeprefix("./"))


def hash_text(s):
    return sha256(s.encode()).hexdigest()


def relocate(public, raw):
    result = deepcopy(raw)
    scripts = ModuleTags()
    scripts.feed(public["starter"]["index.html"])
    assert len(scripts.entries) == 1
    entry = scripts.entries[0]
    assert entry in public["starter"] and entry not in {f["path"] for f in raw["files"]}
    js = result["script"]
    assert re.search(r"(?m)^\s*import\s+(?!\()", js)
    prefix = public["starter"][entry]
    source = prefix + "\n" + js
    result["files"].append({"path": entry, "content": source})
    result["script"] = ""
    offset = len(prefix.encode()) + 1
    assert source.encode()[:offset-1] == prefix.encode() and source.encode()[offset:] == js.encode()
    assert {**result, "script": js, "files": result["files"][:-1]} == raw
    proof = {"path": entry, "starter_sha256": hash_text(prefix), "source_sha256": hash_text(js),
             "module_offset_bytes": offset, "module_source_bytes": len(js.encode()),
             "relocated_slice_sha256": sha256(source.encode()[offset:]).hexdigest(),
             "combined_sha256": hash_text(source), "other_files_sha256":
                 {f["path"]: hash_text(f["content"]) for f in raw["files"]}}
    return result, proof


def register():
    paths = [HERE / "entry.md", Path(__file__), Path(subset.__file__), Path(targeted.__file__),
             subset.OUT / "registration.json", subset.OUT / "seal.json",
             subset.OUT / "form/build/corrected-raw.json", subset.OUT / "form/build/status.json",
             targeted.A_SEAL, targeted.B_SEAL, targeted.LAST, targeted.batch.OUT / "inputs/form/public.json",
             Path(targeted.batch.__file__), Path(original.__file__), Path(core.__file__), Path(browser.__file__)]
    item = {"model": targeted.batch.MODEL, "scheduled": list(targeted.TASKS),
            "files": {str(p.relative_to(ROOT)): sha(p) for p in paths},
            "shared_cap_usd": targeted.batch.CAP, "deadline": targeted.batch.END.isoformat()}
    dest = OUT / "registration.json"
    if not dest.exists():
        assert not list((targeted.batch.OUT / "browser/scores").glob("**/score.json")), "Scores already available"
        assert "Cannot use import statement outside a module" in read(subset.OUT / "form/build/status.json")["reason"]
        core.save(dest, {"utc": now(), **item})
    assert all(read(dest)[k] == v for k,v in item.items())


def build(_ledger):
    dest = OUT / "form/build"
    status = dest / "status.json"
    if status.exists():
        return read(status)
    public = read(targeted.batch.OUT / "inputs/form/public.json")
    raw = read(subset.OUT / "form/build/corrected-raw.json")
    relocated, proof = relocate(public, raw)
    core.save(dest / "relocated-raw.json", relocated)
    core.save(dest / "relocation.json", proof)
    try:
        pkg = core.package(public, original.normalized(deepcopy(relocated)))
        for name, plan in (("default", pkg["defaults"]), ("first", pkg["examples"][0]["plan"])):
            dest_page = dest / name
            core.materialize("form", pkg, plan, dest_page)
            errors = browser.public_load("form", dest_page)
            core.save(dest / (name + "-public.json"), errors)
            if errors:
                raise ValueError(str(errors)[:1200])
        core.save(dest / "package.json", pkg)
        state = {"status": "valid", "package_sha256": sha(dest / "package.json"),
                 "fixed": str((dest / "first").relative_to(ROOT))}
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        state = {"status": "build_failed", "reason": f"{type(exc).__name__}: {exc}"}
    core.save(status, state)
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["register", "generate"])
    action = parser.parse_args().action
    if action == "register":
        register()
    else:
        with patch.multiple(targeted, TAG=TAG, OUT=OUT, build=build, register=register):
            targeted.generate()
