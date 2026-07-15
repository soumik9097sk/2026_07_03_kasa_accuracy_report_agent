import argparse
import json
import sys

import pandas as pd

from kasa_agent.agents.analyst_agent import generate_accuracy_report
from kasa_agent.agents.ppt_agent import generate_findings_slide
from kasa_agent.config import get_config


def _load_forecast_df() -> pd.DataFrame:
    return pd.read_excel(get_config()["data_paths"]["FORECAST_FILE"])


def _load_datamart_df():
    """Best-effort datamart load -- root-cause drill-down is skipped if this fails."""
    try:
        df = pd.read_csv(get_config()["data_paths"]["DATAMART_FILE"])
    except (FileNotFoundError, OSError) as exc:
        print(f"Warning: could not load datamart data ({exc}); "
              f"continuing with forecast-accuracy data only.", file=sys.stderr)
        return None

    required_cols = set(get_config()["datamart_columns"].values())
    if not required_cols.issubset(df.columns):
        print(
            "Warning: datamart file is missing expected columns (likely a "
            "header-less chunk); continuing with forecast-accuracy data only.",
            file=sys.stderr,
        )
        return None
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a forecast-accuracy report with root-cause reasons."
    )
    parser.add_argument(
        "query",
        nargs="*",
        help='Free-text question, e.g. "why is AMAZON doing bad in month 5 2026"',
    )
    parser.add_argument(
        "--json", action="store_true", help="Print the full structured report as JSON."
    )
    parser.add_argument(
        "--ppt",
        action="store_true",
        help="Also generate a findings slide (.pptx) under output/.",
    )
    args = parser.parse_args()

    query = " ".join(args.query) if args.query else input("Query: ").strip()

    forecast_df = _load_forecast_df()
    datamart_df = _load_datamart_df()

    result = generate_accuracy_report(query, forecast_df, datamart_df)

    if isinstance(result, str):
        print(result)
        return

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result["narrative"])

    if args.ppt:
        slide_path = generate_findings_slide(result)
        print(f"Slide saved to: {slide_path}")


if __name__ == "__main__":
    main()
