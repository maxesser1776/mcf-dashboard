# dashboard/app.py

import os
import sys
import traceback

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------
# Ensure project root is on sys.path so `utils.*` imports work
# ---------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.fetch import load_processed_csv
from utils.plot import single_line_plot, dual_axis_plot
from utils.risk_score import compute_macro_risk_score

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
    "Data freshness depends on provider: market data is daily; macro data is weekly/monthly."
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
    "lean risk-off. The score updates whenever the pipelines are run; underlying series are a mix of daily "
    "(yields, credit, FX, funding, volatility) and monthly/weekly (growth, inflation, orders, claims)."
)

try:
    macro_df = compute_macro_risk_score()
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
            st.markdown(
                "🟢 **Risk-On Environment**  \n"
                "Liquidity, volatility, and macro conditions are broadly supportive.  \n"
                "Typical tilt: more equities, small caps, EM, and cyclicals."
            )
        elif latest_score <= 35:
            st.markdown(
                "🔴 **Risk-Off Environment**  \n"
                "Liquidity, credit, or volatility conditions are deteriorating.  \n"
                "Typical tilt: Treasuries, USD, defensives; reduce high-beta exposure."
            )
        else:
            st.markdown(
                "🟡 **Neutral / Mixed Environment**  \n"
                "Signals are mixed across liquidity, curve, credit, FX, volatility, and growth.  \n"
                "Typical tilt: barbell of quality equities plus duration (Treasuries)."
            )

        st.caption(
            "Component scores are z-scored or normalized per factor, then combined with weights. "
            "This is a regime indicator, not a precise return forecast."
        )

        if "fed_liquidity_score" in latest.index:
            st.write(f"- Fed liquidity score: {latest['fed_liquidity_score']:.2f}")
        if "curve_score" in latest.index:
            st.write(f"- Yield curve score: {latest['curve_score']:.2f}")
        if "credit_score" in latest.index:
            st.write(f"- Credit stress score: {latest['credit_score']:.2f}")
        if "fx_score" in latest.index:
            st.write(f"- FX liquidity score: {latest['fx_score']:.2f}")
        if "funding_score" in latest.index:
            st.write(f"- Funding stress score: {latest['funding_score']:.2f}")
        if "volatility_score" in latest.index:
            st.write(f"- Volatility score: {latest['volatility_score']:.2f}")
        if "growth_leading_score" in latest.index:
            st.write(f"- Leading growth score: {latest['growth_leading_score']:.2f}")

except Exception as e:
    traceback.print_exc()
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
        "Leading Growth Signals",
        "Volatility & Market Stress",
    ],
)

