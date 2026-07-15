from __future__ import annotations

import calendar
import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv
from google import genai

load_dotenv()

VALID_LEVELS = {"retailer", "category", "sku", "key"}

_GEMINI_MODEL = "gemini-2.5-flash"
_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (check .env).")
        _client = genai.Client(api_key=api_key)
    return _client

_ACCURACY_FUNCTION_BY_LEVEL = {
    "retailer": "get_forecast_retailer_accuracy",
    "category": "get_forecast_category_accuracy",
    "sku": "get_forecast_sku_accuracy",
    "key": "get_forecast_key_accuracy",
}


@dataclass
class AnalysisRequest:
    """
    Structured input for the analyst agent: what entity, at what level,
    for which year/month, is the user asking about. Populated by
    `extract_analysis_request` from the user's free-text query.

    `retailer` is an extra scope, only meaningful when level == "category":
    which retailer's slice of that category to analyze (e.g. "AMAZON Stand
    Mixers" -> level="category", identifier="Stand Mixers", retailer="AMAZON").
    """

    level: Optional[str] = None
    identifier: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    retailer: Optional[str] = None


def validate_request(request: AnalysisRequest) -> Optional[str]:
    """
    Returns a clarification question if the request is missing or invalid
    fields, otherwise None.
    """
    if request.level and request.level not in VALID_LEVELS:
        return (
            f"'{request.level}' is not a supported level. "
            f"Please specify one of: {', '.join(sorted(VALID_LEVELS))}."
        )

    missing = []
    if not request.level:
        missing.append("level (retailer, category, sku, or key)")
    if not request.identifier:
        missing.append("identifier (the retailer/category/sku/key name)")
    if not request.year:
        missing.append("year")
    if not request.month:
        missing.append("month")

    if missing:
        return f"Could you clarify the following: {', '.join(missing)}?"
    return None


_EXTRACTION_PROMPT = """\
Extract the following fields from the user's question about retail forecast \
accuracy. Respond with ONLY a JSON object, no markdown fences, with exactly \
these keys:

- "level": one of "retailer", "category", "sku", "key" -- or null if not \
  clearly stated.
- "identifier": the specific proper name or code of that retailer, category, \
  SKU, or key, copied verbatim from the question -- or null if no specific \
  name/code is mentioned. Do NOT guess or invent an identifier from generic \
  words like "sales", "business", "products", or "performance" -- those are \
  not identifiers.
- "year": a 4-digit integer explicitly stated in the question -- or null if \
  not stated. Do not infer a year from relative phrases like "this year" or \
  "last month".
- "month": an integer 1-12 explicitly stated in the question -- or null if \
  not stated. Do not infer a month from relative phrases.
- "retailer": ONLY set this when "level" is "category" AND the question also \
  names a specific retailer to scope that category to (e.g. "AMAZON Stand \
  Mixers category" means the category "Stand Mixers" within retailer \
  "AMAZON") -- the retailer name copied verbatim, or null otherwise.

Examples:
Question: "why is AMAZON doing bad in the month 6 in 2026"
{{"level": "retailer", "identifier": "AMAZON", "year": 2026, "month": 6, "retailer": null}}

Question: "why is sales bad this year"
{{"level": null, "identifier": null, "year": null, "month": null, "retailer": null}}

Question: "Analyze AMAZON Stand Mixers category 2026 month 5"
{{"level": "category", "identifier": "Stand Mixers", "year": 2026, "month": 5, "retailer": "AMAZON"}}

User question: {query}
"""


def extract_analysis_request(query: str) -> AnalysisRequest:
    """
    Use Gemini to extract level/identifier/year/month from a free-text query.
    Any field the model can't confidently determine is left as None, which
    `validate_request` then turns into a clarification question for the user.
    """
    response = _get_client().models.generate_content(
        model=_GEMINI_MODEL,
        contents=_EXTRACTION_PROMPT.format(query=query),
    )
    text = response.text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]

    try:
        data: Dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        return AnalysisRequest()

    level = data.get("level")
    if level not in VALID_LEVELS:
        level = None

    return AnalysisRequest(
        level=level,
        identifier=data.get("identifier") or None,
        year=int(data["year"]) if data.get("year") else None,
        month=int(data["month"]) if data.get("month") else None,
        retailer=data.get("retailer") or None if level == "category" else None,
    )


