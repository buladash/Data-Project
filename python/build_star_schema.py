import pandas as pd
import sqlite3

from jupyter_lsp.specs import sql_language_server


def build_dim_date():
    orders = pd.read_csv("data/processed/orders_clean.csv", parse_dates=["order_date"])
    marketing = pd.read_csv("data/processed/marketing_spend_clean.csv", parse_dates=["date"])

    min_date = min(orders["order_date"].min(), marketing["date"].min())
    max_date = max(orders["order_date"].max(), marketing["date"].max())

    dates = pd.date_range(min_date, max_date, freq="D")
    dim_date = pd.DataFrame({"date": dates})

    dim_date ["year"] = dim_date["date"].dt.year
    dim_date ["month"] = dim_date["date"].dt.month
    dim_date ["day_of_week"] = dim_date["date"].dt.dayofweek + 1
    dim_date ["quarter"] = dim_date["date"].dt.quarter
    dim_date ["month_name"] = dim_date["date"].dt.strftime("%B")
    dim_date["date_key"] = dim_date["date"].dt.strftime("%Y%m%d").astype(int)

    return dim_date

dim_date = build_dim_date()
# print(dim_date)

def build_dim_channel():
    customers = pd.read_csv("data/processed/customers_clean.csv")

    channels = customers["acquisition_channel"].unique()
    dim_channel = pd.DataFrame({
        "channel_id": range(1, len(channels) + 1),
        "channel_name": channels
    })
    return dim_channel
dim_channel = build_dim_channel()
# print(dim_channel)

def build_fact_orders():
    orders = pd.read_csv("data/processed/orders_clean.csv", parse_dates = ["order_date"])
    items = pd.read_csv("data/processed/order_items_clean.csv")

    fact_orders = items.merge(orders, on="order_id", how="inner")
    fact_orders["date_key"] = fact_orders["order_date"].dt.strftime("%Y%m%d").astype(int)

    return fact_orders
fact_orders = build_fact_orders()

# print(orders_merge)

def build_dim_customers():
    return pd.read_csv("data/processed/customers_clean.csv")

def build_dim_products():
    return pd.read_csv("data/processed/products_clean.csv")

def build_dim_marketing():
    df = pd.read_csv("data/processed/marketing_spend_clean.csv", parse_dates=["date"])
    df["date_key"] = df["date"].dt.strftime("%Y%m%d").astype(int)
    return df

dim_date = build_dim_date()
dim_channel = build_dim_channel()
fact_orders = build_fact_orders()
dim_customers = build_dim_customers()
dim_products = build_dim_products()
dim_marketing = build_dim_marketing()

# добавляем "Unknown"-клиента в справочник, если такого ещё нет
unknown_customer = pd.DataFrame({"customer_id": [-1]})
dim_customers = pd.concat([dim_customers, unknown_customer], ignore_index=True)

# все customer_id в fact_orders, которых нет в dim_customers, -> -1
valid_ids = set(dim_customers["customer_id"])
fact_orders.loc[~fact_orders["customer_id"].isin(valid_ids), "customer_id"] = -1
# --- проверки после того, как все таблицы собраны ---
missing_dates = set(fact_orders["date_key"]) - set(dim_date["date_key"])
print("date_key без соответствия в dim_date:", missing_dates)

missing_customers = set(fact_orders["customer_id"]) - set(dim_customers["customer_id"])
print("customer_id без соответствия в dim_customers:", missing_customers)

# Сохранение всего в SQLite
conn = sqlite3.connect("data/ecommerce.db")
dim_date.to_sql("dim_date", conn, index=False, if_exists="replace")
dim_channel.to_sql("dim_channel", conn, index=False, if_exists="replace")
dim_customers.to_sql("dim_customers", conn, index=False, if_exists="replace")
dim_products.to_sql("dim_products", conn, index=False, if_exists="replace")
fact_orders.to_sql("fact_orders", conn, index=False, if_exists="replace")
dim_marketing.to_sql("fact_marketing_spend", conn, index=False, if_exists="replace")

conn.close()
