# pipelines/yield_curve.py

import os
import sys
from pathlib import Path
import pandas as pd

# Ensure project root is on sys.path so utils can import correctly
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from utils.fred import get_fred_connection
fred = get_fred_connection()


def fetch_yield_curve():
    """
    Pull modern Treasury constant maturity yields:
    10Y: DGS10
    2Y : DGS2
    3M : DGS3MO (for 3m10y)
    """
    t10 = fred.get_series("DGS10")
    t2 = fred.get_series("DGS2")
    t3m = fred.get_series("DGS3MO")

    df = pd.DataFrame({
        "10Y_Yield": t10,
        "2Y_Yield": t2,
        "3M_Yield": t3m
    })

    df.index = pd.to_datetime(df.index)
    df = df.dropna()

    df["Spread_2s10s"] = df["10Y_Yield"] - df["2Y_Yield"]
    df["Spread_3m10y"] = df["10Y_Yield"] - df["3M_Yield"]
    return df.sort_index()


def fetch_yield_policy_data():
    return fetch_yield_curve()


if __name__ == "__main__":
    df = fetch_yield_policy_data()

    output_dir = BASE_DIR / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "yield_curve.csv"
    df.to_csv(output_path)

    print(f"✔ Saved updated yield curve data: {output_path}")
