import os
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def generate_actual_vs_forecast_chart(
    key_findings: List[Dict[str, Any]],
    title: Optional[str] = None,
    save_path: str = "actual_vs_forecast.png",
) -> str:
    """
    Grouped bar chart with each key on the x-axis and two bars per key
    (Actual, Forecast). `key_findings` is the list produced by
    analyst_agent.generate_accuracy_report() (e.g. the 5 worst keys for a
    retailer/category/month), each item needing "key", "actual_total", and
    "forecast_total". Saves a PNG and returns its path.
    """
    keys = [kf["key"] for kf in key_findings]
    actual_values = [kf["actual_total"] for kf in key_findings]
    forecast_values = [kf["forecast_total"] for kf in key_findings]

    x = np.arange(len(keys))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(6, len(keys) * 1.6), 5))
    ax.bar(x - width / 2, actual_values, width, label="Actual")
    ax.bar(x + width / 2, forecast_values, width, label="Forecast")

    ax.set_xlabel("Key")
    ax.set_ylabel("Units")
    ax.set_title(title or "Actual vs Forecast by Key")
    ax.set_xticks(x)
    ax.set_xticklabels(keys, rotation=30, ha="right")
    ax.legend()
    fig.tight_layout()

    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    return save_path


def generate_chart_from_report(
    report: Dict[str, Any], save_path: str = "actual_vs_forecast.png"
) -> str:
    """
    Convenience wrapper: build the chart directly from a
    generate_accuracy_report() result, using its entity/year/month to build
    the chart title (e.g. "AMAZON / Stand Mixers -- 2026-05 Actual vs Forecast").
    """
    title = (
        f"{report['entity_value']} -- {report['year']}-{report['month']:02d} "
        "Actual vs Forecast"
    )
    return generate_actual_vs_forecast_chart(
        report["key_findings"], title=title, save_path=save_path
    )
