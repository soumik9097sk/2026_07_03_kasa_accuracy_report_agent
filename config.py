def get_config() -> dict:
    """
    Returns the configuration mapping for datamart, forecast, and actual columns.
    """
    return {
        "datamart_columns": {
            "RETAILER": "CC_RETAILER_NAME",
            "KEY": "KEY",
            "SKU": "D0MATERIAL",
            "POS_UNIT": "POS_UNIT",
            "YEAR": "YEAR",
            "HOLIDAY": "ORGANIC_AND_INORGANIC_HOLIDAYS",
            "PRODUCT_CATEGORY": "D0PRODFAM_T",
            "MONTH": "MONTH",
            "WEEK_END_DATE": "WEEK_END_DATE",
            "MONTH_END_DATE": "MONTH_END_DATE",
            "PRICE": "MAP",
            "PROMO_PRICE": "PMAP/MAP",
            "DISCOUNT": "DISCOUNT_DEPTH",
            "OUT_OF_STOCK": "OUT_OF_STOCK",
            "HOLIDAY": "HOLIDAY",
            "WEEK": "WEEK",
        },
        "forecast_columns": {
            "RETAILER": "CC_RETAILER_NAME",
            "KEY": "KEY",
            "SKU": "SKU",
            "FORECAST": "POS",
            "YEAR": "YEAR",
            "PRODUCT_CATEGORY": "Global Product Family",
            "MONTH": "Month",
            "WEEK": "WEEK",
            "ACTUAL": "Actuals",
        },
    }
