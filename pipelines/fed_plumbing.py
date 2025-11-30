import pandas as pd
import requests
from fredapi import Fred
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.fred import get_fred_connection
fred = get_fred_connection()

# --- 1. Fed Balance Sheet (Total Assets - WALCL)
def fetch_fed_balance_sheet():
    df = fred.get_series("WALCL")
    df = df.to_frame(name="Fed_Balance_Sheet")
    df.index = pd.to_datetime(df.index)
    return df

# --- 2. Treasury General Account (TGA) from FiscalData API
def fetch_tga_balance():
    url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
    params = {"sort": "-record_date", "page[size]": 5000}

    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise ValueError(f"TGA API error {response.status_code}: {response.text[:300]}")

    data = response.json()["data"]
    df = pd.DataFrame(data)
    print("TGA Columns:", df.columns.tolist())  # for future debugging

    df["closing_balance"] = pd.to_numeric(df["close_today_bal"], errors="coerce")  # ✅ use actual field
    df = df.dropna(subset=["closing_balance"])
    df["record_date"] = pd.to_datetime(df["record_date"])
    df = df.set_index("record_date").sort_index()

    return df[["closing_balance"]]


# --- 3. Reverse Repo (RRP) via FRED (series ID: RRPONTSYD)
def fetch_rrp():
    df = fred.get_series("RRPONTSYD")
    df = df.to_frame(name="RRP_Usage")
    df.index = pd.to_datetime(df.index)
    return df

# --- 4. Combine all into single DataFrame
def fetch_fed_liquidity_data():
    fed_bs = fetch_fed_balance_sheet()
    tga = fetch_tga_balance()
    rrp = fetch_rrp()
    df = fed_bs.join([tga, rrp], how="outer").sort_index()
    return df

if __name__ == "__main__":
    data = fetch_fed_liquidity_data()
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "fed_liquidity.csv")
    data.to_csv(output_path)
    print(f"Fed liquidity data saved to: {output_path}.")
