from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from repositories.datamart_repository import DatamartRepository


class TrendAnalyzer:
    """Create trend-based analysis for retailer, category, SKU, and key-level data."""

    def __init__(self, repository: DatamartRepository):
        self.repository = repository

    def _get_level_frame(
        self, level: str, identifier: str, start_date: str, end_date: str
    ):
        level_key = level.lower().replace(" ", "_")
        if level_key == "retailer":
            return self.repository.get_retailer(identifier, start_date, end_date)
        if level_key == "product_category":
            return self.repository.get_category(identifier, start_date, end_date)
        if level_key == "sku":
            return self.repository.get_sku(identifier, start_date, end_date)
        if level_key == "key":
            return self.repository.get_key(identifier, start_date, end_date)
        raise ValueError(f"Unsupported level: {level}")

    def get_level_trend(
        self,
        level: str,
        identifier: str,
        start_date: str,
        end_date: str,
        metric_col: str = "POS_UNIT",
    ) -> pd.Series:
        frame = self._get_level_frame(level, identifier, start_date, end_date)
        if frame.empty:
            return pd.Series(dtype="float64")

        date_col = self.repository.cols["WEEK_END_DATE"]
        if metric_col not in frame.columns:
            raise KeyError(f"Metric column '{metric_col}' is not available in the data")

        return (
            frame.groupby(frame[date_col])[metric_col]
            .sum()
            .sort_index()
            .rename(f"{level.lower()}_{identifier}_trend")
        )

    def get_retailer_trend(
        self,
        retailer: str,
        start_date: str,
        end_date: str,
        metric_col: str = "POS_UNIT",
    ) -> pd.Series:
        return self.get_level_trend(
            "retailer", retailer, start_date, end_date, metric_col
        )

    def get_category_trend(
        self,
        category: str,
        start_date: str,
        end_date: str,
        metric_col: str = "POS_UNIT",
    ) -> pd.Series:
        return self.get_level_trend(
            "product_category", category, start_date, end_date, metric_col
        )

    def get_sku_trend(
        self, sku: str, start_date: str, end_date: str, metric_col: str = "POS_UNIT"
    ) -> pd.Series:
        return self.get_level_trend("sku", sku, start_date, end_date, metric_col)

    def get_key_trend(
        self, key: str, start_date: str, end_date: str, metric_col: str = "POS_UNIT"
    ) -> pd.Series:
        return self.get_level_trend("key", key, start_date, end_date, metric_col)

    def get_trend_summary(self, series: pd.Series) -> Dict[str, Any]:
        clean_series = pd.Series(series, dtype="float64").dropna()
        if clean_series.empty:
            return {
                "count": 0,
                "total": 0.0,
                "average": 0.0,
                "max": 0.0,
                "min": 0.0,
                "latest": 0.0,
                "growth_pct": 0.0,
                "direction": "flat",
            }

        growth_pct = 0.0
        if len(clean_series) > 1:
            growth_pct = (
                float(clean_series.pct_change().dropna().iloc[-1])
                if not clean_series.pct_change().dropna().empty
                else 0.0
            )

        if clean_series.iloc[-1] > clean_series.iloc[0]:
            direction = "upward"
        elif clean_series.iloc[-1] < clean_series.iloc[0]:
            direction = "downward"
        else:
            direction = "flat"

        return {
            "count": int(clean_series.count()),
            "total": float(clean_series.sum()),
            "average": float(clean_series.mean()),
            "max": float(clean_series.max()),
            "min": float(clean_series.min()),
            "latest": float(clean_series.iloc[-1]),
            "growth_pct": growth_pct,
            "direction": direction,
        }

    def get_level_trend_summary(
        self,
        level: str,
        identifier: str,
        start_date: str,
        end_date: str,
        metric_col: str = "POS_UNIT",
    ) -> Dict[str, Any]:
        series = self.get_level_trend(
            level, identifier, start_date, end_date, metric_col
        )
        return self.get_trend_summary(series)

    def get_moving_average(self, series: pd.Series, window: int = 4) -> pd.Series:
        return series.rolling(window=window, min_periods=1).mean()

    def get_growth_rate(self, series: pd.Series, periods: int = 1) -> pd.Series:
        return series.pct_change(periods=periods)

    def get_peak_week(self, series: pd.Series) -> Optional[Dict[str, Any]]:
        if series.empty:
            return None
        idx = series.idxmax()
        return {"date": idx, "value": float(series.loc[idx])}
