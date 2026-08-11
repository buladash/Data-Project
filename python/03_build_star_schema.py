"""
Строит звёздную схему (star schema) из очищенных таблиц (data/processed/)
и сохраняет результат в двух видах:

1. SQLite база data/ecommerce.db — для SQL-части проекта.
2. Плоские CSV в data/powerbi/ — для прямого импорта в Power BI.

Схема:
    dim_customers   (customer_id PK)
    dim_products    (product_id PK)
    dim_channel     (channel_id PK)
    dim_date        (date_key PK, формат YYYYMMDD)
    fact_orders     (order_item_id PK; FK: order_id, customer_id, product_id, date_key, channel_id)
    fact_marketing_spend (FK: date_key, channel_id) — отдельный факт с грануляцией день/канал

Запуск:
    python python/03_build_star_schema.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
POWERBI_DIR = ROOT / "data" / "powerbi"
DB_PATH = ROOT / "data" / "ecommerce.db"
POWERBI_DIR.mkdir(parents=True, exist_ok=True)


def build_dim_date(min_date, max_date):
    dates = pd.date_range(min_date, max_date, freq="D")
    df = pd.DataFrame({"date": dates})
    df["date_key"] = df["date"].dt.strftime("%Y%m%d").astype(int)
    df["year"] = df["date"].dt.year
    df["quarter"] = df["date"].dt.quarter
    df["month"] = df["date"].dt.month
    df["month_name"] = df["date"].dt.strftime("%B")
    df["day"] = df["date"].dt.day
    df["day_of_week"] = df["date"].dt.dayofweek + 1  # 1=Monday
    df["day_name"] = df["date"].dt.strftime("%A")
    df["is_weekend"] = df["day_of_week"].isin([6, 7])
    df["year_month"] = df["date"].dt.strftime("%Y-%m")
    return df[
        ["date_key", "date", "year", "quarter", "month", "month_name",
         "day", "day_of_week", "day_name", "is_weekend", "year_month"]
    ]


def main():
    customers = pd.read_csv(PROCESSED_DIR / "customers_clean.csv", parse_dates=["registration_date"])
    products = pd.read_csv(PROCESSED_DIR / "products_clean.csv")
    orders = pd.read_csv(PROCESSED_DIR / "orders_clean.csv", parse_dates=["order_date"])
    order_items = pd.read_csv(PROCESSED_DIR / "order_items_clean.csv")
    marketing = pd.read_csv(PROCESSED_DIR / "marketing_spend_clean.csv", parse_dates=["date"])

    # --------------------------------------------------------------- dim_channel
    channel_names = sorted(set(orders["channel"]) | set(marketing["channel"]) | set(customers["acquisition_channel"]))
    dim_channel = pd.DataFrame({
        "channel_id": range(1, len(channel_names) + 1),
        "channel_name": channel_names,
    })
    channel_to_id = dict(zip(dim_channel["channel_name"], dim_channel["channel_id"]))

    # ------------------------------------------------------------------ dim_date
    min_date = min(orders["order_date"].min(), marketing["date"].min(), customers["registration_date"].min())
    max_date = max(orders["order_date"].max(), marketing["date"].max())
    dim_date = build_dim_date(min_date.normalize(), max_date.normalize())

    # -------------------------------------------------------------- dim_customers
    dim_customers = customers.rename(columns={"registration_date": "registration_date"}).copy()
    dim_customers["full_name"] = dim_customers["first_name"] + " " + dim_customers["last_name"]
    dim_customers["acquisition_channel_id"] = dim_customers["acquisition_channel"].map(channel_to_id)

    # --------------------------------------------------------------- dim_products
    dim_products = products.copy()
    dim_products["margin"] = (dim_products["price"] - dim_products["cost"]).round(2)
    dim_products["margin_pct"] = (dim_products["margin"] / dim_products["price"] * 100).round(1)

    # ---------------------------------------------------------------- fact_orders
    fact = order_items.merge(
        orders[["order_id", "customer_id", "order_date", "status", "channel", "payment_method"]],
        on="order_id", how="inner",
    )
    fact["date_key"] = fact["order_date"].dt.strftime("%Y%m%d").astype(int)
    fact["channel_id"] = fact["channel"].map(channel_to_id)
    fact = fact.rename(columns={"status": "order_status"})
    fact_orders = fact[[
        "order_item_id", "order_id", "customer_id", "product_id", "date_key", "channel_id",
        "quantity", "unit_price", "discount", "line_revenue", "order_status", "payment_method",
    ]]

    # ------------------------------------------------------- fact_marketing_spend
    fact_marketing = marketing.copy()
    fact_marketing["date_key"] = fact_marketing["date"].dt.strftime("%Y%m%d").astype(int)
    fact_marketing["channel_id"] = fact_marketing["channel"].map(channel_to_id)
    fact_marketing_spend = fact_marketing[["date_key", "channel_id", "spend"]]

    # ---------------------------------------------------------------- save SQLite
    tables = {
        "dim_customers": dim_customers,
        "dim_products": dim_products,
        "dim_channel": dim_channel,
        "dim_date": dim_date,
        "fact_orders": fact_orders,
        "fact_marketing_spend": fact_marketing_spend,
    }

    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    for name, df in tables.items():
        df.to_sql(name, conn, index=False)
        df.to_csv(POWERBI_DIR / f"{name}.csv", index=False)
        print(f"  {name:<22} {len(df):>7} строк -> SQLite + data/powerbi/{name}.csv")

    # Индексы для ускорения джойнов/фильтров в SQL-части
    cur = conn.cursor()
    cur.execute("CREATE INDEX idx_fact_orders_customer ON fact_orders(customer_id)")
    cur.execute("CREATE INDEX idx_fact_orders_product ON fact_orders(product_id)")
    cur.execute("CREATE INDEX idx_fact_orders_date ON fact_orders(date_key)")
    cur.execute("CREATE INDEX idx_fact_marketing_date ON fact_marketing_spend(date_key)")
    conn.commit()
    conn.close()

    print(f"\nБаза данных: {DB_PATH}")
    print(f"CSV для Power BI: {POWERBI_DIR}")


if __name__ == "__main__":
    main()
