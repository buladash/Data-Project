"""
Cleans the "raw" e-commerce data (data/raw/) and saves analysis-ready
tables to data/processed/.

Every cleaning step is logged to reports/data_cleaning_report.md, to
explain (to yourself, a reviewer, an interviewer) what issues were found
and what decision was made for each one.

Run:
    python python/02_clean_data.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

log_lines = ["# Data Cleaning Report\n"]


def log(section, text):
    log_lines.append(f"\n## {section}\n\n{text}\n")
    print(f"[{section}] {text}")


COUNTRY_MAP = {
    "usa": "USA", "us": "USA", "united states": "USA",
    "canada": "Canada", "ca": "Canada",
    "united kingdom": "United Kingdom", "uk": "United Kingdom", "u.k.": "United Kingdom",
    "germany": "Germany", "de": "Germany",
    "france": "France", "fr": "France",
}


def normalize_country(value):
    key = str(value).strip().lower()
    return COUNTRY_MAP.get(key, str(value).strip())


def parse_mixed_dates(series):
    return pd.to_datetime(series, format="mixed", dayfirst=False, errors="coerce")


# --------------------------------------------------------------------- CUSTOMERS
def clean_customers():
    df = pd.read_csv(RAW_DIR / "customers.csv")
    n_raw = len(df)

    df["email"] = df["email"].astype(str).str.strip().str.lower()
    df["country"] = df["country"].apply(normalize_country)
    df["registration_date"] = parse_mixed_dates(df["registration_date"])

    invalid_email_mask = ~df["email"].str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    n_invalid_email = int(invalid_email_mask.sum())
    df.loc[invalid_email_mask, "email"] = np.nan

    df["phone"] = df["phone"].fillna("Unknown")
    df["city"] = df["city"].fillna("Unknown")

    n_missing_dates = int(df["registration_date"].isna().sum())

    # Duplicates: the same person appears twice in the export with a
    # different email (customer_id and email differ, everything else matches).
    dup_subset = ["first_name", "last_name", "phone", "city", "country", "acquisition_channel"]
    before = len(df)
    df = df.sort_values("customer_id").drop_duplicates(subset=dup_subset, keep="first")
    n_dupes_removed = before - len(df)

    df = df.reset_index(drop=True)

    log(
        "customers.csv",
        f"- Rows in: {n_raw}\n"
        f"- Duplicate customers removed (matching name/phone/city/channel): {n_dupes_removed}\n"
        f"- Invalid emails (no @ / no domain) replaced with NaN: {n_invalid_email}\n"
        f"- Missing registration_date after parsing mixed formats: {n_missing_dates}\n"
        f"- Missing phone/city filled with 'Unknown'\n"
        f"- Countries normalized to a single spelling (USA/Canada/United Kingdom/Germany/France)\n"
        f"- Rows out: {len(df)}",
    )
    return df


# ---------------------------------------------------------------------- PRODUCTS
def clean_products():
    df = pd.read_csv(RAW_DIR / "products.csv")
    n_raw = len(df)

    df["price"] = (
        df["price"].astype(str).str.replace("$", "", regex=False).str.strip().astype(float)
    )

    n_negative_price = int((df["price"] < 0).sum())
    df["price"] = df["price"].abs()

    # Cost: missing values are backfilled via the median cost-to-price
    # ratio per category, not a flat table-wide average — the estimate is
    # more accurate that way.
    df["cost_to_price_ratio"] = df["cost"] / df["price"]
    median_ratio_by_cat = df.groupby("category")["cost_to_price_ratio"].transform("median")
    n_missing_cost = int(df["cost"].isna().sum())
    df["cost"] = df["cost"].fillna(df["price"] * median_ratio_by_cat)
    df = df.drop(columns=["cost_to_price_ratio"])
    df["cost"] = df["cost"].round(2)

    log(
        "products.csv",
        f"- Rows in: {n_raw}\n"
        f"- Price converted to a numeric type (stripped the '$' symbol)\n"
        f"- Negative prices fixed (took the absolute value): {n_negative_price}\n"
        f"- Missing cost backfilled via median margin per category: {n_missing_cost}\n"
        f"- Rows out: {len(df)}",
    )
    return df


# ------------------------------------------------------------------------ ORDERS
def clean_orders(valid_customer_ids):
    df = pd.read_csv(RAW_DIR / "orders.csv")
    n_raw = len(df)

    before = len(df)
    df = df.drop_duplicates(subset=["order_id"], keep="first")
    n_dupes_removed = before - len(df)

    df["order_date"] = parse_mixed_dates(df["order_date"])
    df["status"] = df["status"].str.lower()

    # Orders with no customer_id aren't dropped (that would lose revenue in
    # the analysis) — they're mapped to a surrogate customer -1 ("Unknown"),
    # a standard dimensional-modeling practice.
    n_orphan = int(df["customer_id"].isna().sum())
    df["customer_id"] = df["customer_id"].apply(
        lambda x: -1 if pd.isna(x) or int(x) not in valid_customer_ids else int(x)
    )

    n_missing_dates = int(df["order_date"].isna().sum())
    df = df.dropna(subset=["order_date"]).reset_index(drop=True)

    log(
        "orders.csv",
        f"- Rows in: {n_raw}\n"
        f"- Exact order_id duplicates removed: {n_dupes_removed}\n"
        f"- Order status normalized to lowercase (completed/cancelled/returned)\n"
        f"- Orders with no customer_id, mapped to surrogate customer -1 (Unknown): {n_orphan}\n"
        f"- Orders with an invalid/missing date removed: {n_missing_dates}\n"
        f"- Rows out: {len(df)}",
    )
    return df


# ------------------------------------------------------------------- ORDER_ITEMS
def clean_order_items(valid_order_ids, valid_product_ids):
    df = pd.read_csv(RAW_DIR / "order_items.csv")
    n_raw = len(df)

    n_negative_qty = int((df["quantity"] < 0).sum())
    df["quantity"] = df["quantity"].abs()

    before = len(df)
    df = df[df["order_id"].isin(valid_order_ids) & df["product_id"].isin(valid_product_ids)]
    n_orphan_removed = before - len(df)

    df["line_revenue"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(2)

    df = df.reset_index(drop=True)

    log(
        "order_items.csv",
        f"- Rows in: {n_raw}\n"
        f"- Negative quantities (data entry error) fixed via absolute value: {n_negative_qty}\n"
        f"- Line items referencing removed order_id/product_id, dropped: {n_orphan_removed}\n"
        f"- Added computed column line_revenue = qty * unit_price * (1 - discount)\n"
        f"- Rows out: {len(df)}",
    )
    return df


# --------------------------------------------------------------- MARKETING SPEND
def clean_marketing_spend():
    df = pd.read_csv(RAW_DIR / "marketing_spend.csv")
    df["date"] = pd.to_datetime(df["date"])
    n_negative = int((df["spend"] < 0).sum())
    df["spend"] = df["spend"].clip(lower=0)
    log(
        "marketing_spend.csv",
        f"- Rows: {len(df)}\n"
        f"- Negative spend values clipped to 0: {n_negative}",
    )
    return df


def main():
    customers = clean_customers()

    # Add a surrogate "Unknown" customer for orders with no customer link
    unknown_customer = pd.DataFrame([{
        "customer_id": -1, "first_name": "Unknown", "last_name": "Unknown",
        "email": np.nan, "phone": "Unknown", "city": "Unknown", "country": "Unknown",
        "registration_date": pd.NaT, "acquisition_channel": "unknown",
    }])
    customers = pd.concat([customers, unknown_customer], ignore_index=True)

    products = clean_products()
    orders = clean_orders(set(customers["customer_id"]))
    order_items = clean_order_items(set(orders["order_id"]), set(products["product_id"]))
    marketing = clean_marketing_spend()

    customers.to_csv(PROCESSED_DIR / "customers_clean.csv", index=False)
    products.to_csv(PROCESSED_DIR / "products_clean.csv", index=False)
    orders.to_csv(PROCESSED_DIR / "orders_clean.csv", index=False)
    order_items.to_csv(PROCESSED_DIR / "order_items_clean.csv", index=False)
    marketing.to_csv(PROCESSED_DIR / "marketing_spend_clean.csv", index=False)

    with open(REPORTS_DIR / "data_cleaning_report.md", "w") as f:
        f.write("".join(log_lines))

    print(f"\nCleaned tables saved to {PROCESSED_DIR}")
    print(f"Cleaning report: {REPORTS_DIR / 'data_cleaning_report.md'}")


if __name__ == "__main__":
    main()
