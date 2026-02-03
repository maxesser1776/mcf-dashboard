import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:  # <-- FIXED: was sys.argv
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.fred import get_fred_connection
import pandas as pd
import requests

fred = get_fred_connection()


# ---------------------------------------------------------
# 1. Fed Balance Sheet (Total Assets - WALCL)
# ---------------------------------------------------------
def fetch_fed_balance_sheet() -> pd.DataFrame:
    """
    Fetch the Federal Reserve balance sheet (total assets) from FRED.

    FRED series: WALCL
    Units from FRED: millions of USD

    We keep it in millions here and convert to billions later in the combined step.
    """
    ser = fred.get_series("WALCL")
    df = ser.to_frame(name="Fed_Balance_Sheet")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df


# ---------------------------------------------------------
# 2. Treasury General Account (TGA) from FiscalData API
# ---------------------------------------------------------
def fetch_tga_balance(start_date: str = "2015-01-01") -> pd.DataFrame:
    """
    Fetch a unified TGA series (legacy + modern) back to at least `start_date`,
    using paginated calls to the FiscalData DTS operating_cash_balance API.

    Returns:
        DataFrame indexed by record_date with a single column:
            - closing_balance (in billions of USD)
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

    # Convert dates and filter to requested start_date
    df["record_date"] = pd.to_datetime(df["record_date"])
    df = df[df["record_date"] >= pd.to_datetime(start_date)]

    # 1) Modern TGA: "Treasury General Account (TGA) Opening Balance"
    modern_mask = df["account_type"] == "Treasury General Account (TGA) Opening Balance"
    modern = df[modern_mask].copy()
    modern["closing_balance"] = pd.to_numeric(modern["open_today_bal"], errors="coerce")

    # 2) Legacy TGA: historically reported as "Federal Reserve Account"
    legacy_mask = df["account_type"] == "Federal Reserve Account"
    legacy = df[legacy_mask].copy()
    legacy["closing_balance"] = pd.to_numeric(legacy["close_today_bal"], errors="coerce")

    # 3) Combine into one unified TGA series
    tga = pd.concat([modern, legacy], axis=0, ignore_index=True)

    # Clean and scale
    tga = tga.dropna(subset=["closing_balance"])
    # FiscalData gives millions → convert to billions
    tga["closing_balance"] = tga["closing_balance"] / 1_000.0

    tga = tga.set_index("record_date").sort_index()
    tga.index.name = "Date"

    return tga[["closing_balance"]]


# ---------------------------------------------------------
# 3. Reverse Repo (RRP) via FRED (series ID: RRPONTSYD)
# ---------------------------------------------------------
def fetch_rrp() -> pd.DataFrame:
    """
    Fetch Reverse Repo usage from FRED.

    FRED series: RRPONTSYD
    Units from FRED: millions of USD (we convert to billions later).
    """
    ser = fred.get_series("RRPONTSYD")
    df = ser.to_frame(name="RRP_Usage")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df


# ---------------------------------------------------------
# 4. Combine into single DataFrame + Net Liquidity / Flows
# ---------------------------------------------------------
def fetch_fed_liquidity_data() -> pd.DataFrame:
    """
    Combine Fed balance sheet, TGA, and RRP into one DataFrame and compute:

    - Fed_Balance_Sheet (billions)
    - TGA_Balance (billions)
    - RRP_Usage (billions)
    - Net_Liquidity (billions) = Fed_Balance_Sheet - TGA_Balance - RRP_Usage
    - Net_Liq_Change_1d / 5d / 20d (billions change over those horizons)
    """
    fed_bs = fetch_fed_balance_sheet()
    tga = fetch_tga_balance()
    rrp = fetch_rrp()

    data = fed_bs.join([tga, rrp], how="outer").sort_index()

    # Ensure a consistent TGA column name
    if "TGA_Balance" not in data.columns and "closing_balance" in data.columns:
        data.rename(columns={"closing_balance": "TGA_Balance"}, inplace=True)

    # --- Ensure consistent units: convert millions → billions for Fed BS and RRP ---
    # WALCL (Fed_Balance_Sheet) and RRPONTSYD (RRP_Usage) come from FRED in millions.
    if "Fed_Balance_Sheet" in data.columns:
        data["Fed_Balance_Sheet"] = data["Fed_Balance_Sheet"] / 1_000.0

    if "RRP_Usage" in data.columns:
        data["RRP_Usage"] = data["RRP_Usage"] / 1_000.0

    # TGA_Balance is already in billions from fetch_tga_balance()

    # --- Net Liquidity and flows ---
    required_cols = {"Fed_Balance_Sheet", "TGA_Balance", "RRP_Usage"}
    if required_cols.issubset(data.columns):
        data["Net_Liquidity"] = (
            data["Fed_Balance_Sheet"].fillna(0)
            - data["TGA_Balance"].fillna(0)
            - data["RRP_Usage"].fillna(0)
        )

        # Liquidity *flows* (billions per day)
        data["Net_Liq_Change_1d"] = data["Net_Liquidity"].diff()
        data["Net_Liq_Change_5d"] = data["Net_Liquidity"].diff(5)
        data["Net_Liq_Change_20d"] = data["Net_Liquidity"].diff(20)

        # --- MASK OUT NET LIQUIDITY BEFORE TGA EXISTS (so charts are clean) ---
        tga_start = data["TGA_Balance"].first_valid_index()
        if tga_start is not None:
            cols_to_mask = [
                "Net_Liquidity",
                "Net_Liq_Change_1d",
                "Net_Liq_Change_5d",
                "Net_Liq_Change_20d",
            ]
            for col in cols_to_mask:
                if col in data.columns:
                    data.loc[data.index < tga_start, col] = None

    else:
        missing = required_cols.difference(data.columns)
        print(f"⚠ Unable to compute Net_Liquidity, missing columns: {missing}")

    return data


# ---------------------------------------------------------
# Main script entry
# ---------------------------------------------------------
if __name__ == "__main__":
    data = fetch_fed_liquidity_data()

    output_dir = PROJECT_ROOT / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "fed_liquidity.csv"
    data.to_csv(output_path)
    print(f"Fed liquidity data saved to: {output_path}.")
