import pandas as pd
import requests
from fredapi import Fred
import os

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
    params = {"sort": "record_date", "page[size]": 10000}
    r = requests.get(url, params=params)
    data = r.json()["data"]
    df = pd.DataFrame(data)
    df["record_date"] = pd.to_datetime(df["record_date"])
    df["closing_balance"] = pd.to_numeric(df["closing_balance_millions"])
    df = df[["record_date", "closing_balance"]].set_index("record_date")
    df = df.sort_index()
    df = df.rename(columns={"closing_balance": "TGA_Balance"})
    return df

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
    data.to_csv("../data/processed/fed_liquidity.csv")
    print("Fed liquidity data updated.")
