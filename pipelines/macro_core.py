import pandas as pd
from fredapi import Fred
import os

from utils.fred import get_fred_connection
fred = get_fred_connection()

# --- 1. Inflation: CPI, Core CPI, Core PCE
def fetch_inflation():
    cpi = fred.get_series("CPIAUCSL").to_frame("CPI")
    core_cpi = fred.get_series("CPILFESL").to_frame("Core_CPI")
    core_pce = fred.get_series("PCEPILFE").to_frame("Core_PCE")
    df = cpi.join([core_cpi, core_pce], how="outer")
    df.index = pd.to_datetime(df.index)
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
    return df

if __name__ == "__main__":
    data = fetch_macro_core()
    data.to_csv("../data/processed/macro_core.csv")
    print("Macro core data updated.")