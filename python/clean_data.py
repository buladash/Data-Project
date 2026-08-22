import os
import pandas as pd

os.makedirs("data/processed", exist_ok=True)


def clean_customers():
    df = pd.read_csv("data/raw/customers.csv")

    df = df.sort_values("customer_id").drop_duplicates(
        subset=["first_name", "last_name", "city", "country", "phone", "reg_date", "acquisition_channel"],
        keep="first",
    )

    invalid_mask = ~df["email"].str.contains("@", na=False)
    print(f"customers: невалидных email — {invalid_mask.sum()}")
    df.loc[invalid_mask, "email"] = pd.NA

    df["phone"] = df["phone"].fillna("Unknown")

    df["reg_date"] = pd.to_datetime(df["reg_date"], format="mixed", errors="coerce")

    return df


def clean_products():
    df = pd.read_csv("data/raw/products.csv")

    df["price"] = df["price"].str.replace("$", "").astype(float)

    mask = df["price"] < 0
    print(f"products: отрицательных цен — {mask.sum()}")
    df.loc[mask, "price"] = abs(df.loc[mask, "price"])

    df["cost_to_price_ratio"] = df["cost"] / df["price"]
    median_ratio_by_cat = df.groupby("category")["cost_to_price_ratio"].transform("median")
    print(f"products: пропусков в cost — {df['cost'].isna().sum()}")
    df["cost"] = df["cost"].fillna(df["price"] * median_ratio_by_cat)
    df = df.drop(columns=["cost_to_price_ratio"])

    return df


def clean_orders():
    df = pd.read_csv("data/raw/orders.csv")

    before = len(df)
    df = df.drop_duplicates(subset=["order_id"], keep="first")
    print(f"orders: удалено дублей — {before - len(df)}")

    df["status"] = df["status"].str.lower()

    n_orphan = df["customer_id"].isna().sum()
    print(f"orders: заказов без customer_id — {n_orphan}")
    df["customer_id"] = df["customer_id"].fillna(-1).astype(int)

    df["order_date"] = pd.to_datetime(df["order_date"], format="mixed", errors="coerce")

    return df


def clean_order_items():
    df = pd.read_csv("data/raw/order_items.csv")

    n_negative_qty = (df["quantity"] < 0).sum()
    print(f"order_items: отрицательных quantity — {n_negative_qty}")
    df["quantity"] = df["quantity"].abs()

    df["line_revenue"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(2)

    return df


def clean_marketing_spend():
    df = pd.read_csv("data/raw/marketing_spend.csv")
    df["date"] = pd.to_datetime(df["date"])

    n_negative = (df["spend"] < 0).sum()
    print(f"marketing_spend: отрицательных расходов — {n_negative}")
    df["spend"] = df["spend"].clip(lower=0)

    return df


tables = {
    "customers_clean": clean_customers,
    "products_clean": clean_products,
    "orders_clean": clean_orders,
    "order_items_clean": clean_order_items,
    "marketing_spend_clean": clean_marketing_spend,
}

for name, clean_func in tables.items():
    df = clean_func()
    df.to_csv(f"data/processed/{name}.csv", index=False)
    print(f"Сохранено: {name}.csv ({len(df)} строк)\n")

print("Готово. Все таблицы очищены и сохранены в data/processed/")
