# utils/risk_score.py

import os
from pathlib import Path
from typing import Dict, List

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


# ---------------------------------------------------------
# Fed Liquidity Score
# ---------------------------------------------------------
def _compute_fed_liquidity_score() -> pd.Series:
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

    if fed is not None:
        components.append((fed - fed.mean()) / fed.std())
    if tga is not None:
        components.append(- (tga - tga.mean()) / tga.std())
    if rrp is not None:
        components.append(- (rrp - rrp.mean()) / rrp.std())

    if not components:
        return pd.Series(np.nan, index=df.index)

    composite = sum(components) / len(components)
    return _scale_to_0_100(composite)


# ---------------------------------------------------------
# Yield Curve Score
# ---------------------------------------------------------
def _compute_yield_curve_score() -> pd.Series:
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
    return _scale_to_0_100(avg_spread)


# ---------------------------------------------------------
# Credit Stress Score
# ---------------------------------------------------------
def _compute_credit_score() -> pd.Series:
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
    return _scale_to_0_100(composite)


# ---------------------------------------------------------
# FX Liquidity Score
# ---------------------------------------------------------
def _compute_fx_score() -> pd.Series:
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
    return _scale_to_0_100(composite)


# ---------------------------------------------------------
# Funding Stress Score
# ---------------------------------------------------------
def _compute_funding_score() -> pd.Series:
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
    return _scale_to_0_100(composite)


# ---------------------------------------------------------
# Volatility Score (VIX + term structure)
# ---------------------------------------------------------
def _compute_volatility_score() -> pd.Series:
    """
    Convert VIX level + term structure into a 0–100 'volatility regime' score.

    - High VIX and inverted term structure -> low score (risk-off)
    - Low VIX and contango term structure -> higher score (risk-on)
    """
    df = _load_processed_csv("volatility_regimes.csv")

    # Prefer smoothed series if available
    vix = df.get("VIX_Short_SMA5", df.get("VIX_Short"))
    term = df.get("VIX_Term_Ratio_SMA5", df.get("VIX_Term_Ratio"))

    if vix is None and term is None:
        return pd.Series(np.nan, index=df.index)

    # Compute simple z-scores
    components = []

    if vix is not None and vix.std() > 0:
        z_vix = (vix - vix.mean()) / vix.std()
        components.append(-z_vix)  # high VIX => more stress => lower score
    if term is not None and term.std() > 0:
        z_term = (term - term.mean()) / term.std()
        components.append(-z_term)  # high term ratio (backwardation) => stress

    if not components:
        return pd.Series(np.nan, index=df.index)

    composite = sum(components) / len(components)
    return _scale_to_0_100(composite)


# ---------------------------------------------------------
# Macro Risk Score (main entry point)
# ---------------------------------------------------------
def compute_macro_risk_score() -> pd.DataFrame:
    """
    Compute component scores and overall macro risk score.

    Returns a DataFrame with columns:
      - fed_liquidity_score
      - curve_score
      - credit_score
      - fx_score
      - funding_score
      - volatility_score
      - macro_score
    """
    # Compute individual scores
    fed_liq = _compute_fed_liquidity_score()
    curve = _compute_yield_curve_score()
    credit = _compute_credit_score()
    fx = _compute_fx_score()
    funding = _compute_funding_score()
    vol = _compute_volatility_score()

    # Build a common index (outer join on dates)
    all_index = fed_liq.index.union(curve.index)
    all_index = all_index.union(credit.index)
    all_index = all_index.union(fx.index)
    all_index = all_index.union(funding.index)
    all_index = all_index.union(vol.index)

    scores = pd.DataFrame(index=all_index)
    scores["fed_liquidity_score"] = fed_liq.reindex(all_index)
    scores["curve_score"] = curve.reindex(all_index)
    scores["credit_score"] = credit.reindex(all_index)
    scores["fx_score"] = fx.reindex(all_index)
    scores["funding_score"] = funding.reindex(all_index)
    scores["volatility_score"] = vol.reindex(all_index)

    # Forward-fill to avoid gaps where higher-frequency data leads
    scores = scores.sort_index().ffill()

    # Weights for each component (tune to taste)
    weights: Dict[str, float] = {
        "fed_liquidity_score": 0.25,
        "curve_score": 0.20,
        "credit_score": 0.20,
        "fx_score": 0.15,
        "funding_score": 0.10,
        "volatility_score": 0.10,
    }

    # Use only available columns for each row
    weight_series = pd.Series(weights)

    macro_scores = []
    for idx, row in scores.iterrows():
        valid = row.dropna()
        if valid.empty:
            macro_scores.append(np.nan)
            continue

        # Filter weights to valid components
        w = weight_series.loc[valid.index]
        w = w / w.sum()
        macro_scores.append((valid * w).sum())

    scores["macro_score"] = macro_scores

    return scores
