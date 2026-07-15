import pandas as pd
from typing import Dict, Any

from kasa_agent.config import get_config


class DatamartRepository:

    def __init__(self, datamart_df):
        self.df = datamart_df
        self.cols = get_config()["datamart_columns"]
        self.df[self.cols["WEEK_END_DATE"]] = pd.to_datetime(
            self.df[self.cols["WEEK_END_DATE"]]
        )

    # -----------------------------
    # Generic Retrieval
    # -----------------------------

    def get_retailer(self, retailer, start_date, end_date):
        return self.df[
            (self.df[self.cols["RETAILER"]] == retailer)
            & (self.df[self.cols["WEEK_END_DATE"]] >= pd.to_datetime(start_date))
            & (self.df[self.cols["WEEK_END_DATE"]] <= pd.to_datetime(end_date))
        ].copy()

    def get_category(self, category, start_date, end_date):
        return self.df[
            (self.df[self.cols["PRODUCT_CATEGORY"]] == category)
            & (self.df[self.cols["WEEK_END_DATE"]] >= pd.to_datetime(start_date))
            & (self.df[self.cols["WEEK_END_DATE"]] <= pd.to_datetime(end_date))
        ].copy()

    def get_sku(self, sku, start_date, end_date):
        return self.df[
            (self.df[self.cols["SKU"]] == sku)
            & (self.df[self.cols["WEEK_END_DATE"]] >= pd.to_datetime(start_date))
            & (self.df[self.cols["WEEK_END_DATE"]] <= pd.to_datetime(end_date))
        ]

    def get_key(self, key, start_date, end_date):
        return self.df[
            (self.df[self.cols["KEY"]] == key)
            & (self.df[self.cols["WEEK_END_DATE"]] >= pd.to_datetime(start_date))
            & (self.df[self.cols["WEEK_END_DATE"]] <= pd.to_datetime(end_date))
        ]

    def get_retailer_category(self, retailer, category, start_date, end_date):
        return self.df[
            (self.df[self.cols["RETAILER"]] == retailer)
            & (self.df[self.cols["PRODUCT_CATEGORY"]] == category)
            & (self.df[self.cols["WEEK_END_DATE"]] >= pd.to_datetime(start_date))
            & (self.df[self.cols["WEEK_END_DATE"]] <= pd.to_datetime(end_date))
        ].copy()

    def get_sku_history(self, sku, start_date, end_date):
        return self.df[
            (self.cols["SKU"] == sku)
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(start_date))
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(end_date))
        ]

    def get_key_history(self, key, start_date, end_date):
        return self.df[
            (self.cols["KEY"] == key)
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(start_date))
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(end_date))
        ]

    # -----------------------------
    # Time Series
    # -----------------------------

    def get_sales_history(self, start_date, end_date):
        return (
            self.df[
                (self.cols["WEEK_END_DATE"] >= pd.to_datetime(start_date))
                & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(end_date))
            ]
            .groupby(self.cols["WEEK_END_DATE"])[self.cols["POS_UNIT"]]
            .sum()
        )

    def get_price_history(self, key, start_date, end_date):
        return self.df.loc[
            (self.cols["KEY"] == key)
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(start_date))
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(end_date)),
            [self.cols["WEEK_END_DATE"], self.cols["PRICE"]],
        ]

    def get_promo_price_history(self, key, start_date, end_date):
        return self.df.loc[
            (self.cols["KEY"] == key)
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(start_date))
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(end_date)),
            [self.cols["WEEK_END_DATE"], self.cols["PROMO_PRICE"]],
        ]

    def get_discount_history(self, key, start_date, end_date):
        return self.df.loc[
            (self.cols["KEY"] == key)(
                self.cols["WEEK_END_DATE"] >= pd.to_datetime(start_date)
            )
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(end_date)),
            [self.cols["WEEK_END_DATE"], self.cols["DISCOUNT"]],
        ]

    def get_inventory_history(self, key, start_date, end_date):
        """returns out of stock history only applicable for D2C retailer products"""
        if key.split("_")[1] == "D2C":
            return self.df.loc[
                (self.cols["KEY"] == key)(
                    self.cols["WEEK_END_DATE"] >= pd.to_datetime(start_date)
                )
                & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(end_date)),
                [self.cols["WEEK_END_DATE"], self.cols["OUT_OF_STOCK"]],
            ]
        else:
            return None

    def get_holiday_history(self, key, start_date, end_date):

        return self.df.loc[
            (self.cols["KEY"] == key)
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(start_date))
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(end_date)),
            [self.cols["WEEK_END_DATE"], self.cols["HOLIDAY"]],
        ]

    def get_feature_history(self, key, feature, start_date, end_date):

        return self.df.loc[
            (self.cols["KEY"] == key)
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(start_date))
            & (self.cols["WEEK_END_DATE"] >= pd.to_datetime(end_date)),
            [self.cols["WEEK_END_DATE"], feature],
        ]

    # -----------------------------
    # Metadata
    # -----------------------------

    def get_all_retailers(self):
        return self.df[self.cols["RETAILER"]].unique()

    def get_all_categories(self):
        return self.df[self.cols["PRODUCT_CATEGORY"]].unique()

    def get_all_skus(self):
        return self.df[self.cols["SKU"]].unique()

    def get_all_keys(self):
        return self.df[self.cols["KEY"]].unique()
