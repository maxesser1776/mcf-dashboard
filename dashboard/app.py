# dashboard/app.py

import os
import sys
import traceback

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf

# ---------------------------------------------------------
# Ensure project root is on sys.path so `utils.*` imports work
# ---------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.fetch import load_processed_csv
from utils.plot import single_line_plot, dual_axis_plot
from utils.risk_score import compute_macro_risk_score, _scale_to_0_100


# ---------------------------------------------------------
# Page config
# ---------------------------------------------------------
st.set_page_config(
    page_title="Macro Capital Flows Dashboard",
    layout="wide",
)

st.title("Macro Capital Flows Dashboard")
st.caption(
    "Tracking liquidity, curve, credit, FX, volatility, and macro data to infer risk regimes. "
    "Data freshness depends on provider: market data is daily; macro data is weekly or monthly."
)


# ---------------------------------------------------------
# Helper: ensure we have a usable date column
# ---------------------------------------------------------
def _get_date_column(df: pd.DataFrame) -> str:
    """
    Ensure there is a concrete date column in the DataFrame and return its name.

    - If a known date column ('record_date', 'Date', 'date') exists, use it.
    - If the index is a DatetimeIndex, reset it into a real column:
        * If the index has a name, that name is used.
        * Otherwise the column is renamed to 'date'.
    - Otherwise, fallback to the first column.
    """
    for col in ["record_date", "Date", "date"]:
        if col in df.columns:
            return col

    if isinstance(df.index, pd.DatetimeIndex):
        idx_name = df.index.name
        df.reset_index(inplace=True)
        if idx_name is None:
            if "index" in df.columns:
                df.rename(columns={"index": "date"}, inplace=True)
                return "date"
            return df.columns[0]
        else:
            return idx_name

    return df.columns[0]


# ---------------------------------------------------------
# 1. Macro Risk Score (top-level summary)
# ---------------------------------------------------------
st.subheader("Macro Risk Score")
st.caption(
    "This gauge compresses Fed liquidity, yield curve shape, credit spreads, FX stress, funding conditions, "
    "volatility regimes, and leading growth indicators into a 0–100 score. Higher values lean risk-on, lower values "
    "lean risk-off. Underlying updates: daily (rates, credit, FX, volatility), weekly/monthly (growth & inflation)."
)

try:
    macro_df = compute_macro_risk_score().sort_index()
    latest = macro_df.iloc[-1]
    latest_score = float(latest["macro_score"])

    col_gauge, col_text = st.columns([1, 1.6])

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
                        {"range": [0, 35], "color": "#ff4b4b"},
                        {"range": [35, 65], "color": "#f2c94c"},
                        {"range": [65, 100], "color": "#6fcf97"},
                    ],
                },
            )
        )
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col_text:
        st.write(f"**Current macro score:** {latest_score:0.1f} / 100")

        if latest_score >= 65:
            st.markdown("🟢 **Risk-On Environment** — flows into equities, EM, cyclicals")
        elif latest_score <= 35:
            st.markdown("🔴 **Risk-Off Environment** — flows into USD, Treasuries, defensives")
        else:
            st.markdown("🟡 **Mixed Environment** — barbell of quality + duration")

    # === Macro Risk Score History ===
    st.subheader("Macro Risk Score History")

    hist = macro_df[["macro_score"]].dropna().copy()

    if not hist.empty:
        if isinstance(hist.index, pd.DatetimeIndex):
            x_vals = hist.index
        else:
            x_vals = pd.to_datetime(hist.index, errors="coerce")

        fig_hist = go.Figure(
            data=[go.Scatter(x=x_vals, y=hist["macro_score"], mode="lines", line=dict(width=2))]
        )

        crisis_windows = [
            ("Dot-com Bust", "2000-03-01", "2002-10-01"),
            ("GFC", "2007-10-01", "2009-03-01"),
            ("Euro Debt", "2011-07-01", "2012-09-01"),
            ("China/EM", "2015-08-01", "2016-02-01"),
            ("COVID", "2020-02-15", "2020-04-30"),
            ("2022 Bear", "2021-11-01", "2022-10-01"),
        ]

        # Crisis shading
        shapes = []
        for name, x0, x1 in crisis_windows:
            shapes.append(
                dict(
                    type="rect",
                    xref="x",
                    yref="paper",
                    x0=x0,
                    x1=x1,
                    y0=0,
                    y1=1,
                    fillcolor="#ff7f0e",
                    opacity=0.12,
                    line_width=0,
                )
            )

        fig_hist.update_layout(
            shapes=shapes,
            height=300,
            yaxis=dict(title="Score", range=[0, 100]),
            xaxis_title="Date",
            margin=dict(l=20, r=20, t=30, b=40),
            showlegend=False,
        )

        # Add labels
        for name, x0, x1 in crisis_windows:
            mid = pd.to_datetime(x0) + (pd.to_datetime(x1) - pd.to_datetime(x0)) / 2
            fig_hist.add_annotation(
                x=mid, y=98, text=name, showarrow=False, yanchor="top", font=dict(size=9)
            )

        st.plotly_chart(fig_hist, use_container_width=True)

    else:
        st.info("Macro score history empty — run pipelines to update data.")

