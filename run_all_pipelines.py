# run_all_pipelines.py

"""
Run all data pipelines to refresh data/processed/*.csv

This is used both locally and by GitHub Actions.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable  # whatever python is running this script

PIPELINE_SCRIPTS = [
    "pipelines/fed_plumbing.py",
    "pipelines/yield_curve.py",
    "pipelines/credit_spreads.py",
    "pipelines/fx_liquidity.py",
    "pipelines/macro_core.py",
    "pipelines/funding_stress.py",
    "pipelines/volatility_regimes.py"
]


def run_pipeline(script_rel_path: str) -> int:
    script_path = BASE_DIR / script_rel_path
    print(f"\n=== Running {script_path} ===")
    result = subprocess.run(
        [PYTHON, str(script_path)],
        cwd=str(BASE_DIR),
        check=False,
    )
    if result.returncode == 0:
        print(f"✔ {script_rel_path} completed.")
    else:
        print(f"✖ {script_rel_path} failed with code {result.returncode}.")
    return result.returncode


def main():
    print("=" * 60)
    print(" Macro Capital Flows – Data Refresh")
    print(" Started:", datetime.utcnow().isoformat() + "Z")
    print("=" * 60)

    failures = 0
    for script in PIPELINE_SCRIPTS:
        rc = run_pipeline(script)
        if rc != 0:
            failures += 1

    if failures:
        print(f"\nCompleted with {failures} failed pipeline(s).")
        sys.exit(1)
    else:
        print("\nAll pipelines finished successfully.")
        print("Done:", datetime.utcnow().isoformat() + "Z")


if __name__ == "__main__":
    main()
