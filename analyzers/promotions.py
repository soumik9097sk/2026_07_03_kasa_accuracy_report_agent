from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import pandas as pd

from repositories.datamart_repository import DatamartRepository


class PromoAnalyzer:
    """Create promo-based analysis for retailer, category, SKU, and key-level data."""

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

    def get_promo_price_trend(self, level, identifier, start_date, end_date):
        frame = self._get_level_frame(level, identifier, start_date, end_date)
        date_col = self.repository.cols["WEEK_END_DATE"]
        feature_col = self.repository.cols["PROMO_PRICE"]
        return (
            frame.groupby(date_col)[feature_col]
            .sum()
            .sort_index()
            .rename(f"{level.lower()}_{feature_col}_trend")
        )

    def get_price_trend(self, level, identifier, start_date, end_date):
        frame = self._get_level_frame(level, identifier, start_date, end_date)
        date_col = self.repository.cols["WEEK_END_DATE"]
        feature_col = self.repository.cols["PRICE"]
        return (
            frame.groupby(date_col)[feature_col]
            .sum()
            .sort_index()
            .rename(f"{level.lower()}_{feature_col}_trend")
        )

    def get_discount_trend(self, level, identifier, start_date, end_date):
        frame = self._get_level_frame(level, identifier, start_date, end_date)
        date_col = self.repository.cols["WEEK_END_DATE"]
        feature_col = self.repository.cols["DISCOUNT"]
        return (
            frame.groupby(date_col)[feature_col]
            .sum()
            .sort_index()
            .rename(f"{level.lower()}_{feature_col}_trend")
        )

    def comp_promo_price_lag52(self, level, identifier, start_date, end_date):
        frame = self._get_level_frame(level, identifier, start_date, end_date)
        frame_lag52 = self._get_level_frame(
            level,
            identifier,
            pd.to_datetime(start_date) - timedelta(weeks=52),
            pd.to_datetime(end_date) - timedelta(weeks=52),
        )
        year_col = self.repository.cols["YEAR"]
        date_col = self.repository.cols["WEEK"]
        feature_col = self.repository.cols["PROMO_PRICE"]
        combined = pd.concat([frame, frame_lag52], ignore_index=True)
        return (
            combined.groupby([date_col, year_col])[feature_col]
            .sum()
            .sort_index()
            .unstack()
        )

    def comp_price_lag52(self, level, identifier, start_date, end_date):
        frame = self._get_level_frame(level, identifier, start_date, end_date)
        frame_lag52 = self._get_level_frame(
            level,
            identifier,
            pd.to_datetime(start_date) - timedelta(weeks=52),
            pd.to_datetime(end_date) - timedelta(weeks=52),
        )
        year_col = self.repository.cols["YEAR"]
        date_col = self.repository.cols["WEEK"]
        feature_col = self.repository.cols["PRICE"]
        combined = pd.concat([frame, frame_lag52], ignore_index=True)
        return (
            combined.groupby([date_col, year_col])[feature_col]
            .sum()
            .sort_index()
            .unstack()
        )

    def comp_discount_lag52(self, level, identifier, start_date, end_date):
        frame = self._get_level_frame(level, identifier, start_date, end_date)
        frame_lag52 = self._get_level_frame(
            level,
            identifier,
            pd.to_datetime(start_date) - timedelta(weeks=52),
            pd.to_datetime(end_date) - timedelta(weeks=52),
        )
        year_col = self.repository.cols["YEAR"]
        date_col = self.repository.cols["WEEK"]
        feature_col = self.repository.cols["DISCOUNT"]
        combined = pd.concat([frame, frame_lag52], ignore_index=True)
        return (
            combined.groupby([date_col, year_col])[feature_col]
            .sum()
            .sort_index()
            .unstack()
        )

    def _summarize_feature(
        self, trend_series: pd.Series, comparison_df: pd.DataFrame
    ) -> Dict[str, Any]:
        if trend_series.empty:
            return {
                "trend": "flat",
                "comp_to_last_year": "same",
                "weekly_comparison": [],
            }

        first_value = float(trend_series.iloc[0])
        last_value = float(trend_series.iloc[-1])
        if last_value < first_value:
            trend = "lower"
        elif last_value > first_value:
            trend = "higher"
        else:
            trend = "flat"

        comparison_df = comparison_df.copy()
        comparison_df.columns = [str(col) for col in comparison_df.columns]
        year_columns = [col for col in comparison_df.columns if col.isdigit()]
        if len(year_columns) < 2:
            comp_to_last_year = "same"
            weekly_comparison = []
        else:
            current_year = year_columns[-1]
            previous_year = year_columns[-2]
            current_series = pd.to_numeric(comparison_df[current_year], errors="coerce")
            previous_series = pd.to_numeric(
                comparison_df[previous_year], errors="coerce"
            )
            current_mean = (
                float(current_series.mean()) if not current_series.empty else 0.0
            )
            previous_mean = (
                float(previous_series.mean()) if not previous_series.empty else 0.0
            )
            if current_mean < previous_mean:
                comp_to_last_year = "decreased"
            elif current_mean > previous_mean:
                comp_to_last_year = "increased"
            else:
                comp_to_last_year = "same"

            weekly_comparison = []
            for week, current_value, previous_value in zip(
                comparison_df.index, current_series, previous_series
            ):
                if pd.isna(current_value) or pd.isna(previous_value):
                    continue
                difference = float(current_value) - float(previous_value)
                if difference < 0:
                    weekly_comparison.append(
                        f"week {week}: decreased by {abs(int(round(difference)))}"
                    )
                elif difference > 0:
                    weekly_comparison.append(
                        f"week {week}: increased by {int(round(difference))}"
                    )
                else:
                    weekly_comparison.append(f"week {week}: no change")

        return {
            "trend": trend,
            "comp_to_last_year": comp_to_last_year,
            "weekly_comparison": weekly_comparison,
        }

    def get_feature_summary_dict(
        self, level: str, identifier: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        return {
            "PROMO_PRICE": self._summarize_feature(
                self.get_promo_price_trend(level, identifier, start_date, end_date),
                self.comp_promo_price_lag52(level, identifier, start_date, end_date),
            ),
            "PRICE": self._summarize_feature(
                self.get_price_trend(level, identifier, start_date, end_date),
                self.comp_price_lag52(level, identifier, start_date, end_date),
            ),
            "DISCOUNT": self._summarize_feature(
                self.get_discount_trend(level, identifier, start_date, end_date),
                self.comp_discount_lag52(level, identifier, start_date, end_date),
            ),
        }
