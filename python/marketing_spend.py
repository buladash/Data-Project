import pandas as pd

df = pd.read_csv("data/raw/marketing_spend.csv")

# смена типа даты
df["date"] = pd.to_datetime(df["date"])

# проверка негатива
n_negative = (df["spend"] < 0).sum()
print(n_negative)

df["spend"] = df["spend"].clip(lower=0)

df.to_csv("data/processed/marketing_spend_clean.csv", index=False)
