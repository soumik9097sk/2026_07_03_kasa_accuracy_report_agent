from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import pandas as pd

from analyzers.forecast_analyzer_main import (
    calculate_mae,
    calculate_mape,
    calculate_smape,
    calculate_top5_worse_keys,
    calculate_wmape,
)
from analyzers.trend import TrendAnalyzer
from repositories.datamart_repository import DatamartRepository
from repositories.forecast_repository import ForecastRepository


def _format_change_point(index_value: Any, year: Optional[int] = None) -> str:
    if hasattr(index_value, "isocalendar"):
        cal = index_value.isocalendar()
        return f"{cal[0]}-W{cal[1]:02d}"

    try:
        week_value = int(index_value)
        if year is not None:
            return f"{year}-W{week_value:02d}"
        return f"W{week_value:02d}"
    except Exception:
        return str(index_value)


def _calculate_sales_trend(
    trend_series: pd.Series, year: Optional[int] = None
) -> Dict[str, Any]:
    """
    Helper function to calculate sales trend from a time series.
    Returns JSON with trend direction, percentage change, and change points.
    """
    if trend_series.empty:
        return {
            "sales_trend": {
                "trend": "No Data",
                "pct_change": 0,
                "change_point": None,
            }
        }

    # Calculate direction and percentage change
    first_value = trend_series.iloc[0]
    last_value = trend_series.iloc[-1]

    if first_value == 0:
        pct_change = 0
    else:
        pct_change = round(((last_value - first_value) / first_value) * 100, 2)

    # Determine trend direction
    if last_value > first_value:
        trend_direction = "Upward"
    elif last_value < first_value:
        trend_direction = "Downward"
    else:
        trend_direction = "Flat"

    # Identify change points (where direction changes)
    change_points = []
    pct_changes = trend_series.pct_change()

    for i in range(1, len(pct_changes)):
        if pct_changes.iloc[i] != 0:
            prev_sign = (
                1
                if pct_changes.iloc[i - 1] > 0
                else (-1 if pct_changes.iloc[i - 1] < 0 else 0)
            )
            curr_sign = (
                1 if pct_changes.iloc[i] > 0 else (-1 if pct_changes.iloc[i] < 0 else 0)
            )

            if prev_sign != 0 and curr_sign != 0 and prev_sign != curr_sign:
                index_val = trend_series.index[i]
                change_points.append(_format_change_point(index_val, year))

    # Use the first significant change point, or None if no changes
    change_point = change_points[0] if change_points else None

    return {
        "sales_trend": {
            "trend": trend_direction,
            "pct_change": pct_change,
            "change_point": change_point,
        }
    }


def get_retailer_sales_trend(
    repository: DatamartRepository,
    retailer: str,
    start_date: str,
    end_date: str,
    metric_col: str = "POS_UNIT",
) -> Dict[str, Any]:
    """
    Analyze retailer sales trend and return JSON output with trend direction,
    percentage change, and change points.
    """
    analyzer = TrendAnalyzer(repository)
    trend_series = analyzer.get_retailer_trend(
        retailer, start_date, end_date, metric_col
    )
    return _calculate_sales_trend(trend_series)


def get_sku_sales_trend(
    repository: DatamartRepository,
    sku: str,
    start_date: str,
    end_date: str,
    metric_col: str = "POS_UNIT",
) -> Dict[str, Any]:
    """
    Analyze SKU sales trend and return JSON output with trend direction,
    percentage change, and change points.
    """
    analyzer = TrendAnalyzer(repository)
    trend_series = analyzer.get_sku_trend(sku, start_date, end_date, metric_col)
    return _calculate_sales_trend(trend_series)


def get_key_sales_trend(
    repository: DatamartRepository,
    key: str,
    start_date: str,
    end_date: str,
    metric_col: str = "POS_UNIT",
) -> Dict[str, Any]:
    """
    Analyze key sales trend and return JSON output with trend direction,
    percentage change, and change points.
    """
    analyzer = TrendAnalyzer(repository)
    trend_series = analyzer.get_key_trend(key, start_date, end_date, metric_col)
    return _calculate_sales_trend(trend_series)


