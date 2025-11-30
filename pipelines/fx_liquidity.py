import yfinance as yf
import pandas as pd
from datetime import datetime

# --- 1. Fetch DXY (US Dollar Index)
def fetch_dxy():
    dxy = yf.download("DX-Y.NYB", start="2015-01-01")
    df = dxy[["Adj Close"]].rename(columns={"Adj Close": "DXY"})
    df.index = pd.to_datetime(df.index)
    return df

# --- 2. EM FX Spot Currencies (e.g. TRY, ZAR, CLP)
def fetch_em_fx():
    tickers = {
        "TRYUSD=X": "USD/TRY",
        "ZARUSD=X": "USD/ZAR",
        "CLPUSD=X": "USD/CLP"
    }
    fx_data = {}
    for symbol, name in tickers.items():
        df = yf.download(symbol, start="2015-01-01")[["Adj Close"]]
        df.columns = [name]
        fx_data[name] = df
    result = pd.concat(fx_data.values(), axis=1)
    return result

# --- 3. Combine DXY and EM FX
def fetch_fx_liquidity():
    dxy = fetch_dxy()
    em = fetch_em_fx()
    df = dxy.join(em, how="outer").sort_index()
    return df

if __name__ == "__main__":
    data = fetch_fx_liquidity()
    data.to_csv("../data/processed/fx_liquidity.csv")
    print("FX liquidity data updated.")
