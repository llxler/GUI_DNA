"""Recompute drag lengths after allowing a translation of both rendered endpoints."""
import argparse
import math

from studies.study_io import ROOT, dump, read, sha

from .run import OUT, PUBLIC, TOLERANCE, mode

OUTPUT = ROOT / "studies/results/draw-pointer-length-20261123.json"


def measure(rows):
    def horizontal(row, size):
        if row["status"] != "line":
            return False
        a, b = row["start"], row["end"]
        return math.hypot(abs(b[0] - a[0]) - size, b[1] - a[1]) <= TOLERANCE
    if not all(horizontal(row, 18) for row in rows["18"]):
        return "long control unavailable"
    short = rows["3"]
    if all(horizontal(row, 3) for row in short):
        return "release displacement"
    if all(row["status"] == "line" and abs(math.dist(row["end"], row["start"]) - 9) <= TOLERANCE for row in short):
        return "minimum length"
    return "other or unavailable"


def reconstruct():
    main = read(PUBLIC)
    measurements, states = {}, {}
    for key, ref in main["measurement_receipts"].items():
        filename = OUT / "measurements" / (ref["digest"] + ".json")
        assert sha(filename) == ref["raw_sha256"]
        raw = read(filename)["rows"]
        assert mode(raw) == main["by_page"][key]
        states[key] = measure(raw)
        if key.startswith("candidate/") or key.startswith("control/"):
            measurements[key] = {"strict": main["by_page"][key], "relative": states[key], "raw": raw}
    for key in main["by_page"].keys() - states.keys():
        assert main["by_page"][key] == "invalid saved response"
        states[key] = "invalid saved response"
    pairs = {}
    for name in main["pairs"]:
        early, late = (states[f"candidate/{name}/task-{t}"] for t in (8, 12))
        pairs[name] = {"task_8": early, "task_12": late,
                       "length_goals_met": int(early == "release displacement") + int(late == "minimum length")}
    settings = [v for k, v in states.items() if k.startswith("setting/")]
    return {"project": "draw", "post_hoc": True, "new_browser_runs": 0, "new_api_calls": 0,
            "reason": "Both direct GPT-OSS pages drew lines, but missed the preregistered absolute location in the long-drag control.",
            "rule": "Ignore common translation of both endpoints; retain 0.6 tolerance, an 18-unit horizontal positive control, both repeats and all pages. The early goal is 3 units horizontally; the later goal is length 9.",
            "primary_sha256": sha(PUBLIC), "analysis_sha256": sha(__file__), "settings": {k: settings.count(k) for k in sorted(set(settings))},
            "pairs": pairs, "workflow_and_control_measurements": measurements}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    values = reconstruct()
    if args.write and not OUTPUT.exists():
        dump(OUTPUT, values)
    assert values == read(OUTPUT)
    print(values["settings"], values["pairs"])
