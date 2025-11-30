import pandas as pd
import numpy as np
from pathlib import Path

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "processed"


def _zscore(series: pd.Series) -> pd.Series:
    """Standardize a series to z-scores, safely."""
    s = series.astype(float)
    return (s - s.mean()) / (s.std(ddof=0) + 1e-9)


def _safe_pct_change(series: pd.Series, periods: int = 30) -> pd.Series:
    return series.astype(float).pct_change(periods=periods)


def _safe_diff(series: pd.Series, periods: int = 30) -> pd.Series:
    return series.astype(float).diff(periods=periods)


def _load_csv(name: str, date_col: str = "record_date") -> pd.DataFrame:
    path = DATA_DIR / name
    df = pd.read_csv(path)
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col).sort_index()
    else:
        # fall back to index-based if needed
        df.index = pd.to_datetime(df.index)
    return df


def compute_macro_risk_score() -> pd.DataFrame:
    """
    Combines Fed plumbing, yield curve, credit spreads, and FX
    into a normalized 0–100 Macro Risk Score.

    Returns a DataFrame indexed by date with:
      - macro_score         (0–100)
      - fed_liquidity_score
      - curve_score
      - credit_score
      - fx_score
    """

    # ----------------------------
    # 1) Load all processed data
    # ----------------------------
    fed = _load_csv("fed_liquidity.csv")          # Fed_Balance_Sheet, closing_balance(TGA), RRP_Usage
    yc = _load_csv("yield_curve.csv")             # expect column: "Spread_2s10s" (in bps or %)
    cs = _load_csv("credit_spreads.csv")          # expect e.g. "IG_OAS", "HY_OAS"
    fx = _load_csv("fx_liquidity.csv", "Date")    # expect "DXY" and maybe "EM_FX"

    # standardize column names a bit (only if they exist)
    fed_cols = fed.columns.tolist()
    if "closing_balance" in fed_cols and "TGA_Balance" not in fed_cols:
        fed = fed.rename(columns={"closing_balance": "TGA_Balance"})

    # ----------------------------
    # 2) Build individual factor scores
    # ----------------------------

    # Fed Liquidity: Fed balance sheet ↑ (good), TGA ↑ (bad), RRP ↑ (bad)
    # use 30-day changes smoothed over 30 days
    fed_liq = pd.DataFrame(index=fed.index)

    if "Fed_Balance_Sheet" in fed.columns:
        fed_bs_trend = _safe_pct_change(fed["Fed_Balance_Sheet"], 30).rolling(30).mean()
        fed_liq["fed_bs_score"] = _zscore(fed_bs_trend)

    if "TGA_Balance" in fed.columns:
        # rising TGA drains liquidity → negative sign
        tga_trend = _safe_diff(fed["TGA_Balance"], 30).rolling(30).mean()
        fed_liq["tga_score"] = -_zscore(tga_trend)

    if "RRP_Usage" in fed.columns:
        # rising RRP → cash parked at Fed → risk-off
        rrp_trend = _safe_diff(fed["RRP_Usage"], 30).rolling(30).mean()
        fed_liq["rrp_score"] = -_zscore(rrp_trend)

    # Aggregate Fed liquidity score (mean of available components)
    fed_liq["fed_liquidity_score"] = fed_liq.mean(axis=1)

    # Yield Curve: steeper (more positive) = risk-on
    curve = pd.DataFrame(index=yc.index)
    if "Spread_2s10s" in yc.columns:
        curve["curve_score"] = _zscore(yc["Spread_2s10s"].astype(float))
    elif "spread_2s10s" in yc.columns:
        curve["curve_score"] = _zscore(yc["spread_2s10s"].astype(float))

    # Credit Spreads: tightening = risk-on, widening = risk-off
    credit = pd.DataFrame(index=cs.index)
    hy_col = None
    if "HY_OAS" in cs.columns:
        hy_col = "HY_OAS"
    elif "hy_oas" in cs.columns:
        hy_col = "hy_oas"

    if hy_col:
        # rising HY spreads = risk-off → negative sign
        hy_trend = _safe_diff(cs[hy_col], 30).rolling(30).mean()
        credit["credit_score"] = -_zscore(hy_trend)

    # FX / Dollar: strong USD = risk-off
    fx_df = pd.DataFrame(index=fx.index)
    if "DXY" in fx.columns:
        dxy_trend = _safe_diff(fx["DXY"], 30).rolling(30).mean()
        fx_df["fx_score"] = -_zscore(dxy_trend)

    # ----------------------------
    # 3) Align all scores on common date index
    # ----------------------------
    combined = pd.concat(
        [
            fed_liq[["fed_liquidity_score"]],
            curve.get("curve_score"),
            credit.get("credit_score"),
            fx_df.get("fx_score"),
        ],
        axis=1,
        join="inner",
    ).dropna()

    # fill any remaining gaps with forward-fill to keep it smooth
    combined = combined.ffill()

    # ----------------------------
    # 4) Combine into single Macro Risk Score (0–100)
    # ----------------------------
    # You can tweak these weights later
    weights = {
        "fed_liquidity_score": 0.30,
        "curve_score": 0.20,
        "credit_score": 0.25,
        "fx_score": 0.25,
    }

    # weighted sum of z-scores
    weighted = 0
    for col, w in weights.items():
        if col in combined.columns:
            weighted = weighted + w * combined[col]

    # compress extreme z-scores
    weighted = weighted.clip(-3, 3)

    # map z-score-ish range [-3, 3] → [20, 80] then clip 0–100
    macro_score = 50 + (weighted * 10)
    macro_score = macro_score.clip(0, 100)

    combined["macro_score"] = macro_score

    return combined
