# pipelines/funding_stress.py

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------
# Ensure project root is on sys.path so `utils.*` imports work
# ---------------------------------------------------------
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.fred import get_fred_connection  # type: ignore[import]

fred = get_fred_connection()


def fetch_funding_series() -> pd.DataFrame:
    """
    Fetch key NY Fed-style overnight rates (via FRED) and build simple stress spreads.

    Raw series:
        EFFR - Effective Federal Funds Rate          (FRED code: "EFFR")
        SOFR - Secured Overnight Financing Rate      (FRED code: "SOFR")
        OBFR - Overnight Bank Funding Rate           (FRED code: "OBFR")

    Derived columns:
        EFFR_minus_SOFR  -> funding stress between unsecured vs secured
        EFFR_minus_OBFR  -> stress between fed funds & broader bank funding
    """
    effr = fred.get_series("EFFR")
    sofr = fred.get_series("SOFR")
    obfr = fred.get_series("OBFR")

    df = pd.DataFrame(
        {
            "EFFR": effr,
            "SOFR": sofr,
            "OBFR": obfr,
        }
    )

    # Clean up index and basic NA handling
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df.dropna(how="all")

    # Keep days where at least EFFR and SOFR exist
    df = df.dropna(subset=["EFFR", "SOFR"], how="any")

    # Spreads – positive spreads = more stress (EFFR trading rich vs SOFR/OBFR)
    df["EFFR_minus_SOFR"] = df["EFFR"] - df["SOFR"]
    df["EFFR_minus_OBFR"] = df["EFFR"] - df["OBFR"]

    return df


def main() -> None:
    df = fetch_funding_series()

    out_dir = Path(project_root) / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "funding_stress.csv"
    df.to_csv(out_path, index_label="Date")
    print(f"✔ Saved funding stress data to: {out_path}")


if __name__ == "__main__":
    main()
