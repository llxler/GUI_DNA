"""Round-2 (follow-up) helper scripts: preload control, compact pair, summary, one-off 429 recovery.

Results are documented in 实验结果.md §3; these scripts only recompute them from local artifacts.
Run from the repository root, e.g. `uv run python -m experiments.round2.summarize_followup`.
`resume_compact.py` was a one-off recovery window (kept byte-identical to the recorded source hash); do not re-run it.
The post-hoc linker replay (`experiments/replay_linked_plans.py`, `experiments/plan_linker.py`) stays one level up:
its frozen manifest in artifacts/linked-plan-posthoc/ records those exact paths and hashes.
"""
