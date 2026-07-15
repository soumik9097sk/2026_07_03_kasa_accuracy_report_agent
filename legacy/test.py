import pandas as pd
import numpy as np


from config import get_config
from repositories.forecast_repository import ForecastRepository
from analyzers.trend import TrendAnalyzer

# Load the datamart data used by the repository
# You can increase nrows if you want more history

df = pd.read_excel(get_config()["data_paths"]["FORECAST_FILE"])

# repo = DatamartRepository(df)
# analyzer = TrendAnalyzer(repo)

# result = analyzer.get_retailer_trend(
#     "AMAZON",
#     "2026-01-12",
#     "2026-01-20",
#     "POS_UNIT",
# )

from analyzers.promotions import PromoAnalyzer
repo = ForecastRepository(df)

# obj = PromoAnalyzer(repo)
# res = obj.get_feature_summary_dict("sku", "K45SSOB", "2025-01-12", "2025-03-20")

from analyzers import analyzer_main
# forecast_df = repo.get_forecast_retailer(2026, 5, 'AMAZON')
# amazon_df = repo.get_actual_retailer(2026, 5, 'AMAZON')
res = analyzer_main._get_forecast_accuracy_summary(repo,2026, 5,'retailer','AMAZON',
  repo.get_forecast_retailer, repo.get_actual_retailer)

print(res)