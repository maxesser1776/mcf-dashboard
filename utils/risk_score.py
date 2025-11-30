# utils/risk_score.py

import numpy as np
import pandas as pd

from .fetch import load_processed_csv


def _safe_pct_change(series: pd.Series, periods: int = 1) -> pd.Series:
    """
    Robust percent-change wrapper:
    - casts to float
    - uses fill_method=None to avoid deprecated padding behavior
    """
    if series is None:
        return pd.Series(dtype=float)

    s = pd.to_numeric(series, errors="coerce")

    if not isinstance(s, pd.Series):
        s = pd.Series(s)

    return s.pct_change(periods=periods, fill_method=None)


def _zscore(series: pd.Series, index=None) -> pd.Series:
    """
    Standard z-score with NaN-safe behavior.

    Always returns a pandas Series with a well-defined index.
    If `index` is provided, the result is reindexed to that index and NaNs filled with 0.
    """
    if series is None:
        out = pd.Series(dtype=float)
    else:
        if not isinstance(series, pd.Series):
            series = pd.Series(series)
        s = pd.to_numeric(series, errors="coerce")
        mean = s.mean()
        std = s.std()

        if std == 0 or np.isnan(std):
            out = pd.Series(0.0, index=s.index)
        else:
            out = (s - mean) / std

    if index is not None:
        out = out.reindex(index).fillna(0.0)
    return out


def _prepare_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Make sure each DF is indexed by a datetime-like index called 'Date' if possible.
    """
    df = df.copy()

    for col in ["record_date", "Date", "date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
            df = df.set_index(col)
            df.index.name = "Date"
            return df.sort_index()

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    df.index.name = "Date"
    return df.sort_index()


def compute_macro_risk_score() -> pd.DataFrame:
    """
    Compute a 0–100 Macro Risk Score based on:

    • Fed liquidity (Fed balance sheet, TGA, RRP)
    • Yield curve (2s10s, 3m10y)
    • Credit spreads (IG, HY)
    • FX / USD liquidity (DXY, EM FX basket)

    Returns a DataFrame indexed by Date with columns:
    - fed_liquidity_score
    - curve_score
    - credit_score
    - fx_score
    - macro_score
    """

    # -----------------------------
    # Load processed CSVs
    # -----------------------------
    fed = _prepare_index(load_processed_csv("fed_liquidity.csv"))
    yc = _prepare_index(load_processed_csv("yield_curve.csv"))
    cs = _prepare_index(load_processed_csv("credit_spreads.csv"))
    fx = _prepare_index(load_processed_csv("fx_liquidity.csv"))

    # Align on common dates
    combined_index = fed.index
    combined_index = combined_index.intersection(yc.index)
    combined_index = combined_index.intersection(cs.index)
    combined_index = combined_index.intersection(fx.index)

    combined_index = combined_index.sort_values()

    if len(combined_index) == 0:
        # No overlap in dates; return empty frame
        return pd.DataFrame(
            columns=[
                "fed_liquidity_score",
                "curve_score",
                "credit_score",
                "fx_score",
                "macro_score",
            ]
        )

    fed = fed.loc[combined_index]
    yc = yc.loc[combined_index]
    cs = cs.loc[combined_index]
    fx = fx.loc[combined_index]

    # Convenience zeros
    zeros = pd.Series(0.0, index=combined_index)

    # -----------------------------
    # Fed Liquidity Score
    # -----------------------------
    fed_parts = []

    if "Fed_Balance_Sheet" in fed.columns:
        s = fed["Fed_Balance_Sheet"]
        trend = _safe_pct_change(s, periods=13)
        fed_parts.append(_zscore(trend, index=combined_index))

    if "TGA_Balance" in fed.columns:
        s = fed["TGA_Balance"]
        trend = -_safe_pct_change(s, periods=13)  # high TGA = drain
        fed_parts.append(_zscore(trend, index=combined_index))

    if "RRP_Usage" in fed.columns:
        s = fed["RRP_Usage"]
        trend = -_safe_pct_change(s, periods=13)  # high RRP = drain
        fed_parts.append(_zscore(trend, index=combined_index))

    if fed_parts:
        fed_liquidity_z = sum(fed_parts) / len(fed_parts)
    else:
        fed_liquidity_z = zeros.copy()

    # -----------------------------
    # Yield Curve Score
    # -----------------------------
    curve_parts = []

    if "Spread_2s10s" in yc.columns:
        curve_parts.append(_zscore(yc["Spread_2s10s"], index=combined_index))

    if "Spread_3m10y" in yc.columns:
        curve_parts.append(_zscore(yc["Spread_3m10y"], index=combined_index))

    if curve_parts:
        curve_z = sum(curve_parts) / len(curve_parts)
    else:
        curve_z = zeros.copy()

    # -----------------------------
    # Credit Stress Score
    # -----------------------------
    credit_parts = []

    if "IG_OAS" in cs.columns:
        credit_parts.append(_zscore(cs["IG_OAS"], index=combined_index))

    if "HY_OAS" in cs.columns:
        credit_parts.append(_zscore(cs["HY_OAS"], index=combined_index))

    if credit_parts:
        credit_stress_z = -sum(credit_parts) / len(credit_parts)
    else:
        credit_stress_z = zeros.copy()

    # -----------------------------
    # FX / USD Liquidity Score
    # -----------------------------
    fx_parts_pos = []
    fx_parts_neg = []

    # Strong dollar = risk-off -> negative contribution
    if "DXY" in fx.columns:
        fx_parts_neg.append(_zscore(fx["DXY"], index=combined_index))

    # Strong EM FX basket = risk-on -> positive contribution
    if "EM_FX_Basket" in fx.columns:
        fx_parts_pos.append(_zscore(fx["EM_FX_Basket"], index=combined_index))

    if fx_parts_pos or fx_parts_neg:
        pos = sum(fx_parts_pos) / max(len(fx_parts_pos), 1)
        neg = sum(fx_parts_neg) / max(len(fx_parts_neg), 1)
        fx_liquidity_z = pos - neg
    else:
        fx_liquidity_z = zeros.copy()

    # -----------------------------
    # Combine into Macro Score
    # -----------------------------
    combined_z = (
        fed_liquidity_z
        + curve_z
        + credit_stress_z
        + fx_liquidity_z
    ) / 4.0

    macro_score = 50 + 15 * combined_z
    macro_score = macro_score.clip(lower=0, upper=100)
    macro_score = macro_score.fillna(50.0)  # neutral fallback if anything slipped through

    out = pd.DataFrame(
        {
            "fed_liquidity_score": fed_liquidity_z,
            "curve_score": curve_z,
            "credit_score": credit_stress_z,
            "fx_score": fx_liquidity_z,
            "macro_score": macro_score,
        },
        index=combined_index,
    )

    out.index.name = "Date"
    return out.sort_index()