@dataclass
class PlanStep:
    """
    One step of an analysis plan.

    `repository` tells the executing agent which repository instance to
    inject ("forecast" -> ForecastRepository, "datamart" -> DatamartRepository,
    "none" for steps that only synthesize prior results).

    `for_each`, when set, tells the executor to repeat this step once per item
    in a prior step's output list, referenced as "<step_id>.<field>". Args
    containing "{item.<field>}" are substituted per iteration.

    `pos_unit_bounded`, when True, tells the executor this step reads actual
    POS_UNIT (sales) history, which the datamart only has up to some cutoff --
    rows beyond it are placeholder feature rows (POS_UNIT filled with 0/-999)
    generated for forward-looking inference, not real sales. The executor
    clips `end_date` to that cutoff before calling. Feature-only steps
    (price/promo/discount, which stay populated into the future) leave this
    False.
    """

    step_id: str
    description: str
    repository: str
    module: str
    function: str
    args: Dict[str, Any] = field(default_factory=dict)
    for_each: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    pos_unit_bounded: bool = False


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start.isoformat(), end.isoformat()


def _history_start(month_start: str, months_back: int = 12) -> str:
    """Trailing window start, `months_back` months before `month_start`."""
    d = date.fromisoformat(month_start)
    total_month_index = d.year * 12 + (d.month - 1) - months_back
    hist_year, hist_month = divmod(total_month_index, 12)
    return date(hist_year, hist_month + 1, 1).isoformat()


def _drill_down_steps(
    key_placeholder: str,
    for_each: Optional[str],
    history_start: str,
    month_start: str,
    month_end: str,
    year: int,
    month: int,
) -> List[PlanStep]:
    """
    Root-cause data-gathering steps for a single key: forecast accuracy,
    sales trend (declining trend / near-zero sales -> possible delisting),
    seasonality (is this month naturally low/high), and promotions (did a
    promo price/discount indicate higher sales that didn't materialize).
    """
    return [
        PlanStep(
            step_id="key_accuracy",
            description="Get forecast accuracy for the drilled-down key.",
            repository="forecast",
            module="kasa_agent.analyzers.analyzer_main",
            function="get_forecast_key_accuracy",
            args={"year": year, "month": month, "key": key_placeholder},
            for_each=for_each,
            depends_on=["entity_accuracy"],
        ),
        PlanStep(
            step_id="key_trend",
            description=(
                "Get sales trend for the key over the trailing 12 months to "
                "check for a declining trend or near-zero sales (possible "
                "delisting)."
            ),
            repository="datamart",
            module="kasa_agent.analyzers.trend",
            function="TrendAnalyzer.get_level_trend_summary",
            args={
                "level": "key",
                "identifier": key_placeholder,
                "start_date": history_start,
                "end_date": month_end,
                "metric_col": "POS_UNIT",
            },
            for_each=for_each,
            depends_on=["entity_accuracy"],
            pos_unit_bounded=True,
        ),
        PlanStep(
            step_id="key_seasonality",
            description=(
                "Get monthly seasonality profile for the key to check whether "
                "the report month is naturally a low/high month."
            ),
            repository="datamart",
            module="kasa_agent.analyzers.seasonality",
            function="SeasonalityAnalyzer.get_level_seasonality_summary",
            args={
                "level": "key",
                "identifier": key_placeholder,
                "start_date": history_start,
                "end_date": month_end,
                "metric_col": "POS_UNIT",
            },
            for_each=for_each,
            depends_on=["entity_accuracy"],
            pos_unit_bounded=True,
        ),
        PlanStep(
            step_id="key_promotions",
            description=(
                "Get promo price / price / discount trend and YoY comparison "
                "for the key to check whether a promotion indicated higher "
                "sales that did not materialize."
            ),
            repository="datamart",
            module="kasa_agent.analyzers.promotions",
            function="PromoAnalyzer.get_feature_summary_dict",
            args={
                "level": "key",
                "identifier": key_placeholder,
                "start_date": month_start,
                "end_date": month_end,
            },
            for_each=for_each,
            depends_on=["entity_accuracy"],
        ),
    ]


