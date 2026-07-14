import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_config() -> dict:
    """
    Returns the configuration mapping for datamart, forecast, and actual columns.
    """
    return {
        "data_paths": {
            "DATAMART_FILE": os.path.join(
                BASE_DIR,
                "data",
                "DATAMART_FILLNA_3268_KEYS_ALL_FAMILIES_TILL_DEC_2026_20th_Nov_v1_part_12d.csv",
            ),
            "FORECAST_FILE": os.path.join(
                BASE_DIR, "data", "April Snapshot - May Forecasts with Actuals.xlsx"
            ),
        },
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
