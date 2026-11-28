"""Acquire integrity-pinned upstream packages and build without bundling another React."""
import base64
import hashlib
from functools import lru_cache
import json
from pathlib import Path
import subprocess
import tarfile
from urllib.request import urlopen
from experiments.webapp1k_probe import STAGING
from studies.study_io import sha
from .. import prepare as p

HERE=Path(__file__).resolve().parent
OUT=p.ART/"duo-form-sdk-20261128"
PKGS={"final-form":("5.0.0","HByosvP7x3N4bWTCPoBeUeoMatadewRifxaH3qhCQI2DBwFNO0m5wxETLVUXNGWz2yokdSCMdJEvtjfZoXnqDA=="),
      "react-final-form":("7.0.0","aEeAWbSsCLVXa4GBkJtjjyhPyX4L/Pgp5P/jXZwdz0YYcK6Zs/0PkgB+qWMSyIsbbGGE7m9yYlSpui5E5Gx26A==")}


def setup():
    folder=OUT/"sdk"
    sources={}
    for name,(version,expected) in PKGS.items():
        filename=f"{name}-{version}.tgz"
        raw=OUT/"packages"/filename
        if not raw.exists():
            raw.parent.mkdir(parents=True,exist_ok=True)
            with urlopen(f"https://registry.npmjs.org/{name}/-/{filename}",timeout=30) as r:
                raw.write_bytes(r.read())
        assert base64.b64encode(hashlib.sha512(raw.read_bytes()).digest()).decode()==expected
        dest=folder/"node_modules"/name
        dest.mkdir(parents=True,exist_ok=True)
        with tarfile.open(raw) as archive:
            for entry in archive:
                path=Path(entry.name)
                if not entry.isfile():continue
                assert path.parts[0]=="package" and ".." not in path.parts
                out=dest/Path(*path.parts[1:])
                out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(archive.extractfile(entry).read())
        meta=json.loads((dest/"package.json").read_text())
        sources[name]=dict(version=version,sha512=expected,license=meta.get("license"),upstream=meta.get("repository"),
                           archive_sha256=sha(raw))
    subprocess.run(["node",str(HERE/"bundle.cjs"),str(folder),str(STAGING)],check=True)
    p.save(OUT/"sdk-receipt.json",dict(packages=sources,bundle=sha(folder/"form-sdk.js"),tool=sha(HERE/"bundle.cjs")))


@lru_cache(maxsize=1)
def prefix():
    bundle=(OUT/"sdk/form-sdk.js").read_text()
    return ("import React from 'react';\n const sdkBox={exports:{}};\n(function(module,exports,require){\n"
            +bundle+"\n})(sdkBox,sdkBox.exports, name=>{if(name==='react')return React;throw Error(name);});\nconst sdk=sdkBox.exports;\n")


def source(config):
    raw=(HERE/"host.jsx").read_text()
    assert raw.count("__FEATURE_CONFIG__")==1
    return prefix()+raw.replace("__FEATURE_CONFIG__",json.dumps(config,ensure_ascii=False))


if __name__=="__main__":setup()
