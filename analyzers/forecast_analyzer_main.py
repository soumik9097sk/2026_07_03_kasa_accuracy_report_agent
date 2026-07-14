from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from config import get_config


def _resolve_forecast_columns(
    forecast_col: str | None = None,
    actual_col: str | None = None,
    key_col: str | None = None,
    week_col: str | None = None,
) -> tuple[str, str, str, str]:
    columns = get_config()["forecast_columns"]
    return (
        forecast_col or columns["FORECAST"],
        actual_col or columns["ACTUAL"],
        key_col or columns["KEY"],
        week_col or columns["WEEK"],
    )


def _validate_metric_frame(
    df: pd.DataFrame, value_col: str, key_col: str, week_col: str
) -> pd.DataFrame:
    required = {value_col, key_col, week_col}
    if not required.issubset(df.columns):
        missing = sorted(required - set(df.columns))
        raise ValueError(f"Missing required columns: {missing}")
    return df.copy()


def _align_forecast_actual(
    forecast_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    forecast_col: str | None = None,
    actual_col: str | None = None,
    key_col: str | None = None,
    week_col: str | None = None,
) -> pd.DataFrame:
    forecast_col, actual_col, key_col, week_col = _resolve_forecast_columns(
        forecast_col, actual_col, key_col, week_col
    )
    forecast_df = _validate_metric_frame(forecast_df, forecast_col, key_col, week_col)
    actual_df = _validate_metric_frame(actual_df, actual_col, key_col, week_col)

    if key_col not in forecast_df.columns or key_col not in actual_df.columns:
        raise ValueError(f"Missing key column: {key_col}")
    if week_col not in forecast_df.columns or week_col not in actual_df.columns:
        raise ValueError(f"Missing week column: {week_col}")

    merged = forecast_df[[week_col, key_col, forecast_col]].merge(
        actual_df[[week_col, key_col, actual_col]],
        on=[week_col, key_col],
        how="inner",
        suffixes=("_forecast", "_actual"),
    )

    if merged.empty:
        return pd.DataFrame(columns=[week_col, key_col, "forecast", "actual"])

    forecast_value_col = (
        f"{forecast_col}_forecast"
        if f"{forecast_col}_forecast" in merged.columns
        else forecast_col
    )
    actual_value_col = (
        f"{actual_col}_actual"
        if f"{actual_col}_actual" in merged.columns
        else actual_col
    )
    merged["forecast"] = pd.to_numeric(merged[forecast_value_col], errors="coerce")
    merged["actual"] = pd.to_numeric(merged[actual_value_col], errors="coerce")
    return merged[[week_col, key_col, "forecast", "actual"]].dropna()


def calculate_mape(
    forecast_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    forecast_col: str | None = None,
    actual_col: str | None = None,
    key_col: str | None = None,
    week_col: str | None = None,
) -> float:
    """
    Calculate MAPE from two dataframes that each contain at least:
    WEEK, KEY and one numeric forecast/actual value column.
    """
    merged = _align_forecast_actual(
        forecast_df, actual_df, forecast_col, actual_col, key_col, week_col
    )
    if merged.empty:
        return float("nan")

    abs_actual = np.abs(merged["actual"].to_numpy(dtype=float))
    abs_error = np.abs(
        merged["actual"].to_numpy(dtype=float)
        - merged["forecast"].to_numpy(dtype=float)
    )
    denom = np.where(abs_actual == 0, np.nan, abs_actual)
    if np.isnan(denom).all():
        return float("nan")
    return float(np.mean((abs_error / denom) * 100))


def calculate_mae(
    forecast_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    forecast_col: str | None = None,
    actual_col: str | None = None,
    key_col: str | None = None,
    week_col: str | None = None,
) -> float:
    """Calculate Mean Absolute Error (MAE) across aligned WEEK/KEY rows."""
    merged = _align_forecast_actual(
        forecast_df, actual_df, forecast_col, actual_col, key_col, week_col
    )
    if merged.empty:
        return float("nan")

    return float(
        np.mean(
            np.abs(
                merged["actual"].to_numpy(dtype=float)
                - merged["forecast"].to_numpy(dtype=float)
            )
        )
    )


def calculate_wmape(
    forecast_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    forecast_col: str | None = None,
    actual_col: str | None = None,
    key_col: str | None = None,
    week_col: str | None = None,
) -> float:
    """Calculate Weighted MAPE (WMAPE) across aligned WEEK/KEY rows."""
    merged = _align_forecast_actual(
        forecast_df, actual_df, forecast_col, actual_col, key_col, week_col
    )
    if merged.empty:
        return float("nan")

    abs_actual = np.abs(merged["actual"].to_numpy(dtype=float))
    abs_error = np.abs(
        merged["actual"].to_numpy(dtype=float)
        - merged["forecast"].to_numpy(dtype=float)
    )
    denom = abs_actual.sum()
    if denom == 0:
        return float("nan")
    return float(np.sum(abs_error) / denom * 100)


