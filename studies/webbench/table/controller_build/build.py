"""Independently build two fresh libraries from public requirements and starter only."""
import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from studies.interface_blind.core import public_check, write_files
from studies.study_io import ROOT, dump, now, read, sha
from studies.table_library_sources.core import starter
from studies.webbench_expand.core import compile_plan, requirements

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/public-controller-table-20261123"
MODEL = "gpt-6.2-astra"
ARMS = ("rep-1", "rep-2")
PROMPT = """Build a reusable browser-native table behavior library satisfying the supplied public requirements and compatible with the public starter. Define one to six semantic, independently selectable boolean controls. Choose their meaningful names, descriptions, defaults and a first example. Return a short design, a controls array with id/behavior/default, an example_enabled array listing exactly the switches on in your first example, and files as an array of path/content strings. Supply index.js, additive index.css, and reusable ES modules as needed. A generic compiler preserves the public starter HTML, adds your CSS after its stylesheet, then imports your implementation after globalThis.APP_CONFIG has been populated with your named boolean values including defaults. Implement both true and false settings. Use only the information in this prompt. No tools, reading files, external dependencies, task-specific dispatch, target identifiers in code, or edits to the starter HTML. Return complete working code in one response."""
def obj(props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}

string = {"type": "string"}
SCHEMA = obj({"design": string, "controls": {"type": "array", "items": obj({"id": string, "behavior": string, "default": {"type": "boolean"}})},
              "example_enabled": {"type": "array", "items": string},
              "files": {"type": "array", "items": obj({"path": string, "content": string})}})
COMPILER = """function compile(plan, files) {
  const cfg = Object.assign({}, JSON.parse(files['dna-defaults.json']), plan);
  return {...files, 'dna-config.js': 'globalThis.APP_CONFIG = '+JSON.stringify(cfg)+';',
          'dna-entry.js': files['index.js'], 'index.js': "import './dna-config.js';\\nimport './dna-entry.js';"};
}"""


def package(value, public):
    cs = value["controls"]
    if not 1 <= len(cs) <= 6 or not value["design"].strip():
        raise ValueError("Expected a nonempty design and one to six semantic switches")
    ids = [c["id"] for c in cs]
    if len(set(ids)) != len(ids) or any(not re.fullmatch("[A-Za-z][A-Za-z0-9_-]{0,63}", key) for key in ids):
        raise ValueError("Expected unique semantic switch names")
    if any(type(c["default"]) is not bool or not c["behavior"].strip() for c in cs):
        raise ValueError("Every switch needs a boolean default and description")
    first = value["example_enabled"]
    if len(set(first)) != len(first) or not set(first) <= set(ids):
        raise ValueError("Invalid enabled switches in first example")
    files = {x["path"]: x["content"] for x in value["files"]}
    if len(files) != len(value["files"]) or set(files) & {"index.html", "dna-config.js", "dna-entry.js", "dna-defaults.json"}:
        raise ValueError("Duplicate or reserved source path")
    if not files.get("index.js", "").strip() or "index.css" not in files:
        raise ValueError("Expected a JS entry and additive stylesheet")
    defaults = {c["id"]: c["default"] for c in cs}
    files = {**public["starter"], **files, "index.css": public["starter"]["index.css"]+"\n"+files["index.css"],
             "dna-defaults.json": json.dumps(defaults)}
    schema = {"type": "object", "properties": {key: {"type": "boolean"} for key in ids},
              "required": [], "additionalProperties": False}
    docs = "Omitted keys take the stated default.\n" + "\n".join(
        f"{c['id']} (default {str(c['default']).lower()}): {c['behavior']}" for c in cs)
    return {"design": value["design"], "files": files, "compiler": COMPILER, "plan_schema": schema,
            "plan_documentation": docs, "examples": [{"description": "First public configuration",
                                                       "plan": {key: key in first for key in ids}}]}


def generate(arm):
    d = OUT / arm
    status = {"status": "failed", "started": now(), "model": MODEL, "effort": "medium", "prompt_sha256": sha(d/"prompt.txt")}
    env = {k:v for k,v in os.environ.items() if k not in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "OPENAI_BASE_URL")}
    try:
        with tempfile.TemporaryDirectory(prefix="public-controller-builder-") as tmp, (d/"events.jsonl").open("w") as log, (d/"stderr.log").open("w") as err:
            command = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
                       "-C", tmp, "-s", "read-only", "-m", MODEL, "-c", 'model_reasoning_effort="medium"', "--json",
                       "--output-schema", str(OUT/"response-schema.json"), "-o", str(d/"reply.json"), "-"]
            subprocess.run(command, input=(d/"prompt.txt").read_text(), text=True, env=env, cwd=tmp,
                           stdout=log, stderr=err, timeout=570, check=True)
        events = [json.loads(line) for line in (d/"events.jsonl").read_text().splitlines() if line]
        sessions = [e["thread_id"] for e in events if e["type"] == "thread.started"]
        tools = [e["item"]["type"] for e in events if isinstance(e.get("item"),dict) and e["item"]["type"] not in ("agent_message","reasoning","plan")]
        status["usage"] = [e["usage"] for e in events if e["type"] == "turn.completed"]
        if len(sessions) != 1 or len(status["usage"]) != 1 or tools:
            raise ValueError("Unexpected tool use, session count, or usage")
        status["session"] = sessions[0]
        p = package(read(d/"reply.json"), read(OUT/"public.json"))
        for label, plan in (("empty", {}), ("first", p["examples"][0]["plan"])):
            page = d/"public-check"/label
            write_files(page, compile_plan(p, plan))
            errors = public_check(page)
            if errors:
                raise ValueError(str(errors))
        dump(d/"package.json", p)
        status.update(status="accepted", package_sha256=sha(d/"package.json"))
    except Exception as err:
        status["error"] = f"{type(err).__name__}: {err}"
    for filename in ("reply.json", "events.jsonl"):
        if (d/filename).exists():
            status[filename+"_sha256"] = sha(d/filename)
    status["finished"] = now()
    dump(d/"status.json", status)
    return arm,status


def main():
    if OUT.exists():
        raise ValueError("One-shot stage already exists")
    auth = read(Path.home()/".codex/auth.json")
    if auth.get("auth_mode") != "chatgpt" or auth.get("OPENAI_API_KEY"):
        raise ValueError("Use subscription authentication")
    public = {"requirements": requirements("table"), "starter": starter()}
    dump(OUT/"public.json", public)
    dump(OUT/"response-schema.json", SCHEMA)
    for name in ARMS:
        d=OUT/name
        d.mkdir()
        (d/"prompt.txt").write_text(PROMPT + "\n" + json.dumps(public,ensure_ascii=False))
    dump(OUT/"registered.json", {"registered": now(), "model": MODEL, "arms": list(ARMS),
         "protocol_sha256": sha(HERE/"PROTOCOL.md"), "builder_sha256": sha(Path(__file__)),
         "public_sha256": sha(OUT/"public.json"), "schema_sha256": sha(OUT/"response-schema.json"),
         "prompt_sha256": {a: sha(OUT/a/"prompt.txt") for a in ARMS}})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = dict(pool.map(generate,ARMS))
    dump(OUT/"sealed.json", {"sealed": now(), "status": results, "registered_sha256": sha(OUT/"registered.json")})
    print({a:r["status"] for a,r in results.items()})


if __name__ == "__main__":
    main()
