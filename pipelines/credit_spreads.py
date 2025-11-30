# pipelines/credit_spreads.py

import os
import sys
from pathlib import Path
import pandas as pd

# Ensure project root is on sys.path so utils imports work
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from utils.fred import get_fred_connection

fred = get_fred_connection()


def fetch_credit_spreads() -> pd.DataFrame:
    """
    Fetch Investment Grade and High Yield option-adjusted spreads from FRED.

    IG:  BAMLC0A0CM   (ICE BofA US Corporate Index OAS, in %)
    HY:  BAMLH0A0HYM2 (ICE BofA US High Yield Index OAS, in %)

    Output columns:
      - IG_OAS   (percent)
      - HY_OAS   (percent)
      - HY_IG_Spread = HY_OAS - IG_OAS (basis points)
    """
    ig = fred.get_series("BAMLC0A0CM")    # Investment Grade OAS
    hy = fred.get_series("BAMLH0A0HYM2")  # High Yield OAS

    df = pd.DataFrame({
        "IG_OAS": ig,
        "HY_OAS": hy,
    })

    # Clean up index and NaNs
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # Drop rows where both series are NaN
    df = df.dropna(how="all")

    # Optional: compute HY-IG spread in bps (if both available)
    if {"IG_OAS", "HY_OAS"}.issubset(df.columns):
        df["HY_IG_Spread"] = (df["HY_OAS"] - df["IG_OAS"]) * 100.0

    return df


if __name__ == "__main__":
    df = fetch_credit_spreads()

    out_dir = BASE_DIR / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "credit_spreads.csv"
    df.to_csv(out_path)

    print(f"✔ Saved credit spreads data to: {out_path}")
