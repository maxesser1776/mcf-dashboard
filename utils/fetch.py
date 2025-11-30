import pandas as pd
import os

# Utility to load CSV from processed folder
def load_processed_csv(filename, parse_dates=True):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join("data", "processed", filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{filename} not found in processed at {path}.")
    return pd.read_csv(path, parse_dates=parse_dates, index_col=0)

# Optional: wrapper for safe loading with fallback
def try_load_csv(filename):
    try:
        return load_processed_csv(filename)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return pd.DataFrame()