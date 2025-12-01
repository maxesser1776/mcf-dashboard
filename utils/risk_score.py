# utils/risk_score.py

from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
import warnings

# Optional: silence FutureWarnings from pandas joins/index dtype
warnings.simplefilter("ignore", category=FutureWarning)

# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "processed"


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def _load_csv(name: str) -> pd.DataFrame:
    """
    Load a processed CSV and return a DataFrame indexed by date.

    Tries columns: record_date, Date, date.
    Falls back to first column as the date index.
    """
    path = DATA_DIR / name
    df = pd.read_csv(path)

    for col in ["record_date", "Date", "date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df = df.sort_values(col)
            df = df.set_index(col)
            return df

    # Fallback: assume first column is date-like
    df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    df = df.sort_values(df.columns[0])
    df = df.set_index(df.columns[0])
    return df


def _safe_pct_change(series: pd.Series, periods: int = 1) -> pd.Series:
    """
    Robust percent change that safely handles non-numeric values.
    """
    s = pd.to_numeric(series, errors="coerce")
    return s.pct_change(periods=periods)


def _zscore(series: pd.Series) -> pd.Series:
    """
    Standard z-score, returns all zeros if variance is zero / NaN.
    """
    s = pd.to_numeric(series, errors="coerce")
    mean = s.mean()
    std = s.std(ddof=0)

    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=s.index)

    return (s - mean) / std


# ---------------------------------------------------------
# Main API
# ---------------------------------------------------------
def compute_macro_risk_score() -> pd.DataFrame:
    """
    Compute macro risk sub-scores and a 0–100 composite Macro Risk Score.

    Uses:
        fed_liquidity.csv
        yield_curve.csv
        credit_spreads.csv
        fx_liquidity.csv
        funding_stress.csv

    Returns a DataFrame indexed by date with columns:
        fed_liquidity_score
        curve_score
        credit_score
        fx_score
        funding_score
        macro_score
    """
    # -------- Load all CSVs --------
    fed = _load_csv("fed_liquidity.csv")
    yc = _load_csv("yield_curve.csv")
    credit = _load_csv("credit_spreads.csv")
    fx = _load_csv("fx_liquidity.csv")
    funding = _load_csv("funding_stress.csv")

    # Standardize index types to datetime
    for d in (fed, yc, credit, fx, funding):
        d.index = pd.to_datetime(d.index)

    # Normalize TGA column name if needed
    if "closing_balance" in fed.columns and "TGA_Balance" not in fed.columns:
        fed = fed.rename(columns={"closing_balance": "TGA_Balance"})

    # -------- Join dataframes SEQUENTIALLY (no suffixes) --------
    # Start from fed and inner-join each dataset on the date index
    df = fed.join(yc, how="inner")
    df = df.join(credit, how="inner")
    df = df.join(fx, how="inner")
    df = df.join(funding, how="inner")

    df = df.sort_index()
    df = df.dropna(how="all")

    scores: Dict[str, pd.Series] = {}

    # ---------------- Fed Liquidity Score -----------------
    # Fed_Balance_Sheet up = good
    # TGA_Balance & RRP_Usage down = good (less cash locked away)
    fed_parts = []

    if "Fed_Balance_Sheet" in df.columns:
        fed_trend = _safe_pct_change(df["Fed_Balance_Sheet"], periods=20)
        fed_parts.append(_zscore(fed_trend))

    if "TGA_Balance" in df.columns:
        tga_trend = -_safe_pct_change(df["TGA_Balance"], periods=20)
        fed_parts.append(_zscore(tga_trend))

    if "RRP_Usage" in df.columns:
        rrp_trend = -_safe_pct_change(df["RRP_Usage"], periods=20)
        fed_parts.append(_zscore(rrp_trend))

    if fed_parts:
        scores["fed_liquidity_score"] = pd.concat(fed_parts, axis=1).mean(axis=1)
    else:
        scores["fed_liquidity_score"] = pd.Series(0.0, index=df.index)

    # ---------------- Yield Curve Score -------------------
    # Steeper / less inverted = good
    curve_parts = []

    if "Spread_2s10s" in df.columns:
        curve_parts.append(_zscore(df["Spread_2s10s"]))

    if "Spread_3m10y" in df.columns:
        curve_parts.append(_zscore(df["Spread_3m10y"]))

    if curve_parts:
        scores["curve_score"] = pd.concat(curve_parts, axis=1).mean(axis=1)
    else:
        scores["curve_score"] = pd.Series(0.0, index=df.index)

    # ---------------- Credit Stress Score -----------------
    # Wider spreads = bad, so we flip sign.
    credit_parts = []

    if "IG_OAS" in df.columns:
        credit_parts.append(-_zscore(df["IG_OAS"]))

    if "HY_OAS" in df.columns:
        credit_parts.append(-_zscore(df["HY_OAS"]))

    if credit_parts:
        scores["credit_score"] = pd.concat(credit_parts, axis=1).mean(axis=1)
    else:
        scores["credit_score"] = pd.Series(0.0, index=df.index)

    # ---------------- FX Liquidity Score ------------------
    # Strong USD (high DXY) = tighter global USD liquidity (bad)
    # Strong EM_FX_Basket = risk-on (good)
    fx_parts = []

    if "DXY" in df.columns:
        fx_parts.append(-_zscore(df["DXY"]))

    if "EM_FX_Basket" in df.columns:
        fx_parts.append(_zscore(df["EM_FX_Basket"]))

    if fx_parts:
        scores["fx_score"] = pd.concat(fx_parts, axis=1).mean(axis=1)
    else:
        scores["fx_score"] = pd.Series(0.0, index=df.index)

    # ---------------- Funding Stress Score ----------------
    # Larger EFFR–SOFR / EFFR–OBFR spreads = more stress (bad).
    funding_parts = []

    if "EFFR_minus_SOFR" in df.columns:
        funding_parts.append(-_zscore(df["EFFR_minus_SOFR"]))

    if "EFFR_minus_OBFR" in df.columns:
        funding_parts.append(-_zscore(df["EFFR_minus_OBFR"]))

    if funding_parts:
        scores["funding_score"] = pd.concat(funding_parts, axis=1).mean(axis=1)
    else:
        scores["funding_score"] = pd.Series(0.0, index=df.index)

    # ---------------- Assemble & Composite ----------------
    score_df = pd.DataFrame(scores).sort_index()

    # Equal-weight the five subscores, then map z-score to 0–100
    avg_z = score_df.mean(axis=1)

    # 1 z-score ≈ 15 points -> typical range ~20–80
    macro_scaled = 50 + 15 * avg_z
    macro_scaled = macro_scaled.clip(lower=0, upper=100)

    score_df["macro_score"] = macro_scaled

    return score_df