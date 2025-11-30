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
import requests
import pandas as pd

def fetch_tga_balance(start_date="2015-01-01"):
    """
    Fetch a unified TGA series (legacy + modern) back to at least `start_date`,
    using paginated calls to the FiscalData DTS operating_cash_balance API.
    Returns a DataFrame indexed by date with a single column: 'closing_balance'
    in USD billions.
    """
    base_url = (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
        "v1/accounting/dts/operating_cash_balance"
    )

    all_pages = []
    page = 1
    page_size = 5000

    while True:
        params = {
            "sort": "-record_date",        # newest → oldest
            "page[size]": page_size,
            "page[number]": page,
        }

        resp = requests.get(base_url, params=params)
        if resp.status_code != 200:
            raise ValueError(f"TGA API error {resp.status_code}: {resp.text[:300]}")

        data = resp.json().get("data", [])
        if not data:
            break  # no more pages

        df_page = pd.DataFrame(data)
        all_pages.append(df_page)

        # If we got fewer than page_size rows, we've reached the end
        if len(data) < page_size:
            break

        page += 1

    if not all_pages:
        raise ValueError("No TGA data retrieved from FiscalData API.")

    df = pd.concat(all_pages, ignore_index=True)
    print(f"Fetched {len(df)} DTS rows across {page} pages")

    # ── convert dates and filter to requested start_date
    df["record_date"] = pd.to_datetime(df["record_date"])
    df = df[df["record_date"] >= pd.to_datetime(start_date)]

    # ── 1) Modern TGA: "Treasury General Account (TGA) Opening Balance"
    modern_mask = df["account_type"] == "Treasury General Account (TGA) Opening Balance"
    modern = df[modern_mask].copy()
    modern["closing_balance"] = pd.to_numeric(modern["open_today_bal"], errors="coerce")

    # ── 2) Legacy TGA: historically reported as "Federal Reserve Account"
    legacy_mask = df["account_type"] == "Federal Reserve Account"
    legacy = df[legacy_mask].copy()
    legacy["closing_balance"] = pd.to_numeric(legacy["close_today_bal"], errors="coerce")

    # ── 3) Combine into one unified TGA series
    tga = pd.concat([modern, legacy], axis=0, ignore_index=True)

    # clean and scale
    tga = tga.dropna(subset=["closing_balance"])
    tga["closing_balance"] = tga["closing_balance"] / 1_000  # millions → billions

    tga = tga.set_index("record_date").sort_index()

    return tga[["closing_balance"]]

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
