# pipelines/growth_leading.py

import os
import sys

import pandas as pd

# Make sure the project root is on sys.path (same pattern as other pipelines)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.fred import get_fred_connection

# Shared FRED client
fred = get_fred_connection()


def fetch_orders_inventories_spread():
    """
    Fetch a proxy for the ISM New Orders - Inventories spread using FRED series:

      - AMTMNO : Manufacturers' New Orders: Total Manufacturing (millions, SA)
      - AMTMTI : Manufacturers' Total Inventories: Total Manufacturing (millions)

    We then compute:
      - Orders_YoY       : YoY % change in new orders
      - Inventories_YoY  : YoY % change in inventories
      - ISM_Spread       : Orders_YoY - Inventories_YoY

    This acts as a forward-looking growth indicator:
      * Strong orders growth vs inventories => positive spread (risk-on)
      * Weak orders growth vs inventories  => negative spread (risk-off)
    """
    series_orders = "AMTMNO"  # Manufacturers' New Orders: Total Manufacturing
    series_inventories = "AMTMTI"  # Manufacturers' Total Inventories: Total Manufacturing

    print(f"Fetching Manufacturers' New Orders ({series_orders}) from FRED...")
    orders = fred.get_series(series_orders).to_frame("Mfg_New_Orders")

    print(f"Fetching Manufacturers' Total Inventories ({series_inventories}) from FRED...")
    inventories = fred.get_series(series_inventories).to_frame("Mfg_Total_Inventories")

    df = orders.join(inventories, how="outer")
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"

    # Year-over-year growth rates
    df["Orders_YoY"] = df["Mfg_New_Orders"].pct_change(12) * 100.0
    df["Inventories_YoY"] = df["Mfg_Total_Inventories"].pct_change(12) * 100.0

    # Our "ISM-style" spread proxy
    df["ISM_Spread"] = df["Orders_YoY"] - df["Inventories_YoY"]

    return df


def fetch_initial_claims():
    """
    Fetch Initial Unemployment Claims (ICSA) from FRED and compute a 4-week moving average.
    """
    series_claims = "ICSA"  # Initial Claims, SA, weekly

    print(f"Fetching Initial Claims ({series_claims}) from FRED...")
    claims = fred.get_series(series_claims).to_frame("Initial_Claims")
    claims.index = pd.to_datetime(claims.index)
    claims.index.name = "Date"

    # 4-week moving average smooths noise
    claims["Initial_Claims_4WMA"] = claims["Initial_Claims"].rolling(window=4).mean()

    return claims


if __name__ == "__main__":
    # Orders vs inventories (monthly) and claims (weekly)
    orders_inv_df = fetch_orders_inventories_spread()
    claims_df = fetch_initial_claims()

    print("Merging Orders/Inventories spread and Initial Claims into growth_leading dataset...")
    combined = orders_inv_df.join(claims_df, how="outer").sort_index()

    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "growth_leading.csv")
    combined.to_csv(output_path)
    print(f"Growth leading indicators saved to: {output_path}")
