"""
Generates synthetic "raw" data for an electronics e-commerce store.

The dataset mimics an export from a production database: it intentionally
contains typical data quality issues (duplicates, missing values,
inconsistent casing/formats, incorrect types, outliers) so there's a real
pipeline to clean afterwards in pandas (see 02_clean_data.py).

Run:
    python python/01_generate_data.py
"""

import numpy as np
import pandas as pd
from faker import Faker
from pathlib import Path
from datetime import datetime, timedelta
import random

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_US")
Faker.seed(SEED)

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)

N_CUSTOMERS = 9000
N_PRODUCTS = 160
N_ORDERS = 16000

CHANNELS = ["organic_search", "paid_search", "social_media", "email", "referral", "direct"]
COUNTRIES_CLEAN = ["USA", "Canada", "United Kingdom", "Germany", "France"]
COUNTRIES_DIRTY = {  # different ways the same country is spelled in the raw data
    "USA": ["USA", "United States", "US", "usa", " USA "],
    "Canada": ["Canada", "CA", "canada"],
    "United Kingdom": ["United Kingdom", "UK", "U.K.", "uk"],
    "Germany": ["Germany", "DE", "germany"],
    "France": ["France", "FR", "france"],
}

CATEGORIES = {
    "Electronics": ["Smartphones", "Laptops", "Headphones", "Tablets", "Cameras"],
    "Home Appliances": ["Vacuum Cleaners", "Kitchen", "Air Conditioners"],
    "Accessories": ["Chargers", "Cases", "Cables"],
    "Gaming": ["Consoles", "Controllers", "Games"],
}

PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "bank_transfer"]
ORDER_STATUSES = ["completed", "cancelled", "returned"]
ORDER_STATUS_WEIGHTS = [0.86, 0.09, 0.05]


def random_date(start, end):
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days), seconds=random.randint(0, 86399))


def build_seasonal_day_weights(start, end):
    """Per-day sampling weights for order dates: a growing business plus
    seasonality (a sales peak in November-December, a dip in
    January-February, slightly more sales on weekends)."""
    days = pd.date_range(start, end, freq="D")
    n = len(days)

    growth = np.linspace(0.7, 1.4, n)  # the business grows over 2 years

    month_factor = {1: 0.82, 2: 0.85, 3: 0.95, 4: 1.0, 5: 1.0, 6: 0.95,
                    7: 0.92, 8: 0.95, 9: 1.0, 10: 1.05, 11: 1.45, 12: 1.6}
    seasonal = np.array([month_factor[d.month] for d in days])

    dow_factor = np.array([1.12 if d.dayofweek in (5, 6) else 1.0 for d in days])

    weights = growth * seasonal * dow_factor
    weights = weights / weights.sum()
    return days, weights


def sample_order_dates(n, start, end):
    days, weights = build_seasonal_day_weights(start, end)
    sampled_days = np.random.choice(days, size=n, p=weights)
    seconds = np.random.randint(0, 86400, size=n)
    return [pd.Timestamp(d) + timedelta(seconds=int(s)) for d, s in zip(sampled_days, seconds)]


def messy_date_format(dt):
    """Returns the date in one of several formats, as if the data had been
    pulled from different systems."""
    fmt = random.choice(["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y"])
    return dt.strftime(fmt)


# ------------------------------------------------------------------ CUSTOMERS
def generate_customers(n):
    rows = []
    for i in range(1, n + 1):
        country_clean = random.choice(COUNTRIES_CLEAN)
        country = random.choice(COUNTRIES_DIRTY[country_clean])
        first = fake.first_name()
        last = fake.last_name()

        email = f"{first}.{last}{random.randint(1,999)}@{fake.free_email_domain()}"
        if random.random() < 0.03:
            email = email.upper()
        if random.random() < 0.02:
            email = " " + email + " "
        if random.random() < 0.015:
            email = f"{first}.{last}"  # invalid email, no domain

        phone = fake.phone_number() if random.random() > 0.12 else None  # 12% missing
        city = fake.city() if random.random() > 0.05 else None

        reg_date = random_date(START_DATE - timedelta(days=365), END_DATE)

        rows.append(
            {
                "customer_id": i,
                "first_name": first,
                "last_name": last,
                "email": email,
                "phone": phone,
                "city": city,
                "country": country,
                "registration_date": messy_date_format(reg_date),
                "acquisition_channel": random.choice(CHANNELS),
            }
        )

    df = pd.DataFrame(rows)

    # Intentional customer duplicates (same person, slightly different email/whitespace) — 2.5%
    dup_n = int(n * 0.025)
    dup_rows = df.sample(dup_n, random_state=SEED).copy()
    dup_rows["customer_id"] = range(n + 1, n + 1 + dup_n)
    dup_rows["email"] = dup_rows["email"].astype(str).str.strip().str.lower() + ".1"
    df = pd.concat([df, dup_rows], ignore_index=True)

    return df


