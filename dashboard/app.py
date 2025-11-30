# dashboard/app.py

import sys
from pathlib import Path

# ---------------------------------------------------------
# Ensure project root is on sys.path so `utils.*` imports work
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from utils.fetch import load_processed_csv
from utils.plot import single_line_plot, dual_axis_plot
from utils.risk_score import compute_macro_risk_score


# ---------------------------------------------------------
# Helper: ensure we have a datetime column available for plotting
# ---------------------------------------------------------
def _prepare_date_column(df: pd.DataFrame):
    """
    Ensure there is a usable datetime column for plotting.
    Returns a tuple: (df_with_datetime_col, date_col_name)
    """
    # Prefer explicit date-like columns if present
    for col in ["record_date", "Date", "date"]:
        if col in df.columns:
            df = df.copy()
            df[col] = pd.to_datetime(df[col], errors="coerce")
            return df, col

    # If index is already datetime, turn it into a column called Date
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        df.rename(columns={"index": "Date"}, inplace=True)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        return df, "Date"

    # Last fallback: treat first column as date-like
    df = df.reset_index()
    first = df.columns[0]
    df[first] = pd.to_datetime(df[first], errors="coerce")
    df.rename(columns={first: "Date"}, inplace=True)
    return df, "Date"


def _find_column(df: pd.DataFrame, *substrings: str):
    """
    Find the first column whose name contains ALL the given substrings (case-insensitive).
    Returns the column name or None.
    """
    cols = df.columns
    lowered = [c.lower() for c in cols]

    for col, low in zip(cols, lowered):
        if all(s.lower() in low for s in substrings):
            return col
    return None


# ---------------------------------------------------------
# Page config
# ---------------------------------------------------------
st.set_page_config(
    page_title="Macro Capital Flows Dashboard",
    layout="wide",
)

st.title("Macro Capital Flows Dashboard")
st.caption("Prototype dashboard for tracking global liquidity and macro risk regimes")


# ---------------------------------------------------------
# 1. Macro Risk Score (top-level summary)
# ---------------------------------------------------------
st.subheader("Macro Risk Score")

try:
    scores = compute_macro_risk_score()

    latest_components = None

    if isinstance(scores, pd.DataFrame) and len(scores) > 0:
        macro_df = scores
        latest_row = macro_df.iloc[-1]

        if "macro_score" in macro_df.columns:
            latest_score = float(latest_row["macro_score"])
        else:
            latest_score = float(latest_row.iloc[-1])

        latest_components = latest_row

    else:
        # No data – treat as neutral
        latest_score = 50.0

    col_gauge, col_text = st.columns([1, 1.2])

    with col_gauge:
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=latest_score,
                title={"text": "Macro Risk Score"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "black"},
                    "steps": [
                        {"range": [0, 35], "color": "#ff4b4b"},    # risk-off
                        {"range": [35, 65], "color": "#f2c94c"},  # neutral
                        {"range": [65, 100], "color": "#6fcf97"}, # risk-on
                    ],
                },
            )
        )
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, width="stretch")

    with col_text:
        st.write(f"**Current macro score:** {latest_score:0.1f} / 100")

        if latest_score >= 65:
            st.markdown(
                "🟢 **Risk-On Environment**  \n"
                "- Liquidity and macro conditions are supportive.  \n"
                "- Tilt toward equities, small caps, EM, and cyclicals."
            )
        elif latest_score <= 35:
            st.markdown(
                "🔴 **Risk-Off Environment**  \n"
                "- Liquidity and/or credit conditions are deteriorating.  \n"
                "- Favor Treasuries, USD, defensives; reduce high-beta exposure."
            )
        else:
            st.markdown(
                "🟡 **Neutral / Mixed Environment**  \n"
                "- Signals are mixed across liquidity, curve, credit, and FX.  \n"
                "- Consider a barbell of quality equities + duration (Treasuries)."
            )

        if isinstance(latest_components, pd.Series):
            if "fed_liquidity_score" in latest_components.index:
                st.write(f"- Fed liquidity score: {latest_components['fed_liquidity_score']:.2f}")
            if "curve_score" in latest_components.index:
                st.write(f"- Yield curve score: {latest_components['curve_score']:.2f}")
            if "credit_score" in latest_components.index:
                st.write(f"- Credit stress score: {latest_components['credit_score']:.2f}")
            if "fx_score" in latest_components.index:
                st.write(f"- USD liquidity score: {latest_components['fx_score']:.2f}")

