# pipelines/volatility_regimes.py

import os
import sys

import pandas as pd
import yfinance as yf

# Ensure project root on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _fetch_vol_series():
    """
    Fetch VIX, 3M VIX, and MOVE Index from Yahoo Finance and return a clean DataFrame with:
      - VIX_Short          (front-month VIX, ^VIX)
      - VIX_3M             (3-month VIX, ^VIX3M)
      - VIX_Term_Ratio     (VIX_Short / VIX_3M)
      - VIX_Short_SMA5
      - VIX_Term_Ratio_SMA5
      - MOVE_Index         (ICE BofAML MOVE Index, ^MOVE)
      - MOVE_SMA20

    Index is Date.
    """
    tickers = ["^VIX", "^VIX3M", "^MOVE"]
    start = "2010-01-01"  # enough history for regimes

    print(f"Downloading volatility indices: {tickers}")
    raw = yf.download(tickers, start=start, group_by="ticker", auto_adjust=False)

    if raw.empty:
        raise RuntimeError("No volatility data returned from Yahoo Finance.")

    frames = []

    mapping = [
        ("^VIX", "VIX_Short"),
        ("^VIX3M", "VIX_3M"),
        ("^MOVE", "MOVE_Index"),
    ]

    for tkr, col_name in mapping:
        df = raw.copy()

        price_col = None
        for candidate in [(tkr, "Adj Close"), (tkr, "Close")]:
            if candidate in df.columns:
                price_col = candidate
                break

        if price_col is None:
            print(f"⚠️ Could not find price column for {tkr}. Available columns: {df.columns.tolist()}")
            continue

        sub = df[[price_col]].copy()
        sub.columns = [col_name]
        frames.append(sub)

    if not frames:
        raise RuntimeError("No usable volatility columns found (VIX / MOVE).")

    vol = pd.concat(frames, axis=1)
    vol.index = pd.to_datetime(vol.index)
    vol.index.name = "Date"

    # Drop rows where all are NaN
    vol = vol.dropna(how="all")

    # Compute VIX term structure: short / 3M
    if "VIX_Short" in vol.columns and "VIX_3M" in vol.columns:
        vol["VIX_Term_Ratio"] = vol["VIX_Short"] / vol["VIX_3M"]
    else:
        vol["VIX_Term_Ratio"] = pd.NA

    # Optional smoothing
    if "VIX_Short" in vol.columns:
        vol["VIX_Short_SMA5"] = vol["VIX_Short"].rolling(5).mean()
    else:
        vol["VIX_Short_SMA5"] = pd.NA

    if "VIX_Term_Ratio" in vol.columns:
        vol["VIX_Term_Ratio_SMA5"] = vol["VIX_Term_Ratio"].rolling(5).mean()
    else:
        vol["VIX_Term_Ratio_SMA5"] = pd.NA

    if "MOVE_Index" in vol.columns:
        vol["MOVE_SMA20"] = vol["MOVE_Index"].rolling(20).mean()
    else:
        vol["MOVE_SMA20"] = pd.NA

    return vol


if __name__ == "__main__":
    vol = _fetch_vol_series()

    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, "volatility_regimes.csv")
    vol.to_csv(out_path)
    print(f"Volatility regimes data saved to: {out_path}")
