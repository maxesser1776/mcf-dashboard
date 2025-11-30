import pandas as pd

# Load the debug CSV you uploaded
df = pd.read_csv("tga_raw_debug.csv")

print("\n====================================")
print("📌 COLUMNS")
print("====================================")
print(df.columns.tolist())

print("\n====================================")
print("📌 FIRST 10 ROWS (Where Missing Data Usually Appears)")
print("====================================")
print(df.head(10))

print("\n====================================")
print("📌 LAST 10 ROWS (Oldest Entries, Usually Fully Populated)")
print("====================================")
print(df.tail(10))

print("\n====================================")
print("📌 DATA TYPES")
print("====================================")
print(df.dtypes)

print("\n====================================")
print("📌 SUMMARY: COUNT OF NULLS PER COLUMN")
print("====================================")
print(df.isna().sum())

print("\n====================================")
print("📌 UNIQUE account_type VALUES")
print("====================================")
print(df['account_type'].unique())

print("\n====================================")
print("📌 FULL ROWS FOR FIRST 3 ENTRIES")
print("====================================")
print(df.iloc[0])
print(df.iloc[1])
print(df.iloc[2])

# (Optional) Save a 20-row clip for manual review
df.head(10).to_csv("tga_first10_preview.csv", index=False)
df.tail(10).to_csv("tga_last10_preview.csv", index=False)
print("\n💾 Saved 'tga_first10_preview.csv' and 'tga_last10_preview.csv'")
