import pandas as pd
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.fred import get_fred_connection

fred = get_fred_connection()

# --- 1. Inflation: CPI, Core CPI, Core PCE + YoY calculations
def fetch_inflation():
    # Level series from FRED
    cpi = fred.get_series("CPIAUCSL").to_frame("CPI")
    core_cpi = fred.get_series("CPILFESL").to_frame("Core_CPI")
    core_pce = fred.get_series("PCEPILFE").to_frame("Core_PCE")

    df = cpi.join([core_cpi, core_pce], how="outer")
    df.index = pd.to_datetime(df.index)

    # YoY % changes
    df["CPI_YoY"] = df["CPI"].pct_change(12) * 100
    df["Core_CPI_YoY"] = df["Core_CPI"].pct_change(12) * 100
    df["PCE_YoY"] = df["Core_PCE"].pct_change(12) * 100

    return df

# --- 2. Growth Proxies: Retail Sales, Industrial Production, Employment
def fetch_growth():
    retail = fred.get_series("RSAFS").to_frame("Retail_Sales")
    ind_prod = fred.get_series("INDPRO").to_frame("Industrial_Production")
    employment = fred.get_series("PAYEMS").to_frame("Nonfarm_Payrolls")

    df = retail.join([ind_prod, employment], how="outer")
    df.index = pd.to_datetime(df.index)
    return df

# --- 3. Combine All Macro Series
def fetch_macro_core():
    infl = fetch_inflation()
    growth = fetch_growth()

    df = infl.join(growth, how="outer").sort_index()

    # Name the datetime index so it saves as a proper date column
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"

    return df

if __name__ == "__main__":
    data = fetch_macro_core()
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "macro_core.csv")
    # index=True by default; index name "Date" becomes the column header
    data.to_csv(output_path)
    print(f"Macro core data saved to: {output_path}")
