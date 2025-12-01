# debug_growth_leading.py

import pandas as pd
from pathlib import Path

path = Path("data/processed/growth_leading.csv")

print(f"📄 Loading: {path}")

df = pd.read_csv(path)
print("\n=== HEAD (first 10 rows) ===")
print(df.head(10))

print("\n=== TAIL (last 10 rows) ===")
print(df.tail(10))

print("\n=== COLUMNS ===")
print(df.columns.tolist())

print("\n=== Null Count per Column ===")
print(df.isna().sum())

# Try to parse first column as date
date_col = None
for c in ["Date", "date", "Unnamed: 0"]:
    if c in df.columns:
        date_col = c
        break

if date_col is None:
    date_col = df.columns[0]

print(f"\nUsing '{date_col}' as date column")

try:
    parsed = pd.to_datetime(df[date_col])
    print("\n=== Date Parsing Sample ===")
    print(parsed.head())
    print(parsed.tail())
except Exception as e:
    print(f"\n⚠ Date parsing failed: {e}")

if "ISM_Spread" in df.columns:
    print("\n=== ISM_Spread summary ===")
    print(df["ISM_Spread"].describe())
    print("\nFirst 20 non-null ISM_Spread values:")
    print(df["ISM_Spread"].dropna().head(20))
else:
    print("\n⚠ Column 'ISM_Spread' not found in growth_leading.csv")
