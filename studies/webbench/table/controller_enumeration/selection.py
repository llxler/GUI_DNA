"""Measure how many reference controllers the recorded Mistral selections enable."""
import argparse

from studies.study_io import ROOT, dump, read, sha

MATRIX = ROOT / "studies/results/table-controller-enumeration-20261123.json"
PLANS = ROOT / "studies/results/table-library-sources-20261123.json"
OUTPUT = ROOT / "studies/results/table-controller-selection-20261123.json"


def reconstruct():
    matrix, plans = read(MATRIX), read(PLANS)
    assert matrix["uniform"]["settled_positions"] == 64 * 20
    hashes = matrix["evidence"]["page_hashes_in_mask_order"]
    assert len(hashes) == len(set(hashes)) == 64
    mask_by_hash = {value: index for index, value in enumerate(hashes)}
    tasks = {}
    fixed = set(range(64))
    for task, scores in matrix["outcomes_by_task_in_mask_order"].items():
        assert len(scores) == 64 and all(type(x) is bool for x in scores)
        passing = {i for i, passed in enumerate(scores) if passed}
        fixed.intersection_update(passing)
        plan = plans["targets"][task]["reference"]["first"]
        chosen = mask_by_hash[plan["page_manifest_sha256"]]
        assert chosen in passing and plan["passed"] is True
        least = min(i.bit_count() for i in passing)
        submasks = [i for i in passing if i & chosen == i]
        tasks[task] = {"chosen_mask": chosen, "enabled": chosen.bit_count(), "file_minimum_enabled": least,
                       "minimum_within_chosen": min(i.bit_count() for i in submasks),
                       "one_switch_removable": any(i.bit_count() == chosen.bit_count() - 1 for i in submasks),
                       "page_manifest_sha256": hashes[chosen]}
    smallest_fixed = min(mask.bit_count() for mask in fixed)
    enabled = sum(row["enabled"] for row in tasks.values())
    return {"project": "table", "post_hoc": True, "new_browser_runs": 0, "new_model_calls": 0, "targets": tasks,
            "interpretation": "Counts enabled bindings on each page, conditional on its own current file. "
                              "All reference modules ship with each page. Counts do not measure bytes, runtime, or correctness on other requirements.",
            "summary": {"targets": len(tasks), "chosen_bindings": enabled, "mean_chosen": enabled / len(tasks),
                        "minimum_bindings_summed_over_files": sum(r["file_minimum_enabled"] for r in tasks.values()),
                        "chosen_globally_minimal_on_current_file": sum(r["enabled"] == r["file_minimum_enabled"] for r in tasks.values()),
                        "can_remove_one_from_chosen": sum(r["one_switch_removable"] for r in tasks.values()),
                        "chose_all_six": sum(r["enabled"] == 6 for r in tasks.values()),
                        "distinct_chosen_masks": len({r["chosen_mask"] for r in tasks.values()}),
                        "perfect_fixed_masks": sorted(fixed), "smallest_perfect_fixed_cardinality": smallest_fixed,
                        "bindings_with_smallest_perfect_fixed_mask": smallest_fixed * len(tasks)},
            "inputs": {str(p.relative_to(ROOT)): sha(p) for p in (MATRIX, PLANS)}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = reconstruct()
    if args.write and not OUTPUT.exists():
        dump(OUTPUT, value)
    assert value == read(OUTPUT)
    print(value["summary"])
