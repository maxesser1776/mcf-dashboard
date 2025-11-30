import requests
import pandas as pd

# --- 1. Raw pull from FiscalData TGA endpoint ---
def fetch_raw_tga():
    url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
    params = {
        "sort": "-record_date",
        "page[size]": 5000,   # grab a big chunk
    }

    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()["data"]
    df = pd.DataFrame(data)

    return df

if __name__ == "__main__":
    df = fetch_raw_tga()

    print("\n🔹 Columns:")
    print(df.columns.tolist())

    print("\n🔹 First 10 rows:")
    print(df.head(10))

    print("\n🔹 Last 10 rows:")
    print(df.tail(10))

    print("\n🔹 Dtypes:")
    print(df.dtypes)

    print("\n🔹 Date range:")
    print(df["record_date"].min(), "→", df["record_date"].max())

    # Optional: save full raw dump so we can inspect in Excel
    df.to_csv("tga_raw_debug.csv", index=False)
    print("\n💾 Saved full raw TGA dump to tga_raw_debug.csv")
