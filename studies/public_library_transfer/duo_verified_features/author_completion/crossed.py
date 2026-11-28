"""Hold the new feature choices fixed and restore the previous, sealed model libraries."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from studies.study_io import read, sha, digest
from .. import prepare as p
from ..resource_routes import run as prior
from . import run as new

OUT=new.OUT/"crossed"
RESULT=new.HERE/"same-choices.json"


def run():
    new_seal=new.OUT/"candidates.json"
    old_libs=prior.OUT/"library-seal.json"
    assert all(sha(p.ROOT/f)==v for f,v in read(old_libs)["features"].items())
    sealed=read(new_seal)
    tasks=p.ORIGINAL.inputs()
    records={}
    files={}
    for tag,model in p.MODELS.items():
        rows=records[model]=[]
        for task,target in sealed["candidates"][model].items():
            group=tasks[task]["group"]
            choice=target["choice"]
            for arm,key in (("self",tag),("gpt5-library","gpt5")):
                components={n:read(prior.OUT/"features"/key/group/(n+".json"))["selected"] for n in p.FEATURES[group]}
                rec=dict(task=task,arm=arm)
                rows.append(rec)
                if not any(s and s["public"]["passed"] for s in components.values()):
                    rec["status"]="build_failed"
                    continue
                if choice["status"]!="valid":
                    rec["status"]=choice["status"]
                    continue
                names=[n for n in dict.fromkeys(choice["names"]) if components[n]]
                slots=names+["NONE","NONE"]
                bundle=p.donor.components.bundle(tasks[task]["public"]["module"],
                     dict(components=[dict(id=n,source=components[n]["source"]) for n in names]),dict(first=slots[0],second=slots[1]))
                key=digest(bundle)
                rec.update(status="valid",files=key)
                dest=OUT/"pages"/(key+".json")
                if key not in files:
                    p.save(dest,bundle)
                    files[key]=sha(dest)
    candidate_seal=OUT/"seal.json"
    p.save(candidate_seal,dict(previous=sha(old_libs),choices=sha(new_seal),models=records,files=files))
    jobs=defaultdict(list)
    for rows in records.values():
        for rec in rows:
            if rec["status"]=="valid":jobs[rec["task"],rec["files"]].append(rec)
            else:rec["passed"]=False if rec["status"]=="invalid" else None
    def grade(job):
        (n,key),rs=job
        old=prior.OUT/"scores"/n/key
        folder=old if (old/"verdict.json").exists() else OUT/"scores"/n/key
        f=OUT/"pages"/(key+".json")
        assert sha(f)==files[key]
        if folder==old:
            assert sha(prior.OUT/"pages"/(key+".json"))==sha(f)
        v=p.runtime.score((tasks[n]["group"],tasks[n],read(f),folder,None))
        assert v["report_sha256"]==sha(folder/"jest.json")
        for rec in rs:
            rec.update(passed=v["passed"],report_sha256=v["report_sha256"],cases=v["assertion_statuses"].count("passed"))
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(grade,jobs.items()))
    p.save(RESULT,dict(choices=sha(new_seal),library=sha(old_libs),seal=sha(candidate_seal),models=records,new_api_calls=0))


if __name__=="__main__":run()
