import pandas as pd
from fredapi import Fred
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.fred import get_fred_connection
fred = get_fred_connection()

# --- 1. Fetch 2-Year and 10-Year Treasury Yields
def fetch_yield_curve():
    t10 = fred.get_series("GS10")  # 10-Year Treasury
    t2 = fred.get_series("GS2")    # 2-Year Treasury

    df = pd.DataFrame({
        "10Y_Yield": t10,
        "2Y_Yield": t2
    })
    df.index = pd.to_datetime(df.index)
    df = df.dropna()
    df["2s10s_Spread"] = df["10Y_Yield"] - df["2Y_Yield"]
    return df

# --- 2. SOFR Rate
def fetch_sofr():
    sofr = fred.get_series("SOFR")
    df = sofr.to_frame(name="SOFR")
    df.index = pd.to_datetime(df.index)
    return df

# --- 3. Combine Yield Curve + SOFR
def fetch_yield_policy_data():
    yc = fetch_yield_curve()
    sofr = fetch_sofr()
    df = yc.join(sofr, how="outer").sort_index()
    return df

if __name__ == "__main__":
    data = fetch_yield_policy_data()
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "yield_curve.csv")
    data.to_csv(output_path)
    print(f"Yield curve and SRF data save to: {output_path}.")
