# Kasa Accuracy Report Agent

An agentic system that answers questions like *"why is AMAZON doing bad in May 2026?"*
with a real, data-grounded root-cause report: forecast accuracy, per-key over/under-forecast
bias, trend/seasonality/promotion drivers, a YoY sales baseline, and (optionally) a
ready-to-present PowerPoint slide.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # pinned, verified versions
pip install -e .                  # installs the `kasa-report` CLI
```

Create `.env` in the project root (see `.env.example`):

```
GEMINI_API_KEY="your-key-here"
```

Data files (`data/*.xlsx`, `data/*.csv`) are tracked with **Git LFS**. If they show up as
tiny pointer files instead of real data, run `git lfs install && git lfs pull`.

## Usage

```bash
kasa-report "why is AMAZON doing bad in month 5 2026"
kasa-report --json "AMAZON 2026 month 5"              # full structured report
kasa-report --ppt  "AMAZON Stand Mixers category 2026 month 5"  # also builds a slide
```

`python3 main.py "<query>"` still works from a source checkout without installing —
`main.py` is a thin shim over `src/kasa_agent/cli.py`.

## Project layout

```
pyproject.toml            packaging + `kasa-report` console script
requirements.txt          pinned dependency versions
Dockerfile / .dockerignore  container deployment (data mounted at runtime)
main.py                   backwards-compatible shim over the packaged CLI
src/kasa_agent/           the installable package
  cli.py                  argument parsing, data loading, entry point
  config.py               column-name indirection + env-overridable paths
  agents/                 planner, analyst, ppt agents
  analyzers/              trend, seasonality, promotions, accuracy metrics
  repositories/           forecast Excel + datamart CSV access
  services/               chart + summary services
data/                     Git LFS-tracked input files
legacy/                   pre-pipeline scratch scripts (not part of the package)
output/                   generated charts/slides (gitignored)
```

### Configuration (env vars)

- `GEMINI_API_KEY` (required) — loaded from `.env` via python-dotenv.
- `KASA_DATA_DIR` — where the input files live (default: `<project-root>/data`).
- `KASA_OUTPUT_DIR` — where slides/charts are written (default: `<project-root>/output`).
- `KASA_DATAMART_FILE` / `KASA_FORECAST_FILE` — full-path overrides for the two
  input files (take precedence over `KASA_DATA_DIR`).

### Docker

```bash
docker build -t kasa-report .
docker run --rm --env-file .env \
  -v "$PWD/data:/app/data" -v "$PWD/output:/app/output" \
  kasa-report --ppt "AMAZON 2026 month 5"
```

The image deliberately does **not** bake in `data/` (large, LFS-tracked) — mount it.

Supported query shapes:
- Retailer: `"AMAZON 2026 month 5"`
- Category: `"Stand Mixers category 2026 month 5"` (across all retailers)
- Retailer + category: `"AMAZON Stand Mixers category 2026 month 5"` (category scoped to one retailer)
- SKU / Key: analogous, via `level="sku"` / `level="key"`

If the query is missing a field (level, identifier, year, month), the agent returns a
clarification question instead of guessing.

## Architecture

All module paths below are relative to `src/kasa_agent/`.

```
query (free text)
   │
   ▼
agents/planner_agent.py    -- Gemini extracts {level, identifier, year, month, retailer?}
   │                          -- builds a declarative list of PlanStep (what to fetch, from
   │                             which repository, in what order, with what fan-out)
   ▼
agents/analyst_agent.py    -- execute_plan(): walks the PlanStep list, resolves fan-out
   │                             over the worst 5 keys, clips date ranges to real data
   │                          -- synthesize_reasons(): rule-based root-cause classification
   │                             + YoY sales baseline, then a Gemini-written narrative
   ▼
services/chart_services.py -- actual vs forecast bar chart (matplotlib) for the worst keys
   ▼
agents/ppt_agent.py        -- single-slide PPTX: heading + bullet reasons + the chart
```

### Data layer

- `repositories/forecast_repository.py` (`ForecastRepository`) — wraps the forecast Excel.
  Per-level getters (`get_forecast_retailer`, `get_forecast_category`, `get_forecast_sku`,
  `get_forecast_key`, `get_forecast_retailer_category`) and their `get_actual_*` counterparts.
- `repositories/datamart_repository.py` (`DatamartRepository`) — wraps the datamart CSV.
  Per-level getters (`get_retailer`, `get_category`, `get_sku`, `get_key`,
  `get_retailer_category`) plus some legacy stub methods (see **Known issues** below).
- `config.py` — all column-name indirection lives here (`datamart_columns`,
  `forecast_columns`), plus `data_paths` for the two data files. Paths default to
  `<project-root>/data` and `<project-root>/output` but are overridable via the
  `KASA_*` env vars listed above, so a deployed install can point anywhere.

### Analysis layer (`analyzers/`)

- `trend.py` — `TrendAnalyzer`: sales trend, growth rate, moving average, peak week.
- `seasonality.py` — `SeasonalityAnalyzer`: monthly seasonality profile, peak/lowest month.
- `promotions.py` — `PromoAnalyzer`: promo price / price / discount trend, plus a
  52-week-lag year-over-year comparison. Returns both the trend *label* (`"higher"/"lower"`)
  and the actual *values* (`first_value`, `last_value`, `current_avg`, `previous_avg`) so
  downstream text can state real numbers, not just directions.
- `forecast_analyzer_main.py` — MAPE / MAE / WMAPE / SMAPE, and `calculate_top5_worse_keys`.
- `analyzer_main.py` — orchestration: `get_forecast_{retailer,category,sku,key,
  retailer_category}_accuracy`, plus the `get_*_sales_trend` family.

### Services (`services/`)

- `summary_services.py` — `SummaryService`: retailer/category contribution stats
  (pre-existing, not currently wired into the agent pipeline).
- `chart_services.py` — `generate_actual_vs_forecast_chart(key_findings, title, save_path)`:
  grouped bar chart, one pair of bars (Actual / Forecast) per key.
  `generate_chart_from_report(report, save_path)` is a convenience wrapper that builds the
  title from the report's entity/year/month.

### Agents (`agents/`)

- `planner_agent.py` — `AnalysisRequest` data model, Gemini-based `extract_analysis_request`,
  `validate_request` (clarification questions), `create_plan` (builds the `PlanStep` list).
- `analyst_agent.py` — `execute_plan`, root-cause rules (`_classify_key_reasons`), YoY sales
  baseline (`_yoy_sales_comparison`), narrative generation, and the top-level
  `generate_accuracy_report(query, forecast_df, datamart_df)`.
- `ppt_agent.py` — `generate_findings_slide(report, ...)`: one slide, heading built from the
  report (e.g. *"AMAZON STAND MIXERS 2026 MONTH 5 FINDINGS"*), left half = per-key bullets,
  right half = the chart. Saves to `output/<entity>_<year>_<month>_<timestamp>.pptx`
  (gitignored) by default.

## Critical data caveats

These are not bugs — they're real properties of the current data files that the code
already accounts for, but any future change should keep in mind:

1. **The datamart's real sales history has a cutoff.** `amazon_all.csv` only has genuine
   `POS_UNIT` (actual sales) data through roughly **2025-11-01**. Rows dated after that are
   forward-looking placeholder rows generated for inference — `POS_UNIT` is filled with
   `0`, but other features (price, promo, discount, holidays, Fourier terms, macro
   indicators) *are* populated all the way into 2026. `analyst_agent._pos_unit_cutoff()`
   auto-detects this cutoff and clips trend/seasonality windows to it
   (`PlanStep.pos_unit_bounded`); promotion analysis is deliberately **not** clipped, since
   those features stay valid.
2. **`-999` is a missing-data sentinel**, not a real value, in `MAP`, `PMAP/MAP`, and
   `DISCOUNT_DEPTH`. It's filtered out (treated as NaN) throughout `promotions.py` and in
   the cutoff detection. Don't sum/average these columns without excluding it.
3. **The forecast Excel's `Actuals` column is only populated for months that have already
   happened.** E.g. June 2026 actuals are all `NaN` — accuracy metrics correctly return
   `NaN`/empty for that month rather than crash; that's expected, not a bug.
4. `data/DATAMART_FILLNA_3268_KEYS_ALL_FAMILIES_TILL_DEC_2026_20th_Nov_v1_part_12d.csv` is a
   **stale, broken artifact** from an earlier incomplete Git LFS push (a mid-file chunk with
   no header row — its "columns" are literal data values). It's still in `data/` but
   `config.py` no longer references it; `amazon_all.csv` superseded it.

## Environment notes

- **pandas is pinned below 3.0** (currently 2.3.3). pandas 3.0 changed
  `groupby().apply()`'s default handling of the grouping column, which broke
  `calculate_top5_worse_keys`. Most of that function was since rewritten to iterate
  `groupby()` directly instead of using `.apply()`, so it no longer depends on this
  behavior — but this hasn't been re-tested against pandas 3.x.
- `GEMINI_API_KEY` must be in `.env` with no stray whitespace around `=`
  (`GEMINI_API_KEY="..."`, not `GEMINI_API_KEY = "..."`) or `python-dotenv` will load it
  under the wrong key name.

## Known gaps / possible follow-ups

- Retailer+category compound scoping is supported; retailer+SKU or retailer+key is not —
  the same "silently drops the retailer filter" bug that was fixed for category could exist
  there too if someone asks for it.
- Several `DatamartRepository` methods (`get_sku_history`, `get_key_history`,
  `get_discount_history`, `get_inventory_history`, `get_holiday_history`,
  `get_feature_history`) have pre-existing bugs — they compare `self.cols["X"]` (the column
  *name* string) instead of `self.df[self.cols["X"]]` (the column's values), and use `>=`
  for both the start *and* end date bound. They're not used by the current agent pipeline,
  so they were left as-is; fix them if anything ever calls them.
- Negative `POS_UNIT` values appear in the data (e.g. `-6` units for one SKU — likely a
  returns/credit adjustment) and are currently shown as-is in trend messages rather than
  clamped or specially flagged.
- `growth_pct` in trend summaries is a plain period-over-period `pct_change()`, which can
  mathematically exceed 100% in magnitude when the base period is small or negative,
  producing confusing text like "declined 233%". Not yet fixed.

## Legacy files (`legacy/`)

Kept out of the installable package; not maintained (imports in them still use the old
pre-package module paths).

- `legacy/test.py`, `legacy/test.ipynb` — ad hoc scratch scripts from before the agent
  pipeline existed.
- `legacy/constants.py` — large static data (`POS_CALENDAR_MAP`, a week-number ↔ date
  lookup for 2013 onward), unrelated to the agent pipeline.
- `legacy/utils.py` — empty placeholder from the original scaffold.