def create_plan(request: AnalysisRequest) -> List[PlanStep]:
    """
    Build the drill-down analysis plan mirroring the manual analyst workflow:

      1. Pull forecast accuracy for the requested entity. This already
         surfaces the top 5 worst-performing keys under it (via
         calculate_top5_worse_keys), so no separate "find bad keys" step
         is needed above the key level.
      2. For each of those worst keys (or the single key itself, if the
         request is already at key level), drill into key-level accuracy,
         trend, seasonality, and promotion features to gather candidate
         root causes.
      3. Leave the actual reasoning/synthesis (which cause applies to which
         key) to the analyst agent that executes this plan -- this function
         only orders the data-gathering steps.

    Raises ValueError if the request is incomplete or invalid; callers should
    check `validate_request` first and ask the user for clarification instead
    of relying on this exception for control flow.
    """
    error = validate_request(request)
    if error:
        raise ValueError(error)

    level = request.level
    identifier = request.identifier
    year = request.year
    month = request.month

    month_start, month_end = _month_bounds(year, month)
    history_start = _history_start(month_start)

    if level == "category" and request.retailer:
        # Compound scope: this category within one specific retailer, not
        # the category across all retailers.
        entity_step = PlanStep(
            step_id="entity_accuracy",
            description=(
                f"Get forecast accuracy for category={identifier} within "
                f"retailer={request.retailer} ({year}-{month:02d}) from the "
                "forecast repository."
            ),
            repository="forecast",
            module="kasa_agent.analyzers.analyzer_main",
            function="get_forecast_retailer_category_accuracy",
            args={
                "year": year,
                "month": month,
                "retailer": request.retailer,
                "category": identifier,
            },
        )
    else:
        entity_step = PlanStep(
            step_id="entity_accuracy",
            description=(
                f"Get forecast accuracy for {level}={identifier} "
                f"({year}-{month:02d}) from the forecast repository."
            ),
            repository="forecast",
            module="kasa_agent.analyzers.analyzer_main",
            function=_ACCURACY_FUNCTION_BY_LEVEL[level],
            args={"year": year, "month": month, level: identifier},
        )

    steps: List[PlanStep] = [entity_step]

    if level == "key":
        # Already atomic -- gather context directly, no fan-out needed.
        steps += _drill_down_steps(
            identifier, None, history_start, month_start, month_end, year, month
        )
    else:
        # Fan out over the worst keys surfaced by the entity_accuracy step.
        steps += _drill_down_steps(
            "{item.key}",
            "entity_accuracy.top5_worse_keys",
            history_start,
            month_start,
            month_end,
            year,
            month,
        )

    steps.append(
        PlanStep(
            step_id="synthesize_reasons",
            description=(
                "Combine entity accuracy, key accuracy, trend, seasonality, "
                "and promotion signals into a root-cause explanation per key "
                "(e.g. declining trend, promo miss, seasonal dip, or "
                "near-zero sales / possible delisting), then roll up into "
                "the final accuracy report for the requested entity."
            ),
            repository="none",
            module="kasa_agent.agents.planner_agent",
            function="<analyst_agent_synthesis>",
            depends_on=[
                "entity_accuracy",
                "key_accuracy",
                "key_trend",
                "key_seasonality",
                "key_promotions",
            ],
        )
    )

    return steps


def handle_query(query: str) -> Union[List[PlanStep], str]:
    """
    Entry point for the planner: extract structured fields from the user's
    free-text query, ask for clarification if anything is missing or
    ambiguous, otherwise build and return the analysis plan.
    """
    request = extract_analysis_request(query)
    error = validate_request(request)
    if error:
        return error
    return create_plan(request)


if __name__ == "__main__":
    result = handle_query("why is AMAZON doing bad in the month 6 in 2026")
    if isinstance(result, str):
        print("Clarification needed:", result)
    else:
        for step in result:
            print(step)
