import os
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def _load_processed_csv(name: str) -> pd.DataFrame:
    """
    Load a processed CSV from data/processed and return a DataFrame with a DatetimeIndex.
    Assumes the first column is a date if 'Date' is not present.
    """
    path = PROCESSED_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run the pipeline for {name} first.")

    df = pd.read_csv(path)
    if "Date" in df.columns:
        date_col = "Date"
    else:
        date_col = df.columns[0]

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    return df


def _scale_to_0_100(series: pd.Series) -> pd.Series:
    """
    Scale a series linearly to 0–100 based on its historical min/max.
    If min == max, return 50 for all non-NaN entries.
    """
    s = series.copy()
    s = s.replace([np.inf, -np.inf], np.nan)

    min_val = s.min()
    max_val = s.max()

    if pd.isna(min_val) or pd.isna(max_val):
        return pd.Series(np.nan, index=s.index)

    if max_val == min_val:
        out = pd.Series(50.0, index=s.index)
    else:
        out = (s - min_val) / (max_val - min_val) * 100.0

    return out


def _scale_to_0_100_robust(
    series: pd.Series,
    lower_q: float = 0.05,
    upper_q: float = 0.95,
) -> pd.Series:
    """
    Robust 0–100 scaling using clipped percentiles instead of raw min/max.

    Values below the lower_q percentile are treated as the min,
    values above the upper_q percentile are treated as the max.
    If the two percentiles coincide, returns 50 for all non-NaN entries.
    """
    s = series.copy()
    s = s.replace([np.inf, -np.inf], np.nan)

    if s.dropna().empty:
        return pd.Series(np.nan, index=s.index)

    q_low = s.quantile(lower_q)
    q_high = s.quantile(upper_q)

    if pd.isna(q_low) or pd.isna(q_high):
        return pd.Series(np.nan, index=s.index)

    if q_high == q_low:
        return pd.Series(50.0, index=s.index)

    clipped = s.clip(lower=q_low, upper=q_high)
    out = (clipped - q_low) / (q_high - q_low) * 100.0
    return out


def _apply_scaling(
    series: pd.Series,
    mode: str = "full",
    lower_q: float = 0.05,
    upper_q: float = 0.95,
) -> pd.Series:
    """
    Helper to apply either full-history or robust percentile-based scaling.
    mode: "full" or "robust"
    """
    mode = (mode or "full").lower()
    if mode == "robust":
        return _scale_to_0_100_robust(series, lower_q=lower_q, upper_q=upper_q)
    return _scale_to_0_100(series)


# ---------------------------------------------------------
# Fed Liquidity Score
# ---------------------------------------------------------
def _compute_fed_liquidity_score(
    scaling_mode: str = "full",
    robust_lower: float = 0.05,
    robust_upper: float = 0.95,
) -> pd.Series:
    """
    Fed liquidity composite:
    + Fed balance sheet
    - TGA
    - RRP

    Higher values => more net liquidity => more risk-on.
    """
    df = _load_processed_csv("fed_liquidity.csv")

    fed = df.get("Fed_Balance_Sheet")
    tga = df.get("TGA_Balance", df.get("closing_balance"))
    rrp = df.get("RRP_Usage")

    components = []

    if fed is not None and fed.std() > 0:
        components.append((fed - fed.mean()) / fed.std())
    if tga is not None and tga.std() > 0:
        components.append(-(tga - tga.mean()) / tga.std())
    if rrp is not None and rrp.std() > 0:
        components.append(-(rrp - rrp.mean()) / rrp.std())

    if not components:
        return pd.Series(np.nan, index=df.index)

    composite = sum(components) / len(components)
    return _apply_scaling(composite, mode=scaling_mode, lower_q=robust_lower, upper_q=robust_upper)


# ---------------------------------------------------------
# Yield Curve Score
# ---------------------------------------------------------
def _compute_yield_curve_score(
    scaling_mode: str = "full",
    robust_lower: float = 0.05,
    robust_upper: float = 0.95,
) -> pd.Series:
    """
    Yield curve composite:
    + 2s10s spread
    + 3m10y spread

    Steeper curve (more positive spreads) => more risk-on.
    Deep, persistent inversions => risk-off.
    """
    df = _load_processed_csv("yield_curve.csv")

    spreads = []

    if "Spread_2s10s" in df.columns:
        spreads.append(df["Spread_2s10s"])
    if "Spread_3m10y" in df.columns:
        spreads.append(df["Spread_3m10y"])

    if not spreads:
        return pd.Series(np.nan, index=df.index)

    avg_spread = sum(spreads) / len(spreads)
    return _apply_scaling(avg_spread, mode=scaling_mode, lower_q=robust_lower, upper_q=robust_upper)