st.sidebar.markdown(
    "v0.3 – Macro Capital Flows Dashboard. "
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
        "Update cadence: balance sheet weekly, TGA and RRP daily (with a short lag)."
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
        st.subheader("Fed Balance Sheet & TGA")
        st.caption(
            "Fed assets (QE/QT) push liquidity into or out of the system, while changes in the Treasury "
            "General Account (TGA) can temporarily drain or add reserves. "
            "Fed balance sheet data is typically updated weekly; TGA balances are daily or near-daily "
            "from Treasury sources."
        )
        fig = dual_axis_plot(
            df_plot,
            x=date_col,
            y1="Fed_Balance_Sheet",
            y2="TGA_Balance",
            title="Fed Balance Sheet (Assets) and Treasury General Account",
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

    st.subheader("Funding Stress: EFFR vs SOFR / OBFR")
    st.caption(
        "These spreads compare the effective fed funds rate to secured and overnight benchmarks. "
        "Persistent positive spreads can indicate tightening conditions or stress in unsecured funding. "
        "EFFR, SOFR, and OBFR are updated daily with roughly a one-day lag."
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
                    title="EFFR - SOFR Spread",
                    y_label="pct points",
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
                    title="EFFR - OBFR Spread",
                    y_label="pct points",
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

            stress_level = "🟢 **Normal** – Funding markets look orderly."
            if effr_sofr > 0.10 or effr_obfr > 0.10:
                stress_level = "🟠 **Elevated Stress** – Fed funds rich vs SOFR/OBFR; watch funding closely."
            if effr_sofr > 0.25 or effr_obfr > 0.25:
                stress_level = "🔴 **High Stress** – Significant dislocation; markets leaning on safer collateral."

            st.write(
                f"- Latest EFFR − SOFR: `{effr_sofr:.3f}`  \n"
                f"- Latest EFFR − OBFR: `{effr_obfr:.3f}`  \n\n"
                f"{stress_level}"
            )

            st.caption(
                "Short spikes can happen around month end or policy events. "
                "Sustained widening is more concerning than one day noise."
            )
        else:
            st.info("No recent non-NaN funding spread values available to interpret.")


# ---------------------------------------------------------
# 3. Yield Curve & Policy
# ---------------------------------------------------------
elif section == "Yield Curve & Policy":
    st.header("Yield Curve & Policy")
    st.caption(
        "The yield curve compares long term and short term interest rates. "
        "Inversions (when short rates exceed long rates) have historically been a reliable recession signal. "
        "Here we track the classic 2s10s and 3m10y spreads. Treasury constant-maturity yields "
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
            title="2s10s Yield Curve (10Y - 2Y)",
            y_label="Basis Points",
        )
        st.plotly_chart(fig_yc, use_container_width=True)
        st.caption(
            "Positive values mean a normal curve with long rates above short rates. "
            "Sustained negative values (inversion) often precede economic slowdowns. "
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
            title="3m10y Yield Curve (10Y - 3M)",
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
        "with about a one-business-day lag."
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
            "Fast widening in HY, especially if IG also widens, often aligns with risk-off regimes. "
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
    st.header("FX & Global Stress")
    st.caption(
        "The dollar sits at the center of global funding. A strong, rapidly rising USD can tighten "
        "financial conditions for the rest of the world. EM FX trends help show whether global risk "
        "appetite is healthy or under pressure. "
        "DXY and EM FX series are pulled from market data (via Yahoo Finance) and update on each trading day."
    )

    try:
        fx = load_processed_csv("fx_liquidity.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    date_col = _get_date_column(fx)
    fx[date_col] = pd.to_datetime(fx[date_col])

    if "DXY" in fx.columns:
        st.subheader("US Dollar Index (DXY)")
        fig_dxy = single_line_plot(
            fx,
            x=date_col,
            y="DXY",
            title="US Dollar Index (DXY)",
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
        st.subheader("EM FX Basket (Inverse Stress Proxy)")
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
    st.header("Growth & Inflation")
    st.caption(
        "This page tracks real activity and price trends. The idea is to see whether we are in an "
        "overheating inflationary phase, a disinflationary soft landing, or a growth slowdown. "
        "Industrial production, CPI, and PCE are all monthly series that update when new releases "
        "are published (typically once per month, with a lag)."
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
            "Industrial production YoY is a classic real-economy growth indicator. "
            "Falling or negative values often coincide with slowdowns or recessions. "
            "This series is updated monthly after the Fed’s G.17 release."
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
            "CPI is released monthly, usually mid-month for the prior month."
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
            "Core PCE YoY is the Fed’s preferred inflation gauge. "
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
        "This page focuses on forward-looking growth indicators: manufacturers' orders vs inventories and "
        "Initial Unemployment Claims. A falling orders–inventories spread and rising claims often precede "
        "broader slowdowns or recessions. Orders/inventories are monthly; claims are weekly."
    )

    try:
        gl = load_processed_csv("growth_leading.csv")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    date_col = _get_date_column(gl)
    gl[date_col] = pd.to_datetime(gl[date_col])

    # Filter to non-null ISM_Spread rows so the line actually shows
    if "ISM_Spread" in gl.columns:
        gl_ism = gl.dropna(subset=["ISM_Spread"]).copy()
        if not gl_ism.empty:
            st.subheader("Orders vs Inventories Growth Spread")
            fig_ism = single_line_plot(
                gl_ism,
                x=date_col,
                y="ISM_Spread",
                title="Manufacturers' Orders YoY – Inventories YoY",
                y_label="Percentage Points",
            )
            st.plotly_chart(fig_ism, use_container_width=True)
            st.caption(
                "This spread proxies the ISM New Orders – Inventories signal using manufacturers' orders and "
                "inventories growth. Large positive values are associated with strong forward demand; "
                "falling or negative values suggest weakening orders relative to stock levels. "
                "Updated monthly from Census manufacturing data."
            )
        else:
            st.info("ISM_Spread is present but all values are NaN.")
    else:
        st.info("ISM_Spread column missing in growth_leading.csv")

    # Filter to non-null claims rows
    if "Initial_Claims_4WMA" in gl.columns:
        gl_claims = gl.dropna(subset=["Initial_Claims_4WMA"]).copy()
        if not gl_claims.empty:
            st.subheader("Initial Jobless Claims (4-week Moving Average)")
            fig_claims = single_line_plot(
                gl_claims,
                x=date_col,
                y="Initial_Claims_4WMA",
                title="Initial Unemployment Claims (4-week MA)",
                y_label="Number of Claims",
            )
            st.plotly_chart(fig_claims, use_container_width=True)
            st.caption(
                "Initial unemployment claims are one of the fastest labor-market indicators. "
                "A sustained uptrend in the 4-week moving average often signals increasing stress in the real economy. "
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
    st.header("Volatility & Market Stress")
    st.caption(
        "This page tracks implied equity volatility (VIX), the shape of the VIX curve, and Treasury rate volatility "
        "(MOVE Index). Front-end VIX spikes, curve inversion (front > 3M), and high MOVE levels are classic signs of "
        "short-term market stress. Data comes from CBOE VIX indices and the ICE BofAML MOVE Index via Yahoo Finance "
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
        st.subheader("Front-Month VIX")
        fig_vix = single_line_plot(
            vol,
            x=date_col,
            y="VIX_Short",
            title="VIX (Front-Month Implied Volatility)",
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
        st.subheader("VIX Term Structure (Front / 3M)")
        fig_term = single_line_plot(
            vol,
            x=date_col,
            y="VIX_Term_Ratio",
            title="VIX Term Structure Ratio (Front / 3M)",
            y_label="Ratio",
        )
        st.plotly_chart(fig_term, use_container_width=True)
        st.caption(
            "When the ratio is below 1, the curve is in contango (front < 3M), which is typical in calm markets. "
            "When the ratio moves above 1 and stays there, the curve is in backwardation and often reflects "
            "acute risk-off conditions. This ratio is calculated daily from VIX and VIX3M."
        )
    else:
        st.info("VIX_Term_Ratio column missing in volatility_regimes.csv")

    if "MOVE_Index" in vol.columns:
        st.subheader("MOVE Index (Treasury Volatility)")
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
