import pandas as pd

df = pd.read_parquet("data/stocks/AAPL.parquet")

print(df.head())
print(df.columns)
print(df.shape)