except Exception as e:
    traceback.print_exc()
    st.warning(f"Macro score section failed: {e}")

st.markdown("---")  # THIS MUST BE OUTSIDE try/except!


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
        "Leading Growth Signals",
        "Volatility & Market Stress",
        "Model Diagnostics",
        "Historical Accuracy",
    ],
)

st.sidebar.markdown(
    "v0.4 – Macro Capital Flows Dashboard. "
    "Run the pipelines or scheduled job to refresh data."
)


# ---------------------------------------------------------
# 2. Fed Liquidity & Plumbing
# ---------------------------------------------------------
if section == "Fed Liquidity & Plumbing":
    st.header("Federal Reserve Plumbing")
    st.caption(
        "This page shows how the Fed, Treasury, and money markets are adding or draining dollar liquidity. "
        "The balance sheet and TGA affect systemic liquidity, RRP reflects excess cash parked at the Fed, "
        "and funding spreads flag stress in short term markets. "
        "Update cadence: balance sheet weekly, TGA and RRP daily with a short lag."
    )

    try:
        data = load_processed_csv("fed_liquidity.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    if "closing_balance" in data.columns and "TGA_Balance" not in data.columns:
        data = data.rename(columns={"closing_balance": "TGA_Balance"})

    date_col = _get_date_column(data)
    df_plot = data.copy()
    df_plot[date_col] = pd.to_datetime(df_plot[date_col])

    if "Fed_Balance_Sheet" in df_plot.columns and "TGA_Balance" in df_plot.columns:
        st.subheader("Fed Balance Sheet and TGA")
        st.caption(
            "Fed assets QE or QT push liquidity into or out of the system, while changes in the Treasury "
            "General Account can temporarily drain or add reserves. "
            "Fed balance sheet data is typically updated weekly; TGA balances are daily or near daily "
            "from Treasury sources."
        )
        fig = dual_axis_plot(
            df_plot,
            x=date_col,
            y1="Fed_Balance_Sheet",
            y2="TGA_Balance",
            title="Fed Balance Sheet Assets and Treasury General Account",
            y1_label="Fed Assets (USD B)",
            y2_label="TGA Balance (USD B)",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Fed_Balance_Sheet or TGA_Balance column missing in fed_liquidity.csv")

    if "RRP_Usage" in df_plot.columns:
        st.subheader("Reverse Repo (RRP) Usage")
        st.caption(
            "High RRP usage means money funds prefer to lend to the Fed instead of private markets. "
            "A falling RRP balance often signals liquidity moving back into risk assets. "
            "RRP facility data is published daily for the prior business day."
        )
        fig_rrp = single_line_plot(
            df_plot,
            x=date_col,
            y="RRP_Usage",
            title="Reverse Repo Facility Usage",
            y_label="USD B",
        )
        st.plotly_chart(fig_rrp, use_container_width=True)
    else:
        st.info("RRP_Usage column missing in fed_liquidity.csv")

    st.markdown("---")

    st.subheader("Funding Stress: EFFR vs SOFR or OBFR")
    st.caption(
        "These spreads compare the effective fed funds rate to secured and overnight benchmarks. "
        "Persistent positive spreads can indicate tightening conditions or stress in unsecured funding. "
        "EFFR, SOFR, and OBFR are updated daily with roughly a one day lag."
    )

    try:
        fs = load_processed_csv("funding_stress.csv")
    except FileNotFoundError:
        st.info("funding_stress.csv not found yet. Run the funding_stress pipeline to enable this section.")
    else:
        fs_date_col = _get_date_column(fs)
        fs_plot = fs.copy()
        fs_plot[fs_date_col] = pd.to_datetime(fs_plot[fs_date_col])

        col_left, col_right = st.columns(2)

        if "EFFR_minus_SOFR" in fs_plot.columns:
            with col_left:
                fig_effr_sofr = single_line_plot(
                    fs_plot,
                    x=fs_date_col,
                    y="EFFR_minus_SOFR",
                    title="EFFR minus SOFR Spread",
                    y_label="percent points",
                )
                st.plotly_chart(fig_effr_sofr, use_container_width=True)
        else:
            with col_left:
                st.info("EFFR_minus_SOFR column missing in funding_stress.csv")

        if "EFFR_minus_OBFR" in fs_plot.columns:
            with col_right:
                fig_effr_obfr = single_line_plot(
                    fs_plot,
                    x=fs_date_col,
                    y="EFFR_minus_OBFR",
                    title="EFFR minus OBFR Spread",
                    y_label="percent points",
                )
                st.plotly_chart(fig_effr_obfr, use_container_width=True)
        else:
            with col_right:
                st.info("EFFR_minus_OBFR column missing in funding_stress.csv")

        numeric_cols = [c for c in ["EFFR_minus_SOFR", "EFFR_minus_OBFR"] if c in fs_plot.columns]
        latest_row = fs_plot.dropna(subset=numeric_cols).iloc[-1] if numeric_cols else None

        if latest_row is not None:
            effr_sofr = float(latest_row.get("EFFR_minus_SOFR", 0.0))
            effr_obfr = float(latest_row.get("EFFR_minus_OBFR", 0.0))

            st.markdown("#### Current Funding Conditions")

            stress_level = "🟢 Normal – funding markets look orderly."
            if effr_sofr > 0.10 or effr_obfr > 0.10:
                stress_level = "🟠 Elevated stress – fed funds rich vs SOFR or OBFR; watch funding closely."
            if effr_sofr > 0.25 or effr_obfr > 0.25:
                stress_level = "🔴 High stress – significant dislocation; markets leaning on safer collateral."

            st.write(
                f"- Latest EFFR minus SOFR: `{effr_sofr:.3f}`  \n"
                f"- Latest EFFR minus OBFR: `{effr_obfr:.3f}`  \n\n"
                f"{stress_level}"
            )

            st.caption(
                "Short spikes can happen around month end or policy events. "
                "Sustained widening is more concerning than one day noise."
            )
        else:
            st.info("No recent non NaN funding spread values available to interpret.")


# ---------------------------------------------------------
# 3. Yield Curve & Policy
# ---------------------------------------------------------
elif section == "Yield Curve & Policy":
    st.header("Yield Curve and Policy")
    st.caption(
        "The yield curve compares long term and short term interest rates. "
        "Inversions, when short rates exceed long rates, have historically been a reliable recession signal. "
        "Here we track the classic 2s10s and 3m10y spreads. Treasury constant maturity yields "
        "update on business days with a short lag."
    )

    try:
        yc = load_processed_csv("yield_curve.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    date_col = _get_date_column(yc)
    yc[date_col] = pd.to_datetime(yc[date_col])

    if "Spread_2s10s" in yc.columns:
        st.subheader("2s10s Yield Curve Spread")
        fig_yc = single_line_plot(
            yc,
            x=date_col,
            y="Spread_2s10s",
            title="2s10s Yield Curve 10Y minus 2Y",
            y_label="Basis Points",
        )
        st.plotly_chart(fig_yc, use_container_width=True)
        st.caption(
            "Positive values mean a normal curve with long rates above short rates. "
            "Sustained negative values inversion often precede economic slowdowns. "
            "This spread updates as new daily yield data is published."
        )
    else:
        st.info("Spread_2s10s column missing in yield_curve.csv")

    if "Spread_3m10y" in yc.columns:
        st.subheader("3m10y Yield Curve Spread")
        fig_yc2 = single_line_plot(
            yc,
            x=date_col,
            y="Spread_3m10y",
            title="3m10y Yield Curve 10Y minus 3M",
            y_label="Basis Points",
        )
        st.plotly_chart(fig_yc2, use_container_width=True)
        st.caption(
            "The 3m10y curve incorporates both Fed policy expectations and term premia. "
            "Deep, persistent inversions here are particularly important for recession risk. "
            "Like 2s10s, this series is updated on business days."
        )
    else:
        st.info("Spread_3m10y column missing in yield_curve.csv")


# ---------------------------------------------------------
# 4. Credit Market Signals
# ---------------------------------------------------------
elif section == "Credit Market Signals":
    st.header("Credit Market Signals")
    st.caption(
        "Credit spreads measure the extra yield that corporate bonds pay over Treasuries. "
        "Rising spreads mean investors are demanding more compensation for credit risk, "
        "which can signal stress before it shows up in equities. "
        "These OAS series are calculated from daily bond market data and typically update "
        "with about a one business day lag."
    )

    try:
        cs = load_processed_csv("credit_spreads.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    date_col = _get_date_column(cs)
    cs[date_col] = pd.to_datetime(cs[date_col])

    cols_available = cs.columns.tolist()

    if "IG_OAS" in cols_available and "HY_OAS" in cols_available:
        st.subheader("IG vs HY Credit Spreads")
        fig_cs = dual_axis_plot(
            cs,
            x=date_col,
            y1="IG_OAS",
            y2="HY_OAS",
            title="Investment Grade vs High Yield Spreads",
            y1_label="IG OAS (bps)",
            y2_label="HY OAS (bps)",
        )
        st.plotly_chart(fig_cs, use_container_width=True)
        st.caption(
            "IG OAS reflects risk in higher quality corporate bonds, while HY OAS reflects risk in junk bonds. "
            "Fast widening in HY, especially if IG also widens, often aligns with risk off regimes. "
            "Spreads are updated as new daily pricing data is ingested."
        )
    else:
        if "IG_OAS" not in cols_available:
            st.info("IG_OAS column missing in credit_spreads.csv")
        if "HY_OAS" not in cols_available:
            st.info("HY_OAS column missing in credit_spreads.csv")


# ---------------------------------------------------------
# 5. FX & Global Stress
# ---------------------------------------------------------
elif section == "FX & Global Stress":
    st.header("FX and Global Stress")
    st.caption(
        "The dollar sits at the center of global funding. A strong, rapidly rising USD can tighten "
        "financial conditions for the rest of the world. EM FX trends help show whether global risk "
        "appetite is healthy or under pressure. "
        "DXY and EM FX series are pulled from market data via Yahoo Finance and update on each trading day."
    )

    try:
        fx = load_processed_csv("fx_liquidity.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    date_col = _get_date_column(fx)
    fx[date_col] = pd.to_datetime(fx[date_col])

    if "DXY" in fx.columns:
        st.subheader("US Dollar Index DXY")
        fig_dxy = single_line_plot(
            fx,
            x=date_col,
            y="DXY",
            title="US Dollar Index DXY",
            y_label="Index",
        )
        st.plotly_chart(fig_dxy, use_container_width=True)
        st.caption(
            "A persistently strong and rising USD often coincides with tighter global dollar liquidity "
            "and pressure on risk assets, especially outside the US. "
            "Updated on each market trading day as new prices are available."
        )
    else:
        st.info("DXY column missing in fx_liquidity.csv")

    if "EM_FX_Basket" in fx.columns:
        st.subheader("EM FX Basket Inverse Stress Proxy")
        fig_emfx = single_line_plot(
            fx,
            x=date_col,
            y="EM_FX_Basket",
            title="EM FX Basket",
            y_label="Index",
        )
        st.plotly_chart(fig_emfx, use_container_width=True)
        st.caption(
            "This basket proxies EM currency strength versus the dollar. "
            "Falling values suggest EM under pressure and a more fragile global risk backdrop. "
            "Like DXY, this series updates on each trading day."
        )
    else:
        st.info("EM_FX_Basket column missing in fx_liquidity.csv")


# ---------------------------------------------------------
# 6. Growth & Inflation
# ---------------------------------------------------------
elif section == "Growth & Inflation":
    st.header("Growth and Inflation")
    st.caption(
        "This page tracks real activity and price trends. The idea is to see whether we are in an "
        "overheating inflationary phase, a disinflationary soft landing, or a growth slowdown. "
        "Industrial production, CPI, and PCE are all monthly series that update when new releases "
        "are published, typically once per month with a lag."
    )

    try:
        macro = load_processed_csv("macro_core.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    date_col = _get_date_column(macro)
    macro[date_col] = pd.to_datetime(macro[date_col])

    if "Industrial_Production" in macro.columns:
        macro["IP_YoY"] = macro["Industrial_Production"].pct_change(12) * 100
        st.subheader("Industrial Production YoY")
        fig_ip = single_line_plot(
            macro,
            x=date_col,
            y="IP_YoY",
            title="Industrial Production YoY",
            y_label="Percent",
        )
        st.plotly_chart(fig_ip, use_container_width=True)
        st.caption(
            "Industrial production YoY is a classic real economy growth indicator. "
            "Falling or negative values often coincide with slowdowns or recessions. "
            "This series is updated monthly after the Fed G17 release."
        )
    else:
        st.info("Industrial_Production column missing in macro_core.csv")

    if "CPI_YoY" in macro.columns:
        st.subheader("CPI YoY")
        fig_cpi = single_line_plot(
            macro,
            x=date_col,
            y="CPI_YoY",
            title="Headline CPI YoY",
            y_label="Percent",
        )
        st.plotly_chart(fig_cpi, use_container_width=True)
        st.caption(
            "Headline CPI YoY measures broad consumer price inflation. "
            "Persistent readings well above the policy target imply tighter financial conditions. "
            "CPI is released monthly, usually mid month for the prior month."
        )
    else:
        st.info("CPI_YoY column missing in macro_core.csv")

    if "PCE_YoY" in macro.columns:
        st.subheader("PCE YoY")
        fig_pce = single_line_plot(
            macro,
            x=date_col,
            y="PCE_YoY",
            title="Core PCE YoY",
            y_label="Percent",
        )
        st.plotly_chart(fig_pce, use_container_width=True)
        st.caption(
            "Core PCE YoY is the Fed preferred inflation gauge. "
            "It strips out food and energy to focus on underlying price pressures. "
            "PCE is also released monthly, typically a couple of weeks after CPI."
        )
    else:
        st.info("PCE_YoY column missing in macro_core.csv")


# ---------------------------------------------------------
# 7. Leading Growth Signals
# ---------------------------------------------------------
elif section == "Leading Growth Signals":
    st.header("Leading Growth Signals")
    st.caption(
        "This page focuses on forward looking growth indicators: manufacturers orders versus inventories and "
        "Initial Unemployment Claims. A falling orders inventories spread and rising claims often precede "
        "broader slowdowns or recessions. Orders and inventories are monthly; claims are weekly."
    )

    try:
        gl = load_processed_csv("growth_leading.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    date_col = _get_date_column(gl)
    gl[date_col] = pd.to_datetime(gl[date_col])

    # Filter to non null ISM_Spread rows so the line actually shows
    if "ISM_Spread" in gl.columns:
        gl_ism = gl.dropna(subset=["ISM_Spread"]).copy()
        if not gl_ism.empty:
            st.subheader("Orders vs Inventories Growth Spread")
            fig_ism = single_line_plot(
                gl_ism,
                x=date_col,
                y="ISM_Spread",
                title="Manufacturers Orders YoY minus Inventories YoY",
                y_label="Percentage Points",
            )
            st.plotly_chart(fig_ism, use_container_width=True)
            st.caption(
                "This spread proxies the ISM New Orders minus Inventories signal using manufacturers orders and "
                "inventories growth. Large positive values are associated with strong forward demand; "
                "falling or negative values suggest weakening orders relative to stock levels. "
                "Updated monthly from Census manufacturing data."
            )
        else:
            st.info("ISM_Spread is present but all values are NaN.")
    else:
        st.info("ISM_Spread column missing in growth_leading.csv")

    # Filter to non null claims rows
    if "Initial_Claims_4WMA" in gl.columns:
        gl_claims = gl.dropna(subset=["Initial_Claims_4WMA"]).copy()
        if not gl_claims.empty:
            st.subheader("Initial Jobless Claims 4 week Moving Average")
            fig_claims = single_line_plot(
                gl_claims,
                x=date_col,
                y="Initial_Claims_4WMA",
                title="Initial Unemployment Claims 4 week MA",
                y_label="Number of Claims",
            )
            st.plotly_chart(fig_claims, use_container_width=True)
            st.caption(
                "Initial unemployment claims are one of the fastest labor market indicators. "
                "A sustained uptrend in the 4 week moving average often signals increasing stress in the real economy. "
                "Claims data is released weekly by the US Department of Labor."
            )
        else:
            st.info("Initial_Claims_4WMA is present but all values are NaN.")
    else:
        st.info("Initial_Claims_4WMA column missing in growth_leading.csv")


# ---------------------------------------------------------
# 8. Volatility & Market Stress
# ---------------------------------------------------------
elif section == "Volatility & Market Stress":
    st.header("Volatility and Market Stress")
    st.caption(
        "This page tracks implied equity volatility VIX, the shape of the VIX curve, and Treasury rate volatility "
        "MOVE Index. Front end VIX spikes, curve inversion where front greater than 3M, and high MOVE levels are classic signs of "
        "short term market stress. Data comes from CBOE VIX indices and the ICE BofAML MOVE Index via Yahoo Finance "
        "and updates on each trading day."
    )

    try:
        vol = load_processed_csv("volatility_regimes.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    date_col = _get_date_column(vol)
    vol[date_col] = pd.to_datetime(vol[date_col])

    if "VIX_Short" in vol.columns:
        st.subheader("Front Month VIX")
        fig_vix = single_line_plot(
            vol,
            x=date_col,
            y="VIX_Short",
            title="VIX Front Month Implied Volatility",
            y_label="Index Level",
        )
        st.plotly_chart(fig_vix, use_container_width=True)
        st.caption(
            "Higher VIX levels indicate greater implied volatility in S&P 500 options. "
            "Short, sharp spikes often correspond to equity selloffs or event risk. "
            "Updated on each trading day from market data."
        )
    else:
        st.info("VIX_Short column missing in volatility_regimes.csv")

    if "VIX_Term_Ratio" in vol.columns:
        st.subheader("VIX Term Structure Front / 3M")
        fig_term = single_line_plot(
            vol,
            x=date_col,
            y="VIX_Term_Ratio",
            title="VIX Term Structure Ratio Front / 3M",
            y_label="Ratio",
        )
        st.plotly_chart(fig_term, use_container_width=True)
        st.caption(
            "When the ratio is below 1, the curve is in contango where front less than 3M, which is typical in calm markets. "
            "When the ratio moves above 1 and stays there, the curve is in backwardation and often reflects "
            "acute risk off conditions. This ratio is calculated daily from VIX and VIX3M."
        )
    else:
        st.info("VIX_Term_Ratio column missing in volatility_regimes.csv")

    if "MOVE_Index" in vol.columns:
        st.subheader("MOVE Index Treasury Volatility")
        fig_move = single_line_plot(
            vol,
            x=date_col,
            y="MOVE_Index",
            title="ICE BofAML MOVE Index",
            y_label="Index Level",
        )
        st.plotly_chart(fig_move, use_container_width=True)
        st.caption(
            "The MOVE Index measures implied volatility in US Treasury markets. "
            "Elevated or spiking MOVE levels often coincide with rate shocks, bond market stress, "
            "and tightening financial conditions. Like VIX, this series is pulled daily from Yahoo Finance."
        )
    else:
        st.info("MOVE_Index column missing in volatility_regimes.csv")


# ---------------------------------------------------------
# 9. Model Diagnostics (scaling debug etc.)
# ---------------------------------------------------------
elif section == "Model Diagnostics":
    st.header("Model Diagnostics")
    st.caption(
        "Tools to sanity check component scores, scaling behavior, and how much the macro score is relying on each factor."
    )

    try:
        scores = compute_macro_risk_score().sort_index()
    except Exception as e:
        st.error(f"Failed to compute macro scores for diagnostics: {e}")
        st.stop()

    if scores.empty:
        st.info("Macro score history empty — run pipelines to update data.")
        st.stop()

    # Component snapshot
    st.subheader("Latest Component Snapshot")
    latest_row = scores.iloc[-1]
    comp_cols = [c for c in scores.columns if c.endswith("_score")]
    snapshot = latest_row[comp_cols + ["macro_score"]].to_frame("Latest Score").round(1)
    st.dataframe(snapshot, use_container_width=True)

    st.markdown("---")
    st.subheader("Factor Normalization Debug")

    factor_options = comp_cols + ["macro_score"]
    factor = st.selectbox("Select factor / macro score to inspect", factor_options, index=0)

    series = scores[factor].copy()
    series = series.replace([np.inf, -np.inf], np.nan).dropna()

    if series.empty:
        st.info("Selected series is empty after cleaning; pick another factor.")
        st.stop()

    window = st.slider("Rolling window (days)", min_value=63, max_value=504, value=252, step=21)

    # Full-history scaling using the same helper as in utils.risk_score
    full_scaled = _scale_to_0_100(series)

    # Rolling min/max scaling to 0–100
    roll_min = series.rolling(window).min()
    roll_max = series.rolling(window).max()

    denom = (roll_max - roll_min).replace(0, np.nan)
    rolling_scaled = (series - roll_min) / denom * 100.0
    # Where denom was 0 or NaN, center at 50
    rolling_scaled = rolling_scaled.fillna(50.0)

    dbg = pd.DataFrame(
        {
            "raw": series,
            "full_scaled": full_scaled.reindex(series.index),
            "rolling_scaled": rolling_scaled,
        }
    )

    # Plot
    fig_dbg = go.Figure()
    fig_dbg.add_trace(
        go.Scatter(
            x=dbg.index,
            y=dbg["raw"],
            mode="lines",
            name="Raw",
            yaxis="y1",
        )
    )
    fig_dbg.add_trace(
        go.Scatter(
            x=dbg.index,
            y=dbg["full_scaled"],
            mode="lines",
            name="Full-history 0–100",
            yaxis="y2",
        )
    )
    fig_dbg.add_trace(
        go.Scatter(
            x=dbg.index,
            y=dbg["rolling_scaled"],
            mode="lines",
            name=f"Rolling {window}d 0–100",
            yaxis="y2",
            line=dict(dash="dash"),
        )
    )

    fig_dbg.update_layout(
        height=350,
        margin=dict(l=40, r=40, t=40, b=40),
        yaxis=dict(title="Raw", side="left"),
        yaxis2=dict(title="Scaled (0–100)", overlaying="y", side="right", range=[0, 100]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        title=f"{factor} — Raw vs Full vs Rolling Scaling",
    )

    st.plotly_chart(fig_dbg, use_container_width=True)

    # Simple stats table
    st.markdown("#### Scaling Stats")
    stats = dbg[["full_scaled", "rolling_scaled"]].describe().T.round(2)
    st.dataframe(stats, use_container_width=True)


# ---------------------------------------------------------
# 10. Historical Accuracy Panel
# ---------------------------------------------------------
elif section == "Historical Accuracy":
    st.header("Historical Accuracy")
    st.caption(
        "How well did each macro regime historically predict asset performance? "
        "Forward returns are computed over each historical regime condition."
    )

    try:
        scores = compute_macro_risk_score().sort_index()
    except Exception as e:
        st.error(f"Failed to compute macro scores for accuracy panel: {e}")
        st.stop()

    if not isinstance(scores.index, pd.DatetimeIndex):
        scores.index = pd.to_datetime(scores.index, errors="coerce")

    scores = scores.dropna(subset=["macro_score"]).sort_index()

    if scores.empty:
        st.info("Macro score history empty — cannot compute historical accuracy.")
        st.stop()

    def classify_regime(x: float) -> str:
        if x >= 60:
            return "Risk-On"
        elif x <= 40:
            return "Risk-Off"
        else:
            return "Mixed"

    scores["Regime"] = scores["macro_score"].apply(classify_regime)

    tickers = {
        "SPY": "US Equities",
        "TLT": "Long Treasuries",
        "GLD": "Gold",
        "UUP": "US Dollar",
        "HYG": "High Yield Credit",
        "EEM": "Emerging Markets",
    }

    st.markdown("### Assets to Evaluate")
    selected = st.multiselect(
        "Select assets",
        list(tickers.keys()),
        default=["SPY", "TLT", "GLD", "UUP"],
    )

    look_aheads = [30, 90, 180]
    start = scores.index.min()
    end = scores.index.max()

    if not selected:
        st.info("Select at least one asset to evaluate.")
        st.stop()

    # Robust yfinance handling
    raw = yf.download(selected, start=start, end=end, auto_adjust=True)

    if raw.empty:
        st.info("No price data returned from yfinance for the selected assets and date range.")
        st.stop()

    # Extract closing prices robustly
    if isinstance(raw.columns, pd.MultiIndex):
        data = None

        # Pattern 1: level 0 = price field, level 1 = ticker
        if "Close" in raw.columns.get_level_values(0):
            try:
                data = raw["Close"].copy()
            except Exception:
                data = None

        # Pattern 2: level 1 = price field, level 0 = ticker
        if data is None and "Close" in raw.columns.get_level_values(1):
            try:
                data = raw.xs("Close", axis=1, level=1)
            except Exception:
                data = None

        # Fallback to Adj Close if needed
        if data is None and "Adj Close" in raw.columns.get_level_values(0):
            try:
                data = raw["Adj Close"].copy()
            except Exception:
                data = None

        if data is None and "Adj Close" in raw.columns.get_level_values(1):
            try:
                data = raw.xs("Adj Close", axis=1, level=1)
            except Exception:
                data = None

        if data is None:
            raise ValueError(
                f"Downloaded data has MultiIndex columns but no usable 'Close' or 'Adj Close' field. "
                f"Columns: {raw.columns}"
            )

    else:
        data = None
        for candidate in ["Adj Close", "Close"]:
            if candidate in raw.columns:
                data = raw[[candidate]].copy()
                # If only one ticker, rename column to ticker for consistency
                if len(selected) == 1:
                    data.columns = [selected[0]]
                break

        if data is None:
            # Assume columns already correspond to tickers
            data = raw.copy()

    data = data.dropna(how="all")

    # Make sure columns are exactly the selected tickers if possible
    missing_cols = [t for t in selected if t not in data.columns]
    if missing_cols:
        st.warning(f"No usable price series for: {', '.join(missing_cols)}. They will be skipped.")
        selected = [t for t in selected if t in data.columns]

    if not selected:
        st.info("No valid assets left after cleaning; cannot compute accuracy.")
        st.stop()

    # Align market data to scores index
    data = data.reindex(scores.index, method="ffill")

    results = []
    for regime in ["Risk-On", "Mixed", "Risk-Off"]:
        mask = scores["Regime"] == regime
        dates = scores.index[mask]

        for ticker in selected:
            for days in look_aheads:
                fwd = []
                dd = []
                for d in dates:
                    end_date = d + pd.Timedelta(days=days)
                    if end_date not in data.index:
                        continue
                    start_px = data.loc[d, ticker]
                    end_px = data.loc[end_date, ticker]
                    if pd.isna(start_px) or pd.isna(end_px):
                        continue

                    ret = (end_px - start_px) / start_px * 100.0
                    fwd.append(ret)

                    window_prices = data.loc[d:end_date, ticker]
                    if window_prices.empty or pd.isna(window_prices).all():
                        continue
                    ddn = (window_prices.min() - start_px) / start_px * 100.0
                    dd.append(ddn)

                if not fwd:
                    continue

                results.append(
                    {
                        "Regime": regime,
                        "Asset": ticker,
                        "Forward": f"{days}d",
                        "Avg Return %": float(np.mean(fwd)),
                        "Win Rate %": float(100 * (np.sum(np.array(fwd) > 0) / len(fwd))),
                        "Avg Max Drawdown %": float(np.mean(dd)) if dd else np.nan,
                    }
                )

    if not results:
        st.info("Not enough overlapping history between macro regimes and asset data to compute stats.")
        st.stop()

    res_df = pd.DataFrame(results)

    st.markdown("### Summary Table")
    pivot = (
        res_df.pivot(index=["Regime", "Asset"], columns="Forward")[
            ["Avg Return %", "Win Rate %", "Avg Max Drawdown %"]
        ]
        .round(2)
        .sort_index()
    )
    st.dataframe(pivot, use_container_width=True)

    st.markdown("### Quick Insights")
    for regime in ["Risk-On", "Mixed", "Risk-Off"]:
        subset = res_df[res_df["Regime"] == regime]
        if subset.empty:
            continue
        best = subset.nlargest(1, "Avg Return %").iloc[0]
        worst = subset.nsmallest(1, "Avg Return %").iloc[0]
        st.write(
            f"**{regime}:** "
            f"Best = {best['Asset']} ({best['Avg Return %']:+.2f}% over {best['Forward']}) — "
            f"Worst = {worst['Asset']} ({worst['Avg Return %']:+.2f}% over {worst['Forward']})"
        )
