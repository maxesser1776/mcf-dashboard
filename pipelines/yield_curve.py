# pipelines/yield_curve.py

import os
import sys
import pandas as pd

from fredapi import Fred  # used via utils.fred
from utils.fred import get_fred_connection

fred: Fred = get_fred_connection()

# -----------------------------
# 1. Fetch 2Y, 10Y, and 3M yields
# -----------------------------
def fetch_yield_curve() -> pd.DataFrame:
    # Your original series (constant maturity)
    t10 = fred.get_series("GS10")   # 10-Year Treasury
    t2 = fred.get_series("GS2")     # 2-Year Treasury

    # Add a 3-month proxy for 3m10y spread
    # Common FRED series: TB3MS = 3-Month Treasury Bill, Secondary Market Rate
    t3m = fred.get_series("TB3MS")  # 3-Month Treasury

    df = pd.DataFrame(
        {
            "10Y_Yield": t10,
            "2Y_Yield": t2,
            "3M_Yield": t3m,
        }
    )

    df.index = pd.to_datetime(df.index)
    df = df.dropna()

    # Your original spread (keep it for reference)
    df["2s10s_Spread"] = df["10Y_Yield"] - df["2Y_Yield"]

    # Spreads expected by the dashboard / risk_score
    # Here yields are in percent, so keep spreads in basis points for clarity
    df["Spread_2s10s"] = (df["10Y_Yield"] - df["2Y_Yield"]) * 100.0
    df["Spread_3m10y"] = (df["10Y_Yield"] - df["3M_Yield"]) * 100.0

    return df


# -----------------------------
# 2. SOFR Rate
# -----------------------------
def fetch_sofr() -> pd.DataFrame:
    sofr = fred.get_series("SOFR")
    df = sofr.to_frame(name="SOFR")
    df.index = pd.to_datetime(df.index)
    return df


# -----------------------------
# 3. Combine Yield Curve + SOFR
# -----------------------------
def fetch_yield_policy_data() -> pd.DataFrame:
    yc = fetch_yield_curve()
    sofr = fetch_sofr()
    df = yc.join(sofr, how="outer").sort_index()
    return df


if __name__ == "__main__":
    data = fetch_yield_policy_data()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    output_dir = os.path.join(project_root, "data", "processed")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "yield_curve.csv")
    data.to_csv(output_path)
    print(f"Yield curve and SOFR data saved to: {output_path}")
