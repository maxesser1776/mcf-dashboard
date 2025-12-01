import yfinance as yf
import pandas as pd
from datetime import datetime
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# --- Fetch DXY Index from ETF Proxy ---
def fetch_dxy():
    dxy = yf.download("UUP", start="2015-01-01", auto_adjust=False)
    price_col = "Adj Close" if "Adj Close" in dxy.columns else "Close"
    df = dxy[[price_col]].copy()
    df.columns = ["DXY"]
    # yfinance already uses a DatetimeIndex named "Date" here
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    return df


# --- Fetch EM FX pairs with correct MultiIndex handling ---
def fetch_em_fx():
    # Same three EM FX pairs you already use
    symbols = ["USDZAR=X", "USDTRY=X", "USDCLP=X"]
    fx_frames = []

    for symbol in symbols:
        print(f"\n📥 Downloading {symbol}...")
        raw = yf.download(symbol, start="2015-01-01", group_by="ticker", auto_adjust=False)

        if raw.empty:
            print(f"⚠️ {symbol} returned empty data. Skipping.")
            continue

        # Look for ('TICKER', 'Adj Close') or ('TICKER', 'Close') in MultiIndex
        price_col = None
        for candidate in [(symbol, "Adj Close"), (symbol, "Close")]:
            if candidate in raw.columns:
                price_col = candidate
                break

        if price_col:
            df = raw[[price_col]].copy()
            df.columns = [symbol]  # flatten to symbol name
            df.index = pd.to_datetime(df.index)
            df.index.name = "Date"
            fx_frames.append(df)
        else:
            print(f"⚠️ {symbol} has no usable price column. Available: {raw.columns.tolist()}")

    if not fx_frames:
        raise ValueError("❌ No usable EM FX data retrieved.")

    combined = pd.concat(fx_frames, axis=1).dropna(how="all")
    combined.index = pd.to_datetime(combined.index)
    combined.index.name = "Date"
    return combined


# --- Combine All FX Liquidity Proxies & Build EM FX Basket ---
def fetch_fx_liquidity():
    dxy = fetch_dxy()
    em = fetch_em_fx()

    df = dxy.join(em, how="outer").sort_index()
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"

    # Build EM FX Basket:
    # USDZAR=X, USDTRY=X, USDCLP=X go UP when USD strengthens vs EM.
    # We want an index where UP = EM strength (i.e. easing stress),
    # so take the negative of the % change (i.e. -dPrice/Price).
    em_cols = [c for c in ["USDZAR=X", "USDTRY=X", "USDCLP=X"] if c in df.columns]

    if em_cols:
        em_returns = df[em_cols].pct_change()
        em_strength = -em_returns.mean(axis=1)       # inverse USD strength
        df["EM_FX_Basket"] = em_strength.rolling(5).mean()
    else:
        print("⚠️ No EM FX columns found to build EM_FX_Basket.")

    return df


if __name__ == "__main__":
    data = fetch_fx_liquidity()

    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "fx_liquidity.csv")
    data.to_csv(output_path)
    print(f"FX liquidity data saved to: {output_path}.")
