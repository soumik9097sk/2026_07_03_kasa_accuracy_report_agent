# CLAUDE.md

This file is auto-loaded into context for every Claude Code session in this repo. See
`README.md` for the full human-facing writeup — this file is the condensed, "don't repeat
past mistakes" version.

## What this project is

An agentic pipeline that turns a free-text question ("why is AMAZON doing bad in May 2026")
into a data-grounded root-cause report, optionally rendered as a PowerPoint slide. The code
is an installable src-layout package under `src/kasa_agent/`. Entry points:
`kasa-report "<query>" [--json] [--ppt]` (console script, from `pip install -e .`), or
`python3 main.py ...` — the root `main.py` is a compat shim that adds `src/` to `sys.path`.

Pipeline (paths relative to `src/kasa_agent/`): `agents/planner_agent.py` (Gemini extracts
intent → builds a declarative `PlanStep` list) → `agents/analyst_agent.py` (`execute_plan`
runs it against real data, `synthesize_reasons` does rule-based root-cause classification,
then Gemini writes the narrative) → `services/chart_services.py` (bar chart) →
`agents/ppt_agent.py` (slide).

`PlanStep.module` strings must be fully qualified (`kasa_agent.analyzers.…`) — the analyst
resolves them with `importlib.import_module`, so a bare `analyzers.…` string will fail on
an installed copy. Data/output paths come from `config.py` and are overridable via
`KASA_DATA_DIR`, `KASA_OUTPUT_DIR`, `KASA_DATAMART_FILE`, `KASA_FORECAST_FILE` (used by the
Dockerfile, which mounts `data/` rather than baking it in).

## Before touching data logic, read this

1. **The datamart's real `POS_UNIT` (sales) data has a cutoff (~2025-11-01 in
   `amazon_all.csv`).** Rows after that are forward-looking placeholder rows for inference —
   `POS_UNIT` is `0`, but price/promo/discount/holiday features *are* real into 2026.
   `analyst_agent._pos_unit_cutoff()` detects this and clips trend/seasonality windows to it
   via `PlanStep.pos_unit_bounded`. **Don't** assume a `POS_UNIT` value near the report month
   is real without checking it's before the cutoff — this caused a real bug (all 5 worst
   keys spuriously flagged "possibly delisted") before the clipping was added.
2. **`-999` in `MAP` / `PMAP/MAP` / `DISCOUNT_DEPTH` means missing data**, not a real
   price/discount of negative 999. Always filter it before summing/averaging those columns
   (see `promotions.py`). Forgetting this produced a bogus "price decreased by $1039" before
   it was fixed.
3. **The forecast Excel's `Actuals` column is only filled for months that already
   happened.** A future month (e.g. June 2026 when "now" is July 2026) will have `NaN`
   actuals — that's correct, not a bug; accuracy functions return `NaN`/empty gracefully.
4. **`config.py`'s `datamart_columns`/`forecast_columns` dicts are the only place column
   names should be hardcoded.** The datamart and forecast files use completely different
   naming schemes for the same concepts (e.g. `POS_UNIT` vs `POS`, `D0GPRODFAM_T` vs
   `Global Product Family`, `MONTH_NUMBER` vs `Month`). Never hardcode a raw column name in
   an analyzer/repository — go through `self.cols[...]`.
5. There's a stale, broken CSV in `data/` (`DATAMART_FILLNA_..._part_12d.csv`) — a
   header-less mid-file chunk from an earlier incomplete LFS push. `config.py` no longer
   points to it (`amazon_all.csv` is the real datamart now). Don't resurrect it without
   checking it actually has a header row.

## Environment

- venv at `.venv/`, not committed. Install with `pip install -r requirements.txt`
  (pinned, verified versions) then `pip install -e .` for the `kasa-report` CLI.
  Dependency ranges also live in `pyproject.toml` — keep the two in sync.
- `.env` needs `GEMINI_API_KEY="..."` — **no spaces around `=`**, or `python-dotenv` loads
  it under the wrong key and every LLM call fails with a confusing "key not set" error.
- **pandas is pinned below 3.0.** pandas 3.0 changed `groupby().apply()`'s default handling
  of the grouping column and broke `calculate_top5_worse_keys` (`KeyError` on the key
  column). That function was rewritten to iterate `groupby()` directly instead of using
  `.apply()`, removing the dependency — but this hasn't been verified against pandas 3.x, so
  don't casually bump the pin without retesting.
- Data files (`data/*.xlsx`, `data/*.csv`) are Git LFS-tracked. If you see tiny pointer
  files instead of real data, the fix is `git lfs install && git lfs pull`, not re-fetching
  the repo.

## Conventions established in this codebase

- **Plan/execute split**: the planner builds a data-only, declarative list of `PlanStep`
  (what function to call, on which repository, with what args, with `for_each` fan-out for
  per-key drill-down) — it does *not* execute anything. `analyst_agent.execute_plan` is the
  only thing that actually calls analyzer/repository functions. Keep this separation when
  extending the pipeline; don't have the planner reach into data.
- **Root-cause reasons are rule-based, not LLM-guessed.** `_classify_key_reasons` computes
  real numbers (trend averages, YoY price deltas, etc.) and only then hands the *already
  computed* structured findings to Gemini for prose (`generate_narrative`). The LLM is
  explicitly instructed not to invent numbers not present in the JSON. Keep new
  root-cause logic in this same style — compute first, narrate second.
- **Bias direction (over/under-forecast)** isn't derivable from MAPE/MAE/WMAPE/SMAPE alone
  (all absolute-error metrics) — it's computed separately in `analyst_agent._pull_bias` from
  raw forecast/actual totals.
- Repository methods that are compound (e.g. `get_forecast_retailer_category`) were added
  next to the single-dimension methods they mirror, not as a generic filter system — that
  matches the existing one-method-per-combination pattern already in this codebase. Follow
  the same pattern if adding another compound dimension (e.g. retailer+SKU).
- PPT/chart output goes to `output/` (gitignored), filename
  `<entity>_<year>_<month>_<timestamp>.pptx`, one slide per file — never appended to an
  existing presentation.

## Known gaps (see README.md for the full list)

- Retailer+SKU / retailer+key compound scoping isn't implemented (only retailer+category
  is) — same class of bug as the one fixed for category could recur there.
- Several `DatamartRepository` methods (`get_sku_history`, `get_key_history`,
  `get_discount_history`, `get_inventory_history`, `get_holiday_history`,
  `get_feature_history`) have pre-existing filter bugs (comparing the column *name* string
  instead of its values). Unused by the current pipeline, so left alone — fix before wiring
  them in.