# ---------------------------------------------------------
# Credit Stress Score
# ---------------------------------------------------------
def _compute_credit_score(
    scaling_mode: str = "full",
    robust_lower: float = 0.05,
    robust_upper: float = 0.95,
) -> pd.Series:
    """
    Credit score based on IG and HY OAS.

    Lower spreads => more risk-on.
    Higher spreads => stress => more risk-off.

    We convert to a risk-on score where high = tighter spreads.
    """
    df = _load_processed_csv("credit_spreads.csv")

    hy = df.get("HY_OAS")
    ig = df.get("IG_OAS")

    if hy is None and ig is None:
        return pd.Series(np.nan, index=df.index)

    components = []
    if hy is not None:
        components.append(-hy)
    if ig is not None:
        components.append(-ig)

    composite = sum(components) / len(components)
    return _apply_scaling(composite, mode=scaling_mode, lower_q=robust_lower, upper_q=robust_upper)


# ---------------------------------------------------------
# FX Liquidity Score
# ---------------------------------------------------------
def _compute_fx_score(
    scaling_mode: str = "full",
    robust_lower: float = 0.05,
    robust_upper: float = 0.95,
) -> pd.Series:
    """
    FX liquidity score using DXY and an EM FX basket.

    - Strong USD (high DXY) tends to be risk-off.
    + Strong EM FX (high EM_FX_Basket) tends to be risk-on.

    We define a composite 'risk-on FX' indicator:
      fx_risk_on = -z(DXY) + z(EM_FX_Basket)

    Then scale to 0–100.
    """
    df = _load_processed_csv("fx_liquidity.csv")

    dxy = df.get("DXY")
    em = df.get("EM_FX_Basket")

    if dxy is None and em is None:
        return pd.Series(np.nan, index=df.index)

    components = []

    if dxy is not None and dxy.std() > 0:
        z_dxy = (dxy - dxy.mean()) / dxy.std()
        components.append(-z_dxy)  # strong USD => lower score
    if em is not None and em.std() > 0:
        z_em = (em - em.mean()) / em.std()
        components.append(z_em)    # strong EM => higher score

    if not components:
        return pd.Series(np.nan, index=df.index)

    composite = sum(components) / len(components)
    return _apply_scaling(composite, mode=scaling_mode, lower_q=robust_lower, upper_q=robust_upper)


# ---------------------------------------------------------
# Funding Stress Score
# ---------------------------------------------------------
def _compute_funding_score(
    scaling_mode: str = "full",
    robust_lower: float = 0.05,
    robust_upper: float = 0.95,
) -> pd.Series:
    """
    Funding stress based on EFFR-SOFR and EFFR-OBFR spreads.

    Higher spreads => more funding stress => risk-off.
    We convert to a risk-on score where lower spreads => higher score.
    """
    df = _load_processed_csv("funding_stress.csv")

    effr_sofr = df.get("EFFR_minus_SOFR")
    effr_obfr = df.get("EFFR_minus_OBFR")

    if effr_sofr is None and effr_obfr is None:
        return pd.Series(np.nan, index=df.index)

    components = []
    if effr_sofr is not None:
        components.append(-effr_sofr)
    if effr_obfr is not None:
        components.append(-effr_obfr)

    composite = sum(components) / len(components)
    return _apply_scaling(composite, mode=scaling_mode, lower_q=robust_lower, upper_q=robust_upper)


# ---------------------------------------------------------
# Volatility Score (VIX + term structure + MOVE)
# ---------------------------------------------------------
def _compute_volatility_score(
    scaling_mode: str = "full",
    robust_lower: float = 0.05,
    robust_upper: float = 0.95,
) -> pd.Series:
    """
    Convert VIX level + term structure + MOVE Index into a 0–100 'volatility regime' score.

    - High VIX, inverted term structure, and high MOVE -> low score (risk-off)
    - Low VIX, contango term structure, and low MOVE  -> higher score (risk-on)
    """
    df = _load_processed_csv("volatility_regimes.csv")

    # Prefer smoothed series if available
    vix = df.get("VIX_Short_SMA5", df.get("VIX_Short"))
    term = df.get("VIX_Term_Ratio_SMA5", df.get("VIX_Term_Ratio"))
    move = df.get("MOVE_SMA20", df.get("MOVE_Index"))

    if vix is None and term is None and move is None:
        return pd.Series(np.nan, index=df.index)

    components = []

    # VIX: high => stress => lower score
    if vix is not None and vix.std() > 0:
        z_vix = (vix - vix.mean()) / vix.std()
        components.append(-z_vix)

    # Term structure: high ratio (front > 3M) => backwardation => stress
    if term is not None and term.std() > 0:
        z_term = (term - term.mean()) / term.std()
        components.append(-z_term)

    # MOVE: high Treasury vol => stress
    if move is not None and move.std() > 0:
        z_move = (move - move.mean()) / move.std()
        components.append(-z_move)

    if not components:
        return pd.Series(np.nan, index=df.index)

    composite = sum(components) / len(components)
    return _apply_scaling(composite, mode=scaling_mode, lower_q=robust_lower, upper_q=robust_upper)


