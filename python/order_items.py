import pandas as pd

df = pd.read_csv("data/raw/order_items.csv")

# Проверяем сколько отрицательных значений в количестве и делаем это кол-во положительным
mask = (df["quantity"] < 0).sum()
print(mask)
df["quantity"] = df["quantity"].abs()

# Расчет скидки
df["price_revenue"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(2)
print(df[["quantity", "unit_price", "discount", "price_revenue"]])

df.to_csv("data/processed/order_items_clean.csv", index=False)
