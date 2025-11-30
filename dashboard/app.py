# macro_dashboard/
# ├── data/
# │ ├── raw/ # Downloaded CSV/JSON files
# │ └── processed/ # Cleaned & formatted dataframes
# ├── pipelines/
# │ ├── fed_plumbing.py # Fed balance sheet, RRP, TGA fetch
# │ ├── yield_curve.py # 2Y-10Y spread, SOFR
# │ ├── credit_spreads.py # HY/IG OAS, CDS, BDC data
# │ ├── fx_liquidity.py # DXY, EM FX, FX basis (proxy)
# │ └── macro_core.py # CPI, GDPNow, PMIs, inflation data
# ├── dashboard/
# │ └── app.py # Streamlit or Dash interface
# ├── utils/
# │ ├── fred.py # Fred API wrapper
# │ ├── plot.py # Plotly or Matplotlib helpers
# │ └── fetch.py # Requests, BeautifulSoup utilities
# └── requirements.txt # Python dependencies

# 🐍 Initial app.py using Streamlit
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.fetch import load_processed_csv
from utils.plot import single_line_plot, dual_axis_plot

st.set_page_config(layout="wide")
st.title("🫡 Macro Capital Flow Dashboard")

st.sidebar.header("Select Dashboard Section")
section = st.sidebar.radio("Section", [
    "Fed Liquidity & Plumbing",
    "Yield Curve & Policy",
    "Credit Market Signals",
    "FX & Global Stress",
    "Growth & Inflation"
])

if section == "Fed Liquidity & Plumbing":
    st.subheader("Federal Reserve Plumbing")
    data = load_processed_csv("fed_liquidity.csv")
    st.plotly_chart(dual_axis_plot(data.reset_index(), "index", "Fed_Balance_Sheet", "TGA_Balance", title="Fed Balance Sheet & TGA", y1_label="Assets (USD B)", y2_label="TGA (USD B)"))
    st.plotly_chart(single_line_plot(data.reset_index(), "index", "RRP_Usage", title="Reverse Repo (RRP) Usage", y_label="USD B"))

elif section == "Yield Curve & Policy":
    st.subheader("Market-Implied Policy")
    data = load_processed_csv("yield_curve.csv")
    st.plotly_chart(dual_axis_plot(data.reset_index(), "index", "2Y_Yield", "10Y_Yield", title="2Y vs 10Y Treasury Yields", y1_label="2Y", y2_label="10Y"))
    st.plotly_chart(single_line_plot(data.reset_index(), "index", "2s10s_Spread", title="Yield Curve: 2s10s Spread", y_label="%"))
    st.plotly_chart(single_line_plot(data.reset_index(), "index", "SOFR", title="SOFR Rate", y_label="%"))

elif section == "Credit Market Signals":
    st.subheader("Credit Risk Overview")
    data = load_processed_csv("credit_spreads.csv")
    st.plotly_chart(dual_axis_plot(data.reset_index(), "index", "High_Yield_OAS", "IG_OAS", title="High Yield vs IG OAS", y1_label="HY OAS", y2_label="IG OAS"))
    st.plotly_chart(single_line_plot(data.reset_index(), "index", "HY_IG_Spread", title="HY - IG Credit Spread", y_label="bps"))

elif section == "FX & Global Stress":
    st.subheader("Dollar Liquidity & FX")
    data = load_processed_csv("fx_liquidity.csv")
    st.plotly_chart(single_line_plot(data.reset_index(), "index", "DXY", title="US Dollar Index (DXY)", y_label="Index"))
    for col in ["USD/TRY", "USD/ZAR", "USD/CLP"]:
        if col in data.columns:
            st.plotly_chart(single_line_plot(data.reset_index(), "index", col, title=f"{col} Exchange Rate", y_label="Rate"))

elif section == "Growth & Inflation":
    st.subheader("Macro Fundamentals")
    data = load_processed_csv("macro_core.csv")
    st.plotly_chart(dual_axis_plot(data.reset_index(), "index", "CPI", "Core_CPI", title="CPI vs Core CPI", y1_label="CPI", y2_label="Core CPI"))
    st.plotly_chart(single_line_plot(data.reset_index(), "index", "Core_PCE", title="Core PCE Price Index", y_label="Index"))
    st.plotly_chart(single_line_plot(data.reset_index(), "index", "Retail_Sales", title="Retail Sales", y_label="Index"))
    st.plotly_chart(single_line_plot(data.reset_index(), "index", "Industrial_Production", title="Industrial Production", y_label="Index"))
    st.plotly_chart(single_line_plot(data.reset_index(), "index", "Nonfarm_Payrolls", title="Nonfarm Payroll Employment", y_label="Thousands"))

st.sidebar.markdown("---")
st.sidebar.caption("v0.1 – Prototype scaffold for macro capital dashboard")