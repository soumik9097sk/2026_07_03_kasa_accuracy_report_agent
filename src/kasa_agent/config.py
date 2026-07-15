import os

# src/kasa_agent/config.py -> project root is two levels above the package dir.
# This holds for a source checkout or editable install; for a wheel/container
# deployment, point KASA_DATA_DIR / KASA_OUTPUT_DIR at real locations instead.
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)

DATA_DIR = os.environ.get("KASA_DATA_DIR", os.path.join(BASE_DIR, "data"))
OUTPUT_DIR = os.environ.get("KASA_OUTPUT_DIR", os.path.join(BASE_DIR, "output"))


def get_config() -> dict:
    """
    Returns the configuration mapping for datamart, forecast, and actual columns.

    File locations resolve in this order: explicit KASA_DATAMART_FILE /
    KASA_FORECAST_FILE env vars, else the default filenames under DATA_DIR
    (itself overridable via KASA_DATA_DIR).
    """
    return {
        "data_paths": {
            "DATAMART_FILE": os.environ.get(
                "KASA_DATAMART_FILE",
                os.path.join(DATA_DIR, "amazon_all.csv"),
            ),
            "FORECAST_FILE": os.environ.get(
                "KASA_FORECAST_FILE",
                os.path.join(
                    DATA_DIR, "April Snapshot - May Forecasts with Actuals.xlsx"
                ),
            ),
        },
        "datamart_columns": {
            "RETAILER": "CC_RETAILER_NAME",
            "KEY": "KEY",
            "SKU": "D0MATERIAL",
            "POS_UNIT": "POS_UNIT",
            "YEAR": "YEAR",
            "HOLIDAY": "ORGANIC_AND_INORGANIC_HOLIDAYS",
            "PRODUCT_CATEGORY": "D0GPRODFAM_T",
            "MONTH": "MONTH_NUMBER",
            "WEEK_END_DATE": "WEEK_END_DATE",
            # "MONTH_END_DATE": "MONTH_END_DATE",
            "PRICE": "MAP",
            "PROMO_PRICE": "PMAP/MAP",
            "DISCOUNT": "DISCOUNT_DEPTH",
            # "OUT_OF_STOCK": "OUT_OF_STOCK",
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
