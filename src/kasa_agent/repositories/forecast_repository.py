import pandas as pd
from typing import Dict, Any

from kasa_agent.config import get_config


class ForecastRepository:

    def __init__(self, data):
        self.df = data
        self.cols = get_config()["forecast_columns"]

    def get_forecast_retailer(self, year, month, retailer):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month)
            & (self.df[self.cols["RETAILER"]] == retailer),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["FORECAST"]],
        ]

    def get_forecast_category(self, year, month, category):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month)
            & (self.df[self.cols["PRODUCT_CATEGORY"]] == category),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["FORECAST"]],
        ]

    def get_forecast_retailer_category(self, year, month, retailer, category):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month)
            & (self.df[self.cols["RETAILER"]] == retailer)
            & (self.df[self.cols["PRODUCT_CATEGORY"]] == category),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["FORECAST"]],
        ]

    def get_forecast_sku(self, year, month, sku):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month)
            & (self.df[self.cols["SKU"]] == sku),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["FORECAST"]],
        ]

    def get_forecast_key(self, year, month, key):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month)
            & (self.df[self.cols["KEY"]] == key),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["FORECAST"]],
        ]

    def get_forecast(self, year, month):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["FORECAST"]],
        ]

    def get_actual_retailer(self, year, month, retailer):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month)
            & (self.df[self.cols["RETAILER"]] == retailer),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["ACTUAL"]],
        ]

    def get_actual_retailer_category(self, year, month, retailer, category):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month)
            & (self.df[self.cols["RETAILER"]] == retailer)
            & (self.df[self.cols["PRODUCT_CATEGORY"]] == category),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["ACTUAL"]],
        ]

    def get_actual_category(self, year, month, category):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month)
            & (self.df[self.cols["PRODUCT_CATEGORY"]] == category),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["ACTUAL"]],
        ]

    def get_actual_sku(self, year, month, sku):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month)
            & (self.df[self.cols["SKU"]] == sku),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["ACTUAL"]],
        ]

    def get_actual_key(self, year, month, key):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month)
            & (self.df[self.cols["KEY"]] == key),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["ACTUAL"]],
        ]

    def get_actual(self, year, month):
        return self.df.loc[
            (self.df[self.cols["YEAR"]] == year)
            & (self.df[self.cols["MONTH"]] == month),
            [self.cols["WEEK"],self.cols["KEY"], self.cols["ACTUAL"]],
        ]
