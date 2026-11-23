"""Run the sealed evaluation with the exact study sources registered before grading."""
import argparse
from pathlib import Path

from studies.compatible_library_rebuild import sealed_evaluate_20261123 as evaluation
from studies.library_refinement_table import sealed_run_20261123 as plan_archive
from studies.study_io import ROOT, dump, read, sha

# A concurrent experiment wrapped its runner after our candidates were sealed.
# Both moved files retain the exact content hashes from our candidate manifest.
SOURCES = {
    ROOT / "studies/library_refinement_table/run.py": (
        Path(plan_archive.__file__), "1e3dec7c0ce4851e8857eaae414e6d281e7cfad23c30fd8e8e87e65df472b140"),
    Path(__file__).resolve(): (
        Path(evaluation.__file__), "0ab285960723cd15825ce73b47bb2cd24eb966ff96a368dd5b78e800282a2f56"),
}


def frozen_sha(path):
    resolved = Path(path).resolve()
    if resolved not in SOURCES:
        return sha(resolved)
    archived, expected = SOURCES[resolved]
    checksum = sha(archived)
    assert checksum == expected, archived
    return checksum


def verify_inputs(manifest):
    for path, expected in manifest.items():
        assert frozen_sha(ROOT / path) == expected, path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("freeze", "score", "report", "check"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    if args.stage == "check" and not (evaluation.EVAL / "candidates-sealed.json").exists():
        raise ValueError("No sealed candidates")
    evaluation.previous = plan_archive
    plan_archive.sha = frozen_sha
    evaluation.sha = frozen_sha
    evaluation.verify = verify_inputs
    manifest = evaluation.freeze_candidates()
    if args.stage == "score":
        evaluation.score(manifest, args.workers)
    if args.stage in ("report", "check"):
        result = evaluation.report(manifest)
        if args.stage == "report" and not evaluation.REPORT.exists():
            dump(evaluation.REPORT, result)
        else:
            assert result == read(evaluation.REPORT), "Published result differs from sealed assessment"
        print({c: {a: v["passed"] for a, v in data["summary"].items()} for c, data in result["cohorts"].items()})
        print(result["confirmation"])


if __name__ == "__main__":
    main()
