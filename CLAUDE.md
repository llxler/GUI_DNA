# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

Key points from AGENTS.md (full details there):

- Install: `uv sync --extra dev && uv run playwright install chromium`. Tests: `uv run pytest -q` (40 tests, real Chromium, ~1 min); single test: `uv run pytest tests/test_scale_study.py::<name> -q`.
- Three experiment generations coexist: v1 `src/gui_dna/`, v2 `src/gui_dna/followup/`, v3 `experiments/scale_study/` (current mainline: LLM emits a JSON wiring plan → `compile_plan` statically checks it → frozen function bodies are stitched → Playwright evaluates DOM + state against an oracle that never enters prompts).
- Frozen by the round-3 manifest: `experiments/scale_study/*.py`, `src/gui_dna/**`, `configs/scale-study.json`. Do not edit them; start a new directory/config for new experiments.
- `artifacts/budget.sqlite3` is the single paid-call ledger (cap $9, stop $8.8, currently `halted=1` = manual pause). Never delete/reset it; use a separate `Ledger` for small probes. Every paid call needs `OPENROUTER_API_KEY` from the environment and the user's explicit go-ahead.
- External benchmark comparisons live under `test/` (an experiment directory; `tests/` is the pytest suite): `test/webapp1k_dna/` (WebApp1K-Duo, no gain), `test/todomvc_dna/` (TodoMVC spec + official Playwright tests) and `test/webbench_dna/` (Web-Bench dom1, official specs verbatim; the clearest gain on weak models). Each has its own ledger.
- Docs: `README.md` (install + idea), `实验结果.md` (the only results doc; append new rounds there), written in Chinese.
- Paper: `DNA_latex/` (local only, gitignored — never commit it; English ICML 2027 draft; `main.tex` + `preamble.tex` + `custom.bib`). Every number must trace to `实验结果.md` / result files; open items are marked `\TODO{}` / `\TBD` / `\figplaceholder{}`.