def get_category_sales_trend(
    repository: DatamartRepository,
    category: str,
    start_date: str,
    end_date: str,
    metric_col: str = "POS_UNIT",
) -> Dict[str, Any]:
    """
    Analyze product category sales trend and return JSON output with trend direction,
    percentage change, and change points.
    """
    analyzer = TrendAnalyzer(repository)
    trend_series = analyzer.get_category_trend(
        category, start_date, end_date, metric_col
    )
    return _calculate_sales_trend(trend_series)


def get_forecast_retailer_sales_trend(
    repository: ForecastRepository,
    year: int,
    month: int,
    retailer: str,
) -> Dict[str, Any]:
    """
    Analyze forecast sales trend for a retailer and return JSON output.
    """
    series = repository.get_forecast_retailer(year, month, retailer)
    if series.empty:
        return _calculate_sales_trend(pd.Series(dtype="float64"))

    trend_series = series.set_index(repository.cols["WEEK"])[
        repository.cols["FORECAST"]
    ]
    return _calculate_sales_trend(trend_series, year)


def get_forecast_category_sales_trend(
    repository: ForecastRepository,
    year: int,
    month: int,
    category: str,
) -> Dict[str, Any]:
    """
    Analyze forecast sales trend for a product category and return JSON output.
    """
    series = repository.get_forecast_category(year, month, category)
    if series.empty:
        return _calculate_sales_trend(pd.Series(dtype="float64"))

    trend_series = series.set_index(repository.cols["WEEK"])[
        repository.cols["FORECAST"]
    ]
    return _calculate_sales_trend(trend_series, year)


def get_forecast_sku_sales_trend(
    repository: ForecastRepository,
    year: int,
    month: int,
    sku: str,
) -> Dict[str, Any]:
    """
    Analyze forecast sales trend for a SKU and return JSON output.
    """
    series = repository.get_forecast_sku(year, month, sku)
    if series.empty:
        return _calculate_sales_trend(pd.Series(dtype="float64"))

    trend_series = series.set_index(repository.cols["WEEK"])[
        repository.cols["FORECAST"]
    ]
    return _calculate_sales_trend(trend_series, year)


def get_forecast_key_sales_trend(
    repository: ForecastRepository,
    year: int,
    month: int,
    key: str,
) -> Dict[str, Any]:
    """
    Analyze forecast sales trend for a key and return JSON output.
    """
    series = repository.get_forecast_key(year, month, key)
    if series.empty:
        return _calculate_sales_trend(pd.Series(dtype="float64"))

    trend_series = series.set_index(repository.cols["WEEK"])[
        repository.cols["FORECAST"]
    ]
    return _calculate_sales_trend(trend_series, year)


def get_actual_retailer_sales_trend(
    repository: ForecastRepository,
    year: int,
    month: int,
    retailer: str,
) -> Dict[str, Any]:
    """
    Analyze actual sales trend for a retailer and return JSON output.
    """
    series = repository.get_actual_retailer(year, month, retailer)
    if series.empty:
        return _calculate_sales_trend(pd.Series(dtype="float64"))

    trend_series = series.set_index(repository.cols["WEEK"])[repository.cols["ACTUAL"]]
    return _calculate_sales_trend(trend_series, year)


def get_actual_category_sales_trend(
    repository: ForecastRepository,
    year: int,
    month: int,
    category: str,
) -> Dict[str, Any]:
    """
    Analyze actual sales trend for a product category and return JSON output.
    """
    series = repository.get_actual_category(year, month, category)
    if series.empty:
        return _calculate_sales_trend(pd.Series(dtype="float64"))

    trend_series = series.set_index(repository.cols["WEEK"])[repository.cols["ACTUAL"]]
    return _calculate_sales_trend(trend_series, year)