def calculate_smape(
    forecast_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    forecast_col: str | None = None,
    actual_col: str | None = None,
    key_col: str | None = None,
    week_col: str | None = None,
) -> float:
    """Calculate Symmetric MAPE (sMAPE) across aligned WEEK/KEY rows."""
    merged = _align_forecast_actual(
        forecast_df, actual_df, forecast_col, actual_col, key_col, week_col
    )
    if merged.empty:
        return float("nan")

    actual = merged["actual"].to_numpy(dtype=float)
    forecast = merged["forecast"].to_numpy(dtype=float)
    abs_error = np.abs(actual - forecast)
    denom = np.abs(actual) + np.abs(forecast)
    denom = np.where(denom == 0, np.nan, denom)
    if np.isnan(denom).all():
        return float("nan")
    return float(np.mean((abs_error / denom) * 100))


def calculate_top5_worse_keys(
    forecast_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    forecast_col: str | None = None,
    actual_col: str | None = None,
    key_col: str | None = None,
    week_col: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Calculate metrics per key and return the worst 5 keys by MAPE.
    If fewer than 5 keys exist, return all available keys.
    """
    forecast_col, actual_col, key_col, week_col = _resolve_forecast_columns(
        forecast_col, actual_col, key_col, week_col
    )
    merged = _align_forecast_actual(
        forecast_df, actual_df, forecast_col, actual_col, key_col, week_col
    )
    if merged.empty:
        return []

    def _metric_summary(group: pd.DataFrame) -> Dict[str, Any]:
        actual = group["actual"].to_numpy(dtype=float)
        forecast = group["forecast"].to_numpy(dtype=float)
        abs_error = np.abs(actual - forecast)
        abs_actual = np.abs(actual)
        mape = np.mean(
            (abs_error / np.where(abs_actual == 0, np.nan, abs_actual)) * 100
        )
        mae = np.mean(abs_error)
        wmape = (
            np.sum(abs_error) / np.sum(abs_actual) * 100
            if np.sum(abs_actual) != 0
            else np.nan
        )
        smape = np.mean(
            (
                abs_error
                / np.where(
                    (abs_actual + np.abs(forecast)) == 0,
                    np.nan,
                    abs_actual + np.abs(forecast),
                )
            )
            * 100
        )
        return {
            "key": str(group[key_col].iloc[0]),
            "mape": float(mape) if not np.isnan(mape) else np.nan,
            "mae": float(mae) if not np.isnan(mae) else np.nan,
            "wmape": float(wmape) if not np.isnan(wmape) else np.nan,
            "smape": float(smape) if not np.isnan(smape) else np.nan,
        }

    summaries = merged.groupby(key_col).apply(_metric_summary).tolist()
    summaries = sorted(summaries, key=lambda item: item.get("mape", float("inf")))
    return summaries[:5]


def calculate_worse_week(
    forecast_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    forecast_col: str | None = None,
    actual_col: str | None = None,
    key_col: str | None = None,
    week_col: str | None = None,
    metric: str = "mape",
) -> Dict[str, Any]:
    """
    Given a single-key dataset, calculate the week with the worst metric.
    The input should contain one unique KEY only.
    """
    forecast_col, actual_col, key_col, week_col = _resolve_forecast_columns(
        forecast_col, actual_col, key_col, week_col
    )
    if forecast_df[key_col].nunique() != 1 or actual_df[key_col].nunique() != 1:
        raise ValueError("Input data should contain exactly one unique KEY")

    merged = _align_forecast_actual(
        forecast_df, actual_df, forecast_col, actual_col, key_col, week_col
    )
    if merged.empty:
        return {"week": None, "metric": None, "value": None}

    actual = merged["actual"].to_numpy(dtype=float)
    forecast = merged["forecast"].to_numpy(dtype=float)
    abs_error = np.abs(actual - forecast)
    abs_actual = np.abs(actual)

    if metric.lower() == "mae":
        metric_values = abs_error
    elif metric.lower() == "wmape":
        metric_values = np.where(abs_actual == 0, np.nan, abs_error / abs_actual * 100)
    elif metric.lower() == "smape":
        denom = np.where(
            (abs_actual + np.abs(forecast)) == 0, np.nan, abs_actual + np.abs(forecast)
        )
        metric_values = np.where(np.isnan(denom), np.nan, abs_error / denom * 100)
    else:
        metric_values = np.where(abs_actual == 0, np.nan, abs_error / abs_actual * 100)

    worst_idx = int(np.nanargmax(metric_values))
    return {
        "week": merged.iloc[worst_idx][week_col],
        "metric": metric.lower(),
        "value": float(metric_values[worst_idx]),
    }
