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
    return df

# --- Fetch EM FX pairs with correct MultiIndex handling ---
def fetch_em_fx():
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
            fx_frames.append(df)
        else:
            print(f"⚠️ {symbol} has no usable price column. Available: {raw.columns.tolist()}")

    if not fx_frames:
        raise ValueError("❌ No usable EM FX data retrieved.")

    combined = pd.concat(fx_frames, axis=1).dropna(how="all")
    return combined

# --- Combine All FX Liquidity Proxies ---
def fetch_fx_liquidity():
    dxy = fetch_dxy()
    em = fetch_em_fx()
    df = dxy.join(em, how="outer").sort_index()
    return df



if __name__ == "__main__":
    data = fetch_fx_liquidity()
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "fx_liquidity.csv")
    data.to_csv(output_path)
    print(f"FX liquidity data saved to: {output_path}.")
