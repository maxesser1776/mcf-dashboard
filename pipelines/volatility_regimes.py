# pipelines/volatility_regimes.py

import os
import sys
from datetime import datetime

import pandas as pd
import yfinance as yf

# Ensure project root on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _fetch_vix_series():
    """
    Fetch VIX and 3M VIX from Yahoo Finance and return a clean DataFrame with:
      - VIX_Short   (front-month VIX)
      - VIX_3M      (3-month VIX)
      - VIX_Term_Ratio = VIX_Short / VIX_3M

    All on a Date index.
    """
    tickers = ["^VIX", "^VIX3M"]
    start = "2010-01-01"  # enough history for z-scores / regimes

    print(f"Downloading volatility indices: {tickers}")
    raw = yf.download(tickers, start=start, group_by="ticker", auto_adjust=False)

    if raw.empty:
        raise RuntimeError("No VIX data returned from Yahoo Finance.")

    frames = []

    for tkr, col_name in [("^VIX", "VIX_Short"), ("^VIX3M", "VIX_3M")]:
        df = raw.copy()

        price_col = None
        for candidate in [(tkr, "Adj Close"), (tkr, "Close")]:
            if candidate in df.columns:
                price_col = candidate
                break

        if price_col is None:
            print(f"⚠️ Could not find price column for {tkr}. Available: {df.columns.tolist()}")
            continue

        sub = df[[price_col]].copy()
        sub.columns = [col_name]
        frames.append(sub)

    if not frames:
        raise RuntimeError("No usable VIX columns found.")

    vol = pd.concat(frames, axis=1)
    vol.index = pd.to_datetime(vol.index)
    vol.index.name = "Date"

    # Drop rows where both are NaN
    vol = vol.dropna(how="all")

    # Compute term structure: short / 3M
    if "VIX_Short" in vol.columns and "VIX_3M" in vol.columns:
        vol["VIX_Term_Ratio"] = vol["VIX_Short"] / vol["VIX_3M"]
    else:
        vol["VIX_Term_Ratio"] = pd.NA

    # Optional smoothing for nicer plots
    vol["VIX_Short_SMA5"] = vol["VIX_Short"].rolling(5).mean()
    vol["VIX_Term_Ratio_SMA5"] = vol["VIX_Term_Ratio"].rolling(5).mean()

    return vol


if __name__ == "__main__":
    vol = _fetch_vix_series()

    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, "volatility_regimes.csv")
    vol.to_csv(out_path)
    print(f"Volatility regimes data saved to: {out_path}")
