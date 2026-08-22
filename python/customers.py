import pandas as pd
import os

df = pd.read_csv("data/raw/customers.csv")

# Убираем дупликаты
df = df.sort_values("customer_id").drop_duplicates(
    subset=["first_name", "last_name", "city", "country", "phone", "reg_date", "acquisition_channel"],
    keep = "first"
)

# Убираем невалидные email
invalid_mask = ~df["email"].str.contains("@", na=False)
df.loc[invalid_mask, "email"] = pd.NA

# Убираем пропуски телефонов
df["phone"] = df["phone"].fillna("Unknown")

# Переводим дату с типа данных object на datetime
df["reg_date"] = pd.to_datetime(df["reg_date"], format="mixed", errors="coerce")

# Сохраняем очищенные данные в папку
os.makedirs("data/processed", exist_ok=True)
df.to_csv("data/processed/customers_clean.csv", index=False)


