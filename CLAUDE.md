# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

Key points from AGENTS.md (full details there):

- Install: `uv sync --extra dev && uv run playwright install chromium`. Tests: `uv run pytest -q` (40 tests, real Chromium, ~1 min); single test: `uv run pytest tests/test_scale_study.py::<name> -q`.
- Three experiment generations coexist: v1 `src/gui_dna/`, v2 `src/gui_dna/followup/`, v3 `experiments/scale_study/` (current mainline: LLM emits a JSON wiring plan → `compile_plan` statically checks it → frozen function bodies are stitched → Playwright evaluates DOM + state against an oracle that never enters prompts).
- Frozen by the round-3 manifest: `experiments/scale_study/*.py`, `src/gui_dna/**`, `configs/scale-study.json`. Do not edit them; start a new directory/config for new experiments.
- `artifacts/budget.sqlite3` is the single paid-call ledger (cap $9, stop $8.8, currently `halted=1` = manual pause). Never delete/reset it; use a separate `Ledger` for small probes. Every paid call needs `OPENROUTER_API_KEY` from the environment and the user's explicit go-ahead.
- Docs: `README.md` (install + idea), `实验结果.md` (the only results doc; append new rounds there), written in Chinese.