def get_actual_sku_sales_trend(
    repository: ForecastRepository,
    year: int,
    month: int,
    sku: str,
) -> Dict[str, Any]:
    """
    Analyze actual sales trend for a SKU and return JSON output.
    """
    series = repository.get_actual_sku(year, month, sku)
    if series.empty:
        return _calculate_sales_trend(pd.Series(dtype="float64"))

    trend_series = series.set_index(repository.cols["WEEK"])[repository.cols["ACTUAL"]]
    return _calculate_sales_trend(trend_series, year)


def get_actual_key_sales_trend(
    repository: ForecastRepository,
    year: int,
    month: int,
    key: str,
) -> Dict[str, Any]:
    """
    Analyze actual sales trend for a key and return JSON output.
    """
    series = repository.get_actual_key(year, month, key)
    if series.empty:
        return _calculate_sales_trend(pd.Series(dtype="float64"))

    trend_series = series.set_index(repository.cols["WEEK"])[repository.cols["ACTUAL"]]
    return _calculate_sales_trend(trend_series, year)


def _get_forecast_accuracy_summary(
    repository: ForecastRepository,
    year: int,
    month: int,
    entity_type: str,
    entity_value: str,
    forecast_getter: Callable[[int, int, str], pd.DataFrame],
    actual_getter: Callable[[int, int, str], pd.DataFrame],
) -> Dict[str, Any]:
    forecast_df = forecast_getter(year, month, entity_value)
    actual_df = actual_getter(year, month, entity_value)

    if forecast_df.empty or actual_df.empty:
        return {
            "entity_type": entity_type,
            "entity_value": entity_value,
            "year": year,
            "month": month,
            "metrics": {
                "mape": None,
                "mae": None,
                "wmape": None,
                "smape": None,
            },
            "top5_worse_keys": [],
        }

    return {
        "entity_type": entity_type,
        "entity_value": entity_value,
        "year": year,
        "month": month,
        "metrics": {
            "mape": calculate_mape(forecast_df, actual_df),
            "mae": calculate_mae(forecast_df, actual_df),
            "wmape": calculate_wmape(forecast_df, actual_df),
            "smape": calculate_smape(forecast_df, actual_df),
        },
        "top5_worse_keys": calculate_top5_worse_keys(forecast_df, actual_df),
    }


def get_forecast_retailer_accuracy(
    repository: ForecastRepository,
    year: int,
    month: int,
    retailer: str,
) -> Dict[str, Any]:
    """Return forecast accuracy metrics for a retailer using the repository pattern."""
    return _get_forecast_accuracy_summary(
        repository,
        year,
        month,
        "retailer",
        retailer,
        repository.get_forecast_retailer,
        repository.get_actual_retailer,
    )


def get_forecast_category_accuracy(
    repository: ForecastRepository,
    year: int,
    month: int,
    category: str,
) -> Dict[str, Any]:
    """Return forecast accuracy metrics for a category using the repository pattern."""
    return _get_forecast_accuracy_summary(
        repository,
        year,
        month,
        "category",
        category,
        repository.get_forecast_category,
        repository.get_actual_category,
    )


def get_forecast_sku_accuracy(
    repository: ForecastRepository,
    year: int,
    month: int,
    sku: str,
) -> Dict[str, Any]:
    """Return forecast accuracy metrics for a SKU using the repository pattern."""
    return _get_forecast_accuracy_summary(
        repository,
        year,
        month,
        "sku",
        sku,
        repository.get_forecast_sku,
        repository.get_actual_sku,
    )


def get_forecast_key_accuracy(
    repository: ForecastRepository,
    year: int,
    month: int,
    key: str,
) -> Dict[str, Any]:
    """Return forecast accuracy metrics for a key using the repository pattern."""
    return _get_forecast_accuracy_summary(
        repository,
        year,
        month,
        "key",
        key,
        repository.get_forecast_key,
        repository.get_actual_key,
    )
