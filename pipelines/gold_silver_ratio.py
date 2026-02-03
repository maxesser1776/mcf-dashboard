import os
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def fetch_gold_silver_ratio(start: str = "2005-01-01") -> pd.DataFrame:
    """
    Fetch COMEX gold and silver futures from Yahoo Finance and compute:

        Gold_Silver_Ratio = GC=F / SI=F

    Tickers:
      - GC=F : Gold futures (USD/oz)
      - SI=F : Silver futures (USD/oz)

    Output index: Date
    Columns:
      - Gold
      - Silver
      - Gold_Silver_Ratio
    """
    tickers = ["GC=F", "SI=F"]

    # group_by="ticker" gives MultiIndex columns: (ticker, field)
    raw = yf.download(
        tickers,
        start=start,
        auto_adjust=False,
        group_by="ticker",
    )

    if raw.empty:
        raise RuntimeError("No data returned from Yahoo Finance for GC=F / SI=F.")

    frames = []
    mapping = [
        ("GC=F", "Gold"),
        ("SI=F", "Silver"),
    ]

    for tkr, out_name in mapping:
        df = raw.copy()

        price_col = None
        # Try ('TICKER', 'Adj Close') then ('TICKER', 'Close')
        if isinstance(df.columns, pd.MultiIndex):
            for candidate in [(tkr, "Adj Close"), (tkr, "Close")]:
                if candidate in df.columns:
                    price_col = candidate
                    break
        else:
            # Flat columns fallback – look for ticker name directly
            if tkr in df.columns:
                price_col = tkr

        if price_col is None:
            print(f"⚠️ Could not find price column for {tkr}. Available: {df.columns.tolist()}")
            continue

        sub = df[[price_col]].copy()
        sub.columns = [out_name]
        frames.append(sub)

    if not frames:
        raise RuntimeError("No usable Gold/Silver price columns found in downloaded data.")

    out = pd.concat(frames, axis=1)
    out.index = pd.to_datetime(out.index)
    out.index.name = "Date"
    out = out.dropna(how="all")

    if {"Gold", "Silver"}.issubset(out.columns):
        out["Gold_Silver_Ratio"] = out["Gold"] / out["Silver"]
    else:
        out["Gold_Silver_Ratio"] = pd.NA

    return out


if __name__ == "__main__":
    data = fetch_gold_silver_ratio()

    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "gold_silver_ratio.csv")
    data.to_csv(output_path)
    print(f"GSR data saved to: {output_path}.")