# ------------------------------------------------------------------- PRODUCTS
def generate_products(n):
    rows = []
    pid = 1
    for _ in range(n):
        category = random.choice(list(CATEGORIES.keys()))
        subcategory = random.choice(CATEGORIES[category])
        base_price = round(np.random.lognormal(mean=4.2, sigma=0.9), 2)
        base_price = max(5.0, min(base_price, 3500.0))
        cost = round(base_price * random.uniform(0.45, 0.75), 2)

        price_field = base_price
        if random.random() < 0.03:
            price_field = f"${base_price}"  # price as a string with a currency symbol
        if random.random() < 0.01:
            price_field = -abs(base_price)  # negative price (export error)

        rows.append(
            {
                "product_id": pid,
                "product_name": f"{subcategory[:-1] if subcategory.endswith('s') else subcategory} {fake.word().capitalize()} {random.choice(['Pro','Lite','Max','Plus',''])}".strip(),
                "category": category,
                "subcategory": subcategory,
                "price": price_field,
                "cost": cost if random.random() > 0.04 else None,  # 4% missing cost
            }
        )
        pid += 1
    return pd.DataFrame(rows)


# --------------------------------------------------------------------- ORDERS
def build_customer_order_weights(customer_ids):
    """Pareto-like distribution: most customers buy 1-2 times, a small
    share are repeat buyers with many orders (typical for real e-commerce,
    ~20% of customers drive most of the revenue)."""
    raw = np.random.pareto(a=2.2, size=len(customer_ids)) + 1
    return raw / raw.sum()


def generate_orders(n, customer_ids):
    order_dates = sample_order_dates(n, START_DATE, END_DATE)
    weights = build_customer_order_weights(customer_ids)
    sampled_customers = np.random.choice(customer_ids, size=n, p=weights)

    rows = []
    for i in range(1, n + 1):
        cust_id = int(sampled_customers[i - 1])
        if random.random() < 0.008:
            cust_id = None  # "orphan" order with no customer

        order_date = order_dates[i - 1]
        status = random.choices(ORDER_STATUSES, weights=ORDER_STATUS_WEIGHTS, k=1)[0]
        if random.random() < 0.05:
            status = status.upper()  # inconsistent casing

        rows.append(
            {
                "order_id": i,
                "customer_id": cust_id,
                "order_date": messy_date_format(order_date),
                "status": status,
                "channel": random.choice(CHANNELS),
                "payment_method": random.choice(PAYMENT_METHODS),
            }
        )

    df = pd.DataFrame(rows)

    # Duplicate orders (the same row exported twice) — 1%
    dup_rows = df.sample(int(n * 0.01), random_state=SEED)
    df = pd.concat([df, dup_rows], ignore_index=True)

    return df


# ---------------------------------------------------------------- ORDER_ITEMS
def generate_order_items(orders_df, products_df):
    rows = []
    item_id = 1
    product_ids = products_df["product_id"].tolist()
    product_price = dict(zip(products_df["product_id"], products_df["price"]))

    for order_id in orders_df["order_id"]:
        n_items = np.random.choice([1, 2, 3, 4], p=[0.55, 0.27, 0.13, 0.05])
        chosen_products = random.sample(product_ids, k=min(n_items, len(product_ids)))
        for pid in chosen_products:
            qty = int(np.random.choice([1, 2, 3, 4, 5], p=[0.55, 0.25, 0.1, 0.07, 0.03]))
            if random.random() < 0.005:
                qty = -qty  # data entry error (returns are tracked separately via order status)

            raw_price = product_price.get(pid, 10.0)
            try:
                base_price = float(str(raw_price).replace("$", ""))
            except ValueError:
                base_price = 10.0
            unit_price = round(abs(base_price) * random.uniform(0.95, 1.0), 2)

            discount = round(random.choice([0, 0, 0, 0.05, 0.1, 0.15]), 2)

            rows.append(
                {
                    "order_item_id": item_id,
                    "order_id": order_id,
                    "product_id": pid,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "discount": discount,
                }
            )
            item_id += 1

    return pd.DataFrame(rows)


# ------------------------------------------------------------- MARKETING SPEND
def generate_marketing_spend(start, end):
    rows = []
    dates = pd.date_range(start, end, freq="D")
    base_spend = {
        "paid_search": 220,
        "social_media": 180,
        "email": 25,
        "referral": 15,
        "organic_search": 0,
        "direct": 0,
    }
    for d in dates:
        for channel, base in base_spend.items():
            if base == 0:
                continue
            noise = np.random.normal(1.0, 0.25)
            spend = max(0, round(base * noise, 2))
            rows.append({"date": d.strftime("%Y-%m-%d"), "channel": channel, "spend": spend})
    return pd.DataFrame(rows)


def main():
    print("Generating customers...")
    customers = generate_customers(N_CUSTOMERS)
    customers.to_csv(RAW_DIR / "customers.csv", index=False)

    print("Generating products...")
    products = generate_products(N_PRODUCTS)
    products.to_csv(RAW_DIR / "products.csv", index=False)

    print("Generating orders...")
    orders = generate_orders(N_ORDERS, customers["customer_id"].tolist())
    orders.to_csv(RAW_DIR / "orders.csv", index=False)

    print("Generating order items...")
    order_items = generate_order_items(orders, products)
    order_items.to_csv(RAW_DIR / "order_items.csv", index=False)

    print("Generating marketing spend...")
    marketing = generate_marketing_spend(START_DATE, END_DATE)
    marketing.to_csv(RAW_DIR / "marketing_spend.csv", index=False)

    print("\nDone. Files saved to data/raw/:")
    for f in sorted(RAW_DIR.glob("*.csv")):
        n_rows = sum(1 for _ in open(f)) - 1
        print(f"  {f.name:<25} {n_rows:>7} rows")


if __name__ == "__main__":
    main()
