from __future__ import annotations

import importlib
import json
import re
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from kasa_agent.agents.planner_agent import (
    AnalysisRequest,
    PlanStep,
    _GEMINI_MODEL,
    _get_client,
    _month_bounds,
    create_plan,
    extract_analysis_request,
    validate_request,
)
from kasa_agent.repositories.datamart_repository import DatamartRepository
from kasa_agent.repositories.forecast_repository import ForecastRepository

_PLACEHOLDER_RE = re.compile(r"^\{item\.(\w+)\}$")


def _substitute_args(
    args: Dict[str, Any], item: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    resolved = {}
    for key, value in args.items():
        match = _PLACEHOLDER_RE.match(value) if isinstance(value, str) else None
        resolved[key] = item[match.group(1)] if match and item is not None else value
    return resolved


def _resolve_step_callable(step: PlanStep, forecast_repo, datamart_repo):
    module = importlib.import_module(step.module)
    repo = {"forecast": forecast_repo, "datamart": datamart_repo, "none": None}[
        step.repository
    ]

    if "." in step.function:
        class_name, method_name = step.function.split(".", 1)
        instance = getattr(module, class_name)(repo)
        return getattr(instance, method_name)

    func = getattr(module, step.function)
    return lambda **kwargs: func(repo, **kwargs)


def _pos_unit_cutoff(datamart_repo: DatamartRepository) -> Optional[pd.Timestamp]:
    """
    Datamart rows beyond a certain date are forward-looking placeholder rows
    generated for inference (other features stay populated, but POS_UNIT is
    filled with 0/-999 since those sales haven't happened/been loaded yet).
    Returns the latest date with real (non 0/-999) POS_UNIT data, or None if
    none is found.
    """
    pos_col = datamart_repo.cols["POS_UNIT"]
    date_col = datamart_repo.cols["WEEK_END_DATE"]
    df = datamart_repo.df
    real = df.loc[~df[pos_col].isin([0, -999]), date_col]
    return real.max() if not real.empty else None


def _clip_end_date(args: Dict[str, Any], cutoff: Optional[pd.Timestamp]) -> Dict[str, Any]:
    if cutoff is None or "end_date" not in args:
        return args
    if pd.to_datetime(args["end_date"]) <= cutoff:
        return args
    clipped = dict(args)
    clipped["end_date"] = cutoff.date().isoformat()
    return clipped


def execute_plan(
    plan: List[PlanStep],
    forecast_repo: ForecastRepository,
    datamart_repo: Optional[DatamartRepository] = None,
) -> Dict[str, Any]:
    """
    Run each data-gathering step in the plan, in order, resolving `for_each`
    fan-out over a prior step's output list. The final `synthesize_reasons`
    step is a marker for the analyst agent's own logic and is skipped here.
    """
    results: Dict[str, Any] = {}
    pos_unit_cutoff = _pos_unit_cutoff(datamart_repo) if datamart_repo is not None else None

    for step in plan:
        if step.function == "<analyst_agent_synthesis>":
            continue

        if step.repository == "datamart" and datamart_repo is None:
            # No datamart data available -- skip this drill-down step rather
            # than fail, leaving empty placeholders for synthesize_reasons.
            if step.for_each:
                ref_step_id, ref_field = step.for_each.split(".", 1)
                items = results[ref_step_id][ref_field]
                results[step.step_id] = [{} for _ in items]
            else:
                results[step.step_id] = {}
            continue

        call = _resolve_step_callable(step, forecast_repo, datamart_repo)

        if step.for_each:
            ref_step_id, ref_field = step.for_each.split(".", 1)
            items = results[ref_step_id][ref_field]
            results[step.step_id] = [
                call(
                    **_clip_end_date(
                        _substitute_args(step.args, item),
                        pos_unit_cutoff if step.pos_unit_bounded else None,
                    )
                )
                for item in items
            ]
        else:
            results[step.step_id] = call(
                **_clip_end_date(
                    _substitute_args(step.args, None),
                    pos_unit_cutoff if step.pos_unit_bounded else None,
                )
            )

    return results


def _pull_bias(
    forecast_repo: ForecastRepository, year: int, month: int, key: str
) -> Dict[str, Any]:
    """Aggregate forecast vs. actual totals for a key to determine over/under-forecast bias."""
    cols = forecast_repo.cols
    forecast_df = forecast_repo.get_forecast_key(year, month, key)
    actual_df = forecast_repo.get_actual_key(year, month, key)
    forecast_total = pd.to_numeric(
        forecast_df[cols["FORECAST"]], errors="coerce"
    ).sum()
    actual_total = pd.to_numeric(actual_df[cols["ACTUAL"]], errors="coerce").sum()

    if forecast_total > actual_total:
        bias = "over_forecast"
    elif forecast_total < actual_total:
        bias = "under_forecast"
    else:
        bias = "balanced"

    return {
        "forecast_total": float(forecast_total),
        "actual_total": float(actual_total),
        "bias": bias,
    }


def _yoy_sales_comparison(
    datamart_repo: Optional[DatamartRepository],
    year: int,
    month: int,
    key: str,
    this_year_actual: float,
) -> Dict[str, Any]:
    """
    This year's actuals come from the forecast file (passed in); last year's
    actuals for the same key/month are pulled from the datamart's POS_UNIT
    history, giving a YoY sales baseline. Returns last_year_actual=None if no
    datamart is available or it has no real (non 0/-999-only) data for that
    period.
    """
    result: Dict[str, Any] = {
        "this_year_actual": this_year_actual,
        "last_year_actual": None,
        "yoy_change_pct": None,
    }
    if datamart_repo is None:
        return result

    pos_col = datamart_repo.cols["POS_UNIT"]
    prev_start, prev_end = _month_bounds(year - 1, month)
    frame = datamart_repo.get_key(key, prev_start, prev_end)
    if frame.empty:
        return result

    valid = frame.loc[~frame[pos_col].isin([0, -999]), pos_col]
    if valid.empty:
        return result

    last_year_actual = float(valid.sum())
    result["last_year_actual"] = last_year_actual
    if last_year_actual != 0:
        result["yoy_change_pct"] = (
            (this_year_actual - last_year_actual) / abs(last_year_actual) * 100
        )
    return result


def _promo_depth_shift(promo_price: Dict[str, Any], discount: Dict[str, Any]) -> Optional[str]:
    """
    Whether this year's promotion was deeper or shallower than last year's,
    from the PROMO_PRICE (lower price ratio = deeper discount) and DISCOUNT
    depth (higher = deeper discount) YoY comparisons. Returns None if the two
    signals disagree or neither is available.
    """
    promo_price_comp = promo_price.get("comp_to_last_year")
    discount_comp = discount.get("comp_to_last_year")

    deeper = promo_price_comp == "decreased" or discount_comp == "increased"
    shallower = promo_price_comp == "increased" or discount_comp == "decreased"

    if deeper and not shallower:
        return "deeper"
    if shallower and not deeper:
        return "shallower"
    return None


def _fmt_money(value: Optional[float]) -> str:
    return f"${value:,.2f}" if value is not None else "N/A"


def _fmt_units(value: Optional[float]) -> str:
    return f"{value:,.0f}" if value is not None else "N/A"


def _fmt_pct(value: Optional[float]) -> str:
    return f"{value:.1f}%" if value is not None else "N/A"


def _promo_change_detail(
    promo_price: Dict[str, Any], discount: Dict[str, Any], yoy: bool
) -> str:
    """Concrete before/after price and discount figures backing a promo-based reason."""
    parts = []
    if yoy:
        if promo_price.get("current_avg") is not None and promo_price.get("previous_avg") is not None:
            parts.append(
                f"promo price averaged {_fmt_money(promo_price['previous_avg'])} last "
                f"year vs {_fmt_money(promo_price['current_avg'])} this year"
            )
        if discount.get("current_avg") is not None and discount.get("previous_avg") is not None:
            parts.append(
                f"discount depth averaged {_fmt_pct(discount['previous_avg'])} last "
                f"year vs {_fmt_pct(discount['current_avg'])} this year"
            )
    else:
        if promo_price.get("trend") == "lower":
            parts.append(
                f"promo price moved from {_fmt_money(promo_price['first_value'])} to "
                f"{_fmt_money(promo_price['last_value'])}"
            )
        if discount.get("trend") == "higher":
            parts.append(
                f"discount depth moved from {_fmt_pct(discount['first_value'])} to "
                f"{_fmt_pct(discount['last_value'])}"
            )
    return "; ".join(parts)


def _classify_key_reasons(
    bias_info: Dict[str, Any],
    trend_summary: Dict[str, Any],
    seasonality_summary: Dict[str, Any],
    promo_summary: Dict[str, Any],
    month: int,
    accuracy: Dict[str, Any],
) -> List[str]:
    """
    Rule-based candidate root causes for a key's forecast miss, mirroring the
    manual analyst drill-down: declining/collapsed trend, seasonal timing,
    and promo/price signals that didn't translate into sales.
    """
    reasons: List[str] = []

    if trend_summary.get("count", 0) == 0:
        reasons.append(
            "No POS_UNIT sales history is available for this key before the "
            "report month in the current datamart snapshot -- trend cannot "
            "be assessed from this data."
        )
    else:
        average = trend_summary.get("average") or 0.0
        latest = trend_summary.get("latest") or 0.0
        if average > 0 and latest <= 0.1 * average:
            reasons.append(
                f"Sales dropped to {_fmt_units(latest)} units in the most "
                f"recent period vs a trailing average of {_fmt_units(average)} "
                "units -- check whether this product has been delisted or "
                "pulled from the market."
            )
        elif (
            trend_summary.get("direction") == "downward"
            and (trend_summary.get("growth_pct") or 0) < -0.1
        ):
            growth_pct = trend_summary.get("growth_pct") or 0.0
            reasons.append(
                f"Sales declined {abs(growth_pct) * 100:.1f}% into this month "
                f"(latest: {_fmt_units(latest)} units vs trailing average of "
                f"{_fmt_units(average)} units)."
            )

    overall_avg = seasonality_summary.get("average")
    lowest_month = seasonality_summary.get("lowest_month")
    if lowest_month and lowest_month.get("month_number") == month:
        reasons.append(
            f"{lowest_month['month']} is historically this key's "
            f"lowest-selling month (avg {_fmt_units(lowest_month.get('value'))} "
            f"units vs overall average {_fmt_units(overall_avg)} units) -- "
            "under-performance here may be seasonal rather than a forecast "
            "error."
        )

    peak_month = seasonality_summary.get("peak_month")
    if (
        peak_month
        and peak_month.get("month_number") == month
        and bias_info["bias"] == "over_forecast"
    ):
        reasons.append(
            f"{peak_month['month']} is historically this key's peak-selling "
            f"month (avg {_fmt_units(peak_month.get('value'))} units vs "
            f"overall average {_fmt_units(overall_avg)} units), yet actuals "
            "came in below forecast -- worth checking for stockouts or "
            "demand disruption."
        )

    promo_price = promo_summary.get("PROMO_PRICE", {})
    discount = promo_summary.get("DISCOUNT", {})
    sales_upward = trend_summary.get("direction") == "upward"
    if (
        promo_price.get("trend") == "lower" or discount.get("trend") == "higher"
    ) and not sales_upward:
        detail = _promo_change_detail(promo_price, discount, yoy=False)
        reasons.append(
            f"A deeper promotion/discount was applied ({detail}) but did not "
            "translate into higher sales -- the forecast may have "
            "over-weighted the expected promo lift."
        )

    price = promo_summary.get("PRICE", {})
    if price.get("trend") == "higher" and trend_summary.get("direction") == "downward":
        reasons.append(
            f"Price increased from {_fmt_money(price.get('first_value'))} to "
            f"{_fmt_money(price.get('last_value'))} over the period, which "
            "may have suppressed demand."
        )

    bias = bias_info["bias"]
    depth_shift = _promo_depth_shift(promo_price, discount)
    yoy_detail = _promo_change_detail(promo_price, discount, yoy=True)
    if depth_shift == "shallower" and bias == "over_forecast":
        reasons.append(
            f"This year's promotion was shallower than last year's "
            f"({yoy_detail}), consistent with actuals coming in below "
            "forecast."
        )
    elif depth_shift == "deeper" and bias == "over_forecast":
        reasons.append(
            f"Despite a deeper promotion than last year ({yoy_detail}), "
            "actuals still missed forecast -- promo effectiveness may be "
            "declining, or another factor suppressed demand."
        )
    elif depth_shift == "deeper" and bias == "under_forecast":
        reasons.append(
            f"This year's promotion was deeper than last year's "
            f"({yoy_detail}), consistent with actuals exceeding forecast."
        )
    elif depth_shift == "shallower" and bias == "under_forecast":
        reasons.append(
            f"Actuals exceeded forecast despite a shallower promotion than "
            f"last year ({yoy_detail}) -- underlying demand appears "
            "stronger than the forecast assumed."
        )

    if not reasons:
        mape = accuracy.get("mape")
        mape_text = (
            f"{mape:.1f}%" if isinstance(mape, (int, float)) and mape == mape else "N/A"
        )
        reasons.append(
            f"No clear driver identified from trend, seasonality, or promotion "
            f"signals (MAPE {mape_text}) -- may need manual review."
        )

    return reasons


def synthesize_reasons(
    results: Dict[str, Any],
    request: AnalysisRequest,
    forecast_repo: ForecastRepository,
    datamart_repo: Optional[DatamartRepository] = None,
) -> Dict[str, Any]:
    """
    Combine entity accuracy, key accuracy, trend, seasonality, and promotion
    signals into a root-cause explanation per key, rolled up into the final
    accuracy report for the requested entity.
    """
    entity_accuracy = results["entity_accuracy"]

    key_accuracy_list = results.get("key_accuracy", [])
    key_trend_list = results.get("key_trend", [])
    key_seasonality_list = results.get("key_seasonality", [])
    key_promotions_list = results.get("key_promotions", [])

    if isinstance(key_accuracy_list, list):
        keys = [item["key"] for item in entity_accuracy.get("top5_worse_keys", [])]
    else:
        keys = [request.identifier]
        key_accuracy_list = [key_accuracy_list]
        key_trend_list = [key_trend_list]
        key_seasonality_list = [key_seasonality_list]
        key_promotions_list = [key_promotions_list]

    key_findings = []
    for idx, key in enumerate(keys):
        accuracy = key_accuracy_list[idx].get("metrics", {})
        trend_summary = key_trend_list[idx]
        seasonality_summary = key_seasonality_list[idx]
        promo_summary = key_promotions_list[idx]

        bias_info = _pull_bias(forecast_repo, request.year, request.month, key)
        reasons = _classify_key_reasons(
            bias_info, trend_summary, seasonality_summary, promo_summary,
            request.month, accuracy,
        )
        yoy_sales = _yoy_sales_comparison(
            datamart_repo, request.year, request.month, key, bias_info["actual_total"]
        )

        key_findings.append(
            {
                "key": key,
                "metrics": accuracy,
                "forecast_total": bias_info["forecast_total"],
                "actual_total": bias_info["actual_total"],
                "bias": bias_info["bias"],
                "yoy_sales": yoy_sales,
                "reasons": reasons,
            }
        )

    entity_value = (
        f"{request.retailer} / {request.identifier}"
        if request.level == "category" and request.retailer
        else request.identifier
    )

    return {
        "entity_type": request.level,
        "entity_value": entity_value,
        "year": request.year,
        "month": request.month,
        "entity_metrics": entity_accuracy.get("metrics", {}),
        "key_findings": key_findings,
    }


_NARRATIVE_PROMPT = """\
You are writing a concise forecast-accuracy report for a retail analytics \
team. Given the structured findings below (JSON), write a short \
business-readable explanation: first the overall accuracy for the {level} \
"{identifier}" in {year}-{month:02d}, then for each listed key, state \
whether it was over-forecast or under-forecast and the most likely reason(s) \
from the data. Be concise and factual -- do not invent numbers that are not \
present in the JSON. Plain prose, no markdown headers.

JSON findings:
{findings_json}
"""


def generate_narrative(report: Dict[str, Any]) -> str:
    prompt = _NARRATIVE_PROMPT.format(
        level=report["entity_type"],
        identifier=report["entity_value"],
        year=report["year"],
        month=report["month"],
        findings_json=json.dumps(report, indent=2, default=str),
    )
    response = _get_client().models.generate_content(
        model=_GEMINI_MODEL, contents=prompt
    )
    return response.text.strip()


def generate_accuracy_report(
    query: str,
    forecast_df: pd.DataFrame,
    datamart_df: Optional[pd.DataFrame] = None,
) -> Union[str, Dict[str, Any]]:
    """
    End-to-end entry point: parse the query, ask for clarification if it's
    incomplete, otherwise build the plan, execute it against the given data,
    and return the synthesized accuracy report with a written narrative.
    """
    request = extract_analysis_request(query)
    error = validate_request(request)
    if error:
        return error

    plan = create_plan(request)
    forecast_repo = ForecastRepository(forecast_df)
    datamart_repo = DatamartRepository(datamart_df) if datamart_df is not None else None

    raw_results = execute_plan(plan, forecast_repo, datamart_repo)
    report = synthesize_reasons(raw_results, request, forecast_repo, datamart_repo)
    report["narrative"] = generate_narrative(report)
    return report