# ---------------------------------------------------------
# Leading Growth Score (orders/inventories + claims)
# ---------------------------------------------------------
def _compute_growth_leading_score(
    scaling_mode: str = "full",
    robust_lower: float = 0.05,
    robust_upper: float = 0.95,
) -> pd.Series:
    """
    Leading growth score based on:
      + Orders_YoY – Inventories_YoY (proxy for ISM New Orders - Inventories)
      - Initial Unemployment Claims (4-week MA)

    To reduce look-ahead bias, we use a 1-period lag for each series
    so that the score only uses information that would have been available
    at or before the observation date.

    Strong orders growth vs inventories and low / stable claims => risk-on.
    Collapsing spread and rising claims => risk-off.
    """
    df = _load_processed_csv("growth_leading.csv")

    ism_spread = df.get("ISM_Spread")
    claims = df.get("Initial_Claims_4WMA", df.get("Initial_Claims"))

    # Apply a one-period lag to approximate "known at time t"
    if ism_spread is not None:
        ism_spread = ism_spread.shift(1)
    if claims is not None:
        claims = claims.shift(1)

    if ism_spread is None and claims is None:
        return pd.Series(np.nan, index=df.index)

    components = []

    if ism_spread is not None and ism_spread.std() > 0:
        z_ism = (ism_spread - ism_spread.mean()) / ism_spread.std()
        components.append(z_ism)  # higher spread => better growth

    if claims is not None and claims.std() > 0:
        z_claims = (claims - claims.mean()) / claims.std()
        components.append(-z_claims)  # higher claims => worse growth

    if not components:
        return pd.Series(np.nan, index=df.index)

    composite = sum(components) / len(components)
    return _apply_scaling(composite, mode=scaling_mode, lower_q=robust_lower, upper_q=robust_upper)


# ---------------------------------------------------------
# Macro Risk Score (main entry point)
# ---------------------------------------------------------
def compute_macro_risk_score(
    scaling_mode: str = "full",
    robust_lower: float = 0.05,
    robust_upper: float = 0.95,
) -> pd.DataFrame:
    """
    Compute component scores and overall macro risk score.

    scaling_mode:
      - "full"   : simple min/max scaling (historical extremes)
      - "robust" : percentile-clipped scaling (less sensitive to outliers)

    Returns a DataFrame with columns:
      - fed_liquidity_score
      - curve_score
      - credit_score
      - fx_score
      - funding_score
      - volatility_score
      - growth_leading_score
      - macro_score
    """
    fed_liq = _compute_fed_liquidity_score(scaling_mode, robust_lower, robust_upper)
    curve = _compute_yield_curve_score(scaling_mode, robust_lower, robust_upper)
    credit = _compute_credit_score(scaling_mode, robust_lower, robust_upper)
    fx = _compute_fx_score(scaling_mode, robust_lower, robust_upper)
    funding = _compute_funding_score(scaling_mode, robust_lower, robust_upper)
    vol = _compute_volatility_score(scaling_mode, robust_lower, robust_upper)
    growth_leading = _compute_growth_leading_score(scaling_mode, robust_lower, robust_upper)

    # Common index
    all_index = fed_liq.index.union(curve.index)
    all_index = all_index.union(credit.index)
    all_index = all_index.union(fx.index)
    all_index = all_index.union(funding.index)
    all_index = all_index.union(vol.index)
    all_index = all_index.union(growth_leading.index)

    scores = pd.DataFrame(index=all_index)
    scores["fed_liquidity_score"] = fed_liq.reindex(all_index)
    scores["curve_score"] = curve.reindex(all_index)
    scores["credit_score"] = credit.reindex(all_index)
    scores["fx_score"] = fx.reindex(all_index)
    scores["funding_score"] = funding.reindex(all_index)
    scores["volatility_score"] = vol.reindex(all_index)
    scores["growth_leading_score"] = growth_leading.reindex(all_index)

    # Fill forward so higher-frequency indicators lead without causing NaNs
    scores = scores.sort_index().ffill()

    # Weights for each component (sum ≈ 1)
    weights: Dict[str, float] = {
        "fed_liquidity_score": 0.22,
        "curve_score": 0.18,
        "credit_score": 0.18,
        "fx_score": 0.13,
        "funding_score": 0.09,
        "volatility_score": 0.10,
        "growth_leading_score": 0.10,
    }

    weight_series = pd.Series(weights)

    macro_scores = []
    for _, row in scores.iterrows():
        valid = row.dropna()
        if valid.empty:
            macro_scores.append(np.nan)
            continue

        # Filter weights down to components actually present for this date
        w = weight_series.loc[valid.index]
        w = w / w.sum()
        macro_scores.append((valid * w).sum())

    scores["macro_score"] = macro_scores

    return scores
