import numpy as np
import pandas as pd

product = pd.read_csv("data/raw/products.csv")

# Переводим price из типа данных object в int
product["price"] = product["price"].str.replace("$", "").astype(float)

# Находим ценники в отрицательным значением и делаем их положительными
mask = product["price"] < 0
product.loc[mask, "price"] = abs(product.loc[mask, "price"])

# Заполняем медианой пустую клетку с cost
product["cost_to_price_ratio"] = product["cost"] / product["price"]
median_ratio_by_cat = product.groupby("category")["cost_to_price_ratio"].transform("median")
product["cost"] = product["cost"].fillna(product["price"] * median_ratio_by_cat)
# сохраняем
product = product.drop(columns=["cost_to_price_ratio"])
product.to_csv("data/processed/products_clean.csv", index=False)
