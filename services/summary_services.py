import pandas as pd
from typing import Dict, Any

from config import get_config


class SummaryService:
    """
    Service responsible for generating business-level summary statistics.
    """

    def __init__(self, data: pd.DataFrame):
        self.df = data
        self.cols = get_config()["datamart_columns"]

    def get_retailer_summary(self, retailer_name: str) -> Dict[str, Any]:
        """
        Generate summary statistics for a retailer.
        """

        df_retailer = self.df[
            self.df[self.cols["RETAILER"]] == retailer_name
        ]

        if df_retailer.empty:
            return {"error": f"No data found for retailer '{retailer_name}'."}

        total_pos = self.df[self.cols["POS_UNIT"]].sum()
        yearly_pos = (
            self.df.groupby(self.cols["YEAR"])[self.cols["POS_UNIT"]].sum()
        )
        retailer_pos = df_retailer[self.cols["POS_UNIT"]].sum()

        return {
            "retailer": retailer_name,
            "total_skus": df_retailer[self.cols["SKU"]].nunique(),
            "pos_units": retailer_pos,
            "pct_contribution": (
                retailer_pos / total_pos if total_pos else 0
            ),
            "yearly_contribution": (
                df_retailer.groupby(self.cols["YEAR"])[
                    self.cols["POS_UNIT"]
                ].sum()
                / yearly_pos
            ).to_dict(),
            "holidays": (
                df_retailer[self.cols["HOLIDAY"]]
                .dropna()
                .unique()
                .tolist()
            ),
            "product_categories": (
                df_retailer[self.cols["PRODUCT_CATEGORY"]]
                .dropna()
                .unique()
                .tolist()
            ),
            "category_contribution": (
                df_retailer.groupby(self.cols["PRODUCT_CATEGORY"])[
                    self.cols["POS_UNIT"]
                ].sum()
                / retailer_pos
            ).to_dict()
            if retailer_pos
            else {},
        }

    def get_category_summary(self, category_name: str) -> Dict[str, Any]:
        """
        Generate summary statistics for a product category.
        """

        df_category = self.df[
            self.df[self.cols["PRODUCT_CATEGORY"]] == category_name
        ]

        if df_category.empty:
            return {"error": f"No data found for category '{category_name}'."}

        total_pos = self.df[self.cols["POS_UNIT"]].sum()
        yearly_pos = (
            self.df.groupby(self.cols["YEAR"])[self.cols["POS_UNIT"]].sum()
        )
        category_pos = df_category[self.cols["POS_UNIT"]].sum()

        return {
            "category": category_name,
            "total_skus": df_category[self.cols["SKU"]].nunique(),
            "pos_units": category_pos,
            "pct_contribution": (
                category_pos / total_pos if total_pos else 0
            ),
            "yearly_contribution": (
                df_category.groupby(self.cols["YEAR"])[
                    self.cols["POS_UNIT"]
                ].sum()
                / yearly_pos
            ).to_dict(),
        }

    def get_category_retailer_summary(
        self,
        category_name: str,
        retailer_name: str,
    ) -> Dict[str, Any]:
        """
        Generate summary statistics for a retailer within a product category.
        """

        df_filtered = self.df[
            (self.df[self.cols["PRODUCT_CATEGORY"]] == category_name)
            & (self.df[self.cols["RETAILER"]] == retailer_name)
        ]

        if df_filtered.empty:
            return {
                "error": (
                    f"No data found for retailer '{retailer_name}' "
                    f"and category '{category_name}'."
                )
            }

        total_pos = self.df[self.cols["POS_UNIT"]].sum()
        yearly_pos = (
            self.df.groupby(self.cols["YEAR"])[self.cols["POS_UNIT"]].sum()
        )
        filtered_pos = df_filtered[self.cols["POS_UNIT"]].sum()

        return {
            "retailer": retailer_name,
            "category": category_name,
            "total_skus": df_filtered[self.cols["SKU"]].nunique(),
            "pos_units": filtered_pos,
            "pct_contribution": (
                filtered_pos / total_pos if total_pos else 0
            ),
            "yearly_contribution": (
                df_filtered.groupby(self.cols["YEAR"])[
                    self.cols["POS_UNIT"]
                ].sum()
                / yearly_pos
            ).to_dict(),
            "holidays": (
                df_filtered[self.cols["HOLIDAY"]]
                .dropna()
                .unique()
                .tolist()
            ),
            "category_distribution": (
                df_filtered.groupby(self.cols["PRODUCT_CATEGORY"])[
                    self.cols["POS_UNIT"]
                ].sum()
                / filtered_pos
            ).to_dict()
            if filtered_pos
            else {},
        }
