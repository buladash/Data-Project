import pandas as pd

df = pd.read_csv("data/raw/orders.csv")

# удаляем дупликаты (дупликаты тут точь в точь)
df = df.drop_duplicates(subset=["order_id"], keep="first")

# приводим к нижнему регистру status
df["status"] = df["status"].str.lower()

# бесхозные заказы привязываем к одному customer_id
n_orphan = df["customer_id"].isna().sum()
df["customer_id"] = df["customer_id"].fillna(-1).astype(int)

# переводим дату в формат datetime
df["order_date"] = pd.to_datetime(df["order_date"], format="mixed", errors="coerce")

df.to_csv("data/processed/orders_clean.csv", index=False)

