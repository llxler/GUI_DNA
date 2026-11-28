"""Audit the released source columns, a real router alternative, and fetch-mock URL semantics."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
from urllib.request import urlopen

from experiments.webapp1k_probe import REPO, STAGING
from studies.study_io import read, sha
from . import prepare as p
from .resource_routes import run as routes

REPO_COMMIT = "00895306c81d5329904827b65f4a933ce3cb8746"
HF_DATA = {
    "WebApp1K-React":"9ed6037a3b7021d43f37e54d918660398195bb9a",
    "WebApp1K-Duo-React":"7531b3a892b05a464c2fe4ccc8e002f5ed516eb9",
    "WebApp1K-React-Generations":"41a2605f5b9591f8e412a3d5e08755909789a2cc",
    "WebApp1K-Duo-React-Generations":p.donor.REVISION,
}
OUT=p.OUT/"source-and-harness"


def release(name):
    revision=HF_DATA[name]
    raw=OUT/(name+".json")
    if not raw.exists():
        url=f"https://huggingface.co/api/datasets/onekq-ai/{name}/revision/{revision}"
        with urlopen(url,timeout=35) as stream:
            p.save(raw,json.load(stream))
    info=read(raw)
    assert info["sha"]==revision
    schema=info.get("cardData",{}).get("dataset_info",{}).get("features")
    if schema:
        columns=[x["name"] for x in schema]
    else:
        binary=OUT/(name+".parquet")
        if not binary.exists():
            url=f"https://huggingface.co/datasets/onekq-ai/{name}/resolve/{revision}/dataset.parquet"
            with urlopen(url,timeout=60) as stream:
                binary.write_bytes(stream.read())
        import duckdb
        columns=[r[0] for r in duckdb.connect().execute("describe select * from read_parquet(?)",[str(binary)]).fetchall()]
    return dict(repository="onekq-ai/"+name, revision=revision, files=[x["rfilename"] for x in info["siblings"]],columns=columns)


def probe(tag, test, candidate=None):
    stage=OUT/tag
    stage.mkdir(parents=True,exist_ok=True)
    packages=stage/"node_modules"
    if not packages.exists(): packages.symlink_to(STAGING/"node_modules",target_is_directory=True)
    shutil.copyfile(STAGING/"package.json", stage/"package.json")
    src=stage/"src";src.mkdir(exist_ok=True)
    if candidate: (src/"ResourceEditor.js").write_text(candidate)
    spec=src/test.name
    shutil.copyfile(test,spec)
    report=stage/"jest.json"
    if not report.exists():
        import os
        env={k:v for k,v in os.environ.items() if not ("KEY" in k or "TOKEN" in k)}|{"CI":"true"}
        with (stage/"jest.log").open("w") as log:
            subprocess.run(["npm","test","--","--runInBand","--json",f"--outputFile={report}","--runTestsByPath",str(spec)],
                           cwd=stage,env=env,stdout=log,stderr=log,check=True,timeout=90)
    suite,=read(report)["testResults"]
    assert Path(suite["name"]).resolve()==spec and sha(spec)==sha(test)
    cases={c["title"]:c["status"] for c in suite["assertionResults"]}
    assert cases and all(v=="passed" for v in cases.values())
    return dict(test_sha256=sha(test),cases=cases,report_sha256=sha(report))


def run():
    assert subprocess.check_output(["git","-C",str(REPO),"rev-parse","HEAD"],text=True).strip()==REPO_COMMIT
    tree=subprocess.check_output(["git","-C",str(REPO),"ls-tree","-r","--name-only",REPO_COMMIT],text=True).splitlines()
    assert not any(f.startswith("staging/src/") for f in tree)
    js=[f for f in tree if f.endswith((".js",".jsx",".tsx")) and not f.endswith(".test.js")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        releases=dict(zip(HF_DATA,pool.map(release, HF_DATA),strict=True))
    for name,v in releases.items():
        assert not any("human" in s.lower() or "reference" in s.lower() for s in v["columns"])
        if name.endswith("Generations"): assert ("gpt-5" in v["columns"])==("Duo" in name)
    info=dict(upstream_commit=REPO_COMMIT, application_js_outside_tests=js, releases=releases,
              human_status="unavailable", human_reason="No attributable human feature implementation in the audited releases.",
              local_sanity="One local alternative-text smoke component, without documented human authorship.",
              runtime_version=read(STAGING/"node_modules/fetch-mock/package.json")["version"],
              harness=probe("query",p.HERE/"harness.test.js"))
    sel=read(routes.OUT/"features/deepseek-flash/blogging/editComment.json")["selected"]
    if sel and sel.get("route"):
        info["alternate_resource"]=dict(probe("route",routes.HERE/"alternate-id.test.js",sel["source"]),
                                         candidate_sha256=p.checksum(sel["source"]))
    else:
        info["alternate_resource"]=None
    p.save(p.HERE/"source-audit.json",info)


if __name__=="__main__":
    run()