except Exception as e:
    st.warning(f"Macro risk score could not be computed: {e}")

st.markdown("---")


# ---------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------
st.sidebar.header("Select Dashboard Section")

section = st.sidebar.radio(
    "Section",
    [
        "Fed Liquidity & Plumbing",
        "Yield Curve & Policy",
        "Credit Market Signals",
        "FX & Global Stress",
        "Growth & Inflation",
    ],
)

st.sidebar.markdown("v0.1 – Prototype scaffold for macro capital dashboard")


# ---------------------------------------------------------
# 2. Fed Liquidity & Plumbing
# ---------------------------------------------------------
if section == "Fed Liquidity & Plumbing":
    st.header("Federal Reserve Plumbing")

    try:
        data = load_processed_csv("fed_liquidity.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    # Normalise column names a bit
    if "closing_balance" in data.columns and "TGA_Balance" not in data.columns:
        data = data.rename(columns={"closing_balance": "TGA_Balance"})

    df_plot, date_col = _prepare_date_column(data)

    # Fed balance sheet + TGA
    if "Fed_Balance_Sheet" in df_plot.columns and "TGA_Balance" in df_plot.columns:
        st.subheader("Fed Balance Sheet & TGA")
        fig = dual_axis_plot(
            df_plot,
            x=date_col,
            y1="Fed_Balance_Sheet",
            y2="TGA_Balance",
            title="Fed Balance Sheet (Assets) and Treasury General Account",
            y1_label="Fed Assets (USD B)",
            y2_label="TGA Balance (USD B)",
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Fed_Balance_Sheet or TGA_Balance column missing in fed_liquidity.csv")

    # RRP usage
    if "RRP_Usage" in df_plot.columns:
        st.subheader("Reverse Repo (RRP) Usage")
        fig_rrp = single_line_plot(
            df_plot,
            x=date_col,
            y="RRP_Usage",
            title="Reverse Repo Facility Usage",
            y_label="USD B",
        )
        st.plotly_chart(fig_rrp, width="stretch")
    else:
        st.info("RRP_Usage column missing in fed_liquidity.csv")


# ---------------------------------------------------------
# 3. Yield Curve & Policy
# ---------------------------------------------------------
elif section == "Yield Curve & Policy":
    st.header("Yield Curve & Policy")

    try:
        yc = load_processed_csv("yield_curve.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    yc_plot, date_col = _prepare_date_column(yc)

    if "Spread_2s10s" in yc_plot.columns:
        st.subheader("2s10s Yield Curve Spread")
        fig_yc = single_line_plot(
            yc_plot,
            x=date_col,
            y="Spread_2s10s",
            title="2s10s Yield Curve (10Y - 2Y)",
            y_label="Basis Points",
        )
        st.plotly_chart(fig_yc, width="stretch")
    else:
        st.info("Spread_2s10s column missing in yield_curve.csv")

    if "Spread_3m10y" in yc_plot.columns:
        st.subheader("3m10y Yield Curve Spread")
        fig_yc2 = single_line_plot(
            yc_plot,
            x=date_col,
            y="Spread_3m10y",
            title="3m10y Yield Curve (10Y - 3M)",
            y_label="Basis Points",
        )
        st.plotly_chart(fig_yc2, width="stretch")


# ---------------------------------------------------------
# 4. Credit Market Signals
# ---------------------------------------------------------
elif section == "Credit Market Signals":
    st.header("Credit Market Signals")

    try:
        cs = load_processed_csv("credit_spreads.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    cs_plot, date_col = _prepare_date_column(cs)
    cols_available = list(cs_plot.columns)

    ig_col = "IG_OAS" if "IG_OAS" in cols_available else None
    hy_col = "HY_OAS" if "HY_OAS" in cols_available else None

    if ig_col and hy_col:
        st.subheader("IG vs HY Credit Spreads")
        fig_cs = dual_axis_plot(
            cs_plot,
            x=date_col,
            y1=ig_col,
            y2=hy_col,
            title="Investment Grade vs High Yield Spreads",
            y1_label="IG OAS (bps)",
            y2_label="HY OAS (bps)",
        )
        st.plotly_chart(fig_cs, width="stretch")
    elif ig_col:
        st.subheader("Investment Grade Credit Spreads")
        fig_ig = single_line_plot(
            cs_plot,
            x=date_col,
            y=ig_col,
            title="Investment Grade OAS",
            y_label="bps",
        )
        st.plotly_chart(fig_ig, width="stretch")
        st.info("HY_OAS column missing in credit_spreads.csv – showing IG only.")
    elif hy_col:
        st.subheader("High Yield Credit Spreads")
        fig_hy = single_line_plot(
            cs_plot,
            x=date_col,
            y=hy_col,
            title="High Yield OAS",
            y_label="bps",
        )
        st.plotly_chart(fig_hy, width="stretch")
        st.info("IG_OAS column missing in credit_spreads.csv – showing HY only.")
    else:
        st.info("No IG_OAS or HY_OAS columns found in credit_spreads.csv.")


# ---------------------------------------------------------
# 5. FX & Global Stress
# ---------------------------------------------------------
elif section == "FX & Global Stress":
    st.header("FX & Global Stress")

    try:
        fx = load_processed_csv("fx_liquidity.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    fx_plot, date_col = _prepare_date_column(fx)

    if "DXY" in fx_plot.columns:
        st.subheader("US Dollar Index (DXY)")
        fig_dxy = single_line_plot(
            fx_plot,
            x=date_col,
            y="DXY",
            title="US Dollar Index (DXY)",
            y_label="Index",
        )
        st.plotly_chart(fig_dxy, width="stretch")
    else:
        st.info("DXY column missing in fx_liquidity.csv")

    if "EM_FX_Basket" in fx_plot.columns:
        st.subheader("EM FX Basket (Inverse Stress Proxy)")
        fig_emfx = single_line_plot(
            fx_plot,
            x=date_col,
            y="EM_FX_Basket",
            title="EM FX Basket",
            y_label="Index",
        )
        st.plotly_chart(fig_emfx, width="stretch")


# ---------------------------------------------------------
# 6. Growth & Inflation
# ---------------------------------------------------------
elif section == "Growth & Inflation":
    st.header("Growth & Inflation")

    try:
        macro = load_processed_csv("macro_core.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    macro_plot, date_col = _prepare_date_column(macro)

    # Try to find PMI / CPI / PCE by flexible name matching
    pmi_col = "PMI" if "PMI" in macro_plot.columns else _find_column(macro_plot, "pmi")
    cpi_col = (
        "CPI_YoY"
        if "CPI_YoY" in macro_plot.columns
        else _find_column(macro_plot, "cpi", "yoy")
        or _find_column(macro_plot, "cpi")
    )
    pce_col = (
        "PCE_YoY"
        if "PCE_YoY" in macro_plot.columns
        else _find_column(macro_plot, "pce", "yoy")
        or _find_column(macro_plot, "pce")
    )

    # If we still couldn't find explicit macro series, fall back to any numeric columns
    numeric_cols = list(macro_plot.select_dtypes(include=["number"]).columns)

    def _pick_or_fallback(preferred, used):
        if preferred and preferred in macro_plot.columns:
            used.add(preferred)
            return preferred
        for col in numeric_cols:
            if col not in used:
                used.add(col)
                return col
        return None

    used_cols = set()
    pmi_col = _pick_or_fallback(pmi_col, used_cols)
    cpi_col = _pick_or_fallback(cpi_col, used_cols)
    pce_col = _pick_or_fallback(pce_col, used_cols)

    # PMI
    if pmi_col:
        st.subheader(f"Manufacturing PMI ({pmi_col})")
        fig_pmi = single_line_plot(
            macro_plot,
            x=date_col,
            y=pmi_col,
            title="Manufacturing PMI",
            y_label="Index / Level",
        )
        st.plotly_chart(fig_pmi, width="stretch")
    else:
        st.info("No usable PMI-like or numeric column found in macro_core.csv.")

    # CPI
    if cpi_col:
        st.subheader(f"CPI / Inflation ({cpi_col})")
        fig_cpi = single_line_plot(
            macro_plot,
            x=date_col,
            y=cpi_col,
            title="CPI / Inflation",
            y_label="Percent / Index",
        )
        st.plotly_chart(fig_cpi, width="stretch")
    else:
        st.info("No usable CPI-like or additional numeric column found in macro_core.csv.")

    # PCE
    if pce_col:
        st.subheader(f"PCE / Core Inflation ({pce_col})")
        fig_pce = single_line_plot(
            macro_plot,
            x=date_col,
            y=pce_col,
            title="PCE / Core Inflation",
            y_label="Percent / Index",
        )
        st.plotly_chart(fig_pce, width="stretch")
    else:
        st.info("No usable PCE-like or additional numeric column found in macro_core.csv.")
