from __future__ import annotations

from calendar import month_name
from typing import Any, Dict, Optional

import pandas as pd

from kasa_agent.repositories.datamart_repository import DatamartRepository


class SeasonalityAnalyzer:
    """Analyze repeating monthly seasonality for retailer, category, SKU, and key-level data."""

    def __init__(self, repository: DatamartRepository):
        self.repository = repository

    def _get_level_frame(
        self, level: str, identifier: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
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

    def get_level_seasonality(
        self,
        level: str,
        identifier: str,
        start_date: str,
        end_date: str,
        metric_col: str = "POS_UNIT",
        agg: str = "mean",
    ) -> pd.Series:
        frame = self._get_level_frame(level, identifier, start_date, end_date)
        if frame.empty:
            return pd.Series(dtype="float64")

        if metric_col not in frame.columns:
            raise KeyError(f"Metric column '{metric_col}' is not available in the data")

        date_col = self.repository.cols["WEEK_END_DATE"]
        monthly = frame.assign(month=frame[date_col].dt.month).groupby("month")[
            metric_col
        ]

        if agg == "mean":
            monthly_profile = monthly.mean()
        elif agg == "sum":
            monthly_profile = monthly.sum()
        else:
            raise ValueError("agg must be either 'mean' or 'sum'")

        return monthly_profile.reindex(range(1, 13)).rename(
            f"{level.lower()}_{identifier}_seasonality"
        )

    def get_retailer_seasonality(
        self,
        retailer: str,
        start_date: str,
        end_date: str,
        metric_col: str = "POS_UNIT",
        agg: str = "mean",
    ) -> pd.Series:
        return self.get_level_seasonality(
            "retailer", retailer, start_date, end_date, metric_col, agg
        )

    def get_category_seasonality(
        self,
        category: str,
        start_date: str,
        end_date: str,
        metric_col: str = "POS_UNIT",
        agg: str = "mean",
    ) -> pd.Series:
        return self.get_level_seasonality(
            "product_category", category, start_date, end_date, metric_col, agg
        )

    def get_sku_seasonality(
        self,
        sku: str,
        start_date: str,
        end_date: str,
        metric_col: str = "POS_UNIT",
        agg: str = "mean",
    ) -> pd.Series:
        return self.get_level_seasonality(
            "sku", sku, start_date, end_date, metric_col, agg
        )

    def get_key_seasonality(
        self,
        key: str,
        start_date: str,
        end_date: str,
        metric_col: str = "POS_UNIT",
        agg: str = "mean",
    ) -> pd.Series:
        return self.get_level_seasonality(
            "key", key, start_date, end_date, metric_col, agg
        )

    def get_seasonal_index(self, series: pd.Series) -> pd.Series:
        series = pd.Series(series, dtype="float64").dropna()
        if series.empty:
            return pd.Series(dtype="float64")
        avg = series.mean()
        if avg == 0:
            return pd.Series(0.0, index=series.index)
        return series / avg

    def get_peak_month(self, series: pd.Series) -> Optional[Dict[str, Any]]:
        if series.empty:
            return None
        month_num = int(series.idxmax())
        return {
            "month": month_name[month_num],
            "month_number": month_num,
            "value": float(series.loc[month_num]),
        }

    def get_seasonality_summary(self, series: pd.Series) -> Dict[str, Any]:
        clean_series = pd.Series(series, dtype="float64").dropna()
        if clean_series.empty:
            return {
                "count": 0,
                "average": 0.0,
                "peak_month": None,
                "lowest_month": None,
            }

        peak = self.get_peak_month(clean_series)
        low_month = clean_series.idxmin()
        return {
            "count": int(clean_series.count()),
            "average": float(clean_series.mean()),
            "peak_month": peak,
            "lowest_month": {
                "month": month_name[int(low_month)],
                "month_number": int(low_month),
                "value": float(clean_series.loc[low_month]),
            },
        }

    def get_level_seasonality_summary(
        self,
        level: str,
        identifier: str,
        start_date: str,
        end_date: str,
        metric_col: str = "POS_UNIT",
        agg: str = "mean",
    ) -> Dict[str, Any]:
        series = self.get_level_seasonality(
            level, identifier, start_date, end_date, metric_col, agg
        )
        return self.get_seasonality_summary(series)
