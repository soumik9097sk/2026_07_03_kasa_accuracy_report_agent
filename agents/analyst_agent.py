from __future__ import annotations

import importlib
import json
import re
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from agents.planner_agent import (
    AnalysisRequest,
    PlanStep,
    _GEMINI_MODEL,
    _get_client,
    create_plan,
    extract_analysis_request,
    validate_request,
)
from repositories.datamart_repository import DatamartRepository
from repositories.forecast_repository import ForecastRepository

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
                call(**_substitute_args(step.args, item)) for item in items
            ]
        else:
            results[step.step_id] = call(**_substitute_args(step.args, None))

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

    average = trend_summary.get("average") or 0.0
    latest = trend_summary.get("latest") or 0.0
    if average > 0 and latest <= 0.1 * average:
        reasons.append(
            "Sales have dropped to near zero relative to their trailing "
            "average -- check whether this product has been delisted or "
            "pulled from the market."
        )
    elif (
        trend_summary.get("direction") == "downward"
        and (trend_summary.get("growth_pct") or 0) < -0.1
    ):
        reasons.append("Sales show a declining trend leading into this month.")

    lowest_month = seasonality_summary.get("lowest_month")
    if lowest_month and lowest_month.get("month_number") == month:
        reasons.append(
            f"{lowest_month['month']} is historically this key's "
            "lowest-selling month -- under-performance here may be seasonal "
            "rather than a forecast error."
        )

    peak_month = seasonality_summary.get("peak_month")
    if (
        peak_month
        and peak_month.get("month_number") == month
        and bias_info["bias"] == "over_forecast"
    ):
        reasons.append(
            f"{peak_month['month']} is historically this key's peak-selling "
            "month, yet actuals came in below forecast -- worth checking for "
            "stockouts or demand disruption."
        )

    promo_price = promo_summary.get("PROMO_PRICE", {})
    discount = promo_summary.get("DISCOUNT", {})
    sales_upward = trend_summary.get("direction") == "upward"
    if (
        promo_price.get("trend") == "lower" or discount.get("trend") == "higher"
    ) and not sales_upward:
        reasons.append(
            "A deeper promotion/discount was applied but did not translate "
            "into higher sales -- the forecast may have over-weighted the "
            "expected promo lift."
        )

    price = promo_summary.get("PRICE", {})
    if price.get("trend") == "higher" and trend_summary.get("direction") == "downward":
        reasons.append(
            "Price increased over the period, which may have suppressed demand."
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

        key_findings.append(
            {
                "key": key,
                "metrics": accuracy,
                "forecast_total": bias_info["forecast_total"],
                "actual_total": bias_info["actual_total"],
                "bias": bias_info["bias"],
                "reasons": reasons,
            }
        )

    return {
        "entity_type": request.level,
        "entity_value": request.identifier,
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
    report = synthesize_reasons(raw_results, request, forecast_repo)
    report["narrative"] = generate_narrative(report)
    return report
