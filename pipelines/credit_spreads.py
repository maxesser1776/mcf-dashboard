import pandas as pd
from fredapi import Fred
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.fred import get_fred_connection
fred = get_fred_connection()

# --- 1. High-Yield OAS (Option-Adjusted Spread)
def fetch_high_yield_oas():
    df = fred.get_series("BAMLH0A0HYM2")  # ICE BofA US High Yield Index OAS
    df = df.to_frame(name="High_Yield_OAS")
    df.index = pd.to_datetime(df.index)
    return df

# --- 2. Investment Grade OAS
def fetch_ig_oas():
    df = fred.get_series("BAMLC0A0CM")  # ICE BofA US Corporate Index OAS
    df = df.to_frame(name="IG_OAS")
    df.index = pd.to_datetime(df.index)
    return df

# --- 3. Credit Spread Differential (HY - IG)
def fetch_credit_spreads():
    hy = fetch_high_yield_oas()
    ig = fetch_ig_oas()
    df = hy.join(ig, how="outer")
    df["HY_IG_Spread"] = df["High_Yield_OAS"] - df["IG_OAS"]
    return df

if __name__ == "__main__":
    data = fetch_credit_spreads()
    data.to_csv("../data/processed/credit_spreads.csv")
    print("Credit spread data updated.")