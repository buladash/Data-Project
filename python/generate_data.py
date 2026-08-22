import pandas as pd
import numpy as np
from faker import Faker
import random
from datetime import datetime, timedelta
import os

os.makedirs("data/raw", exist_ok=True)

random.seed(42)
np.random.seed(42)
fake = Faker("en_US")
Faker.seed(42)


def generate_customers(n):
    def random_date(start, end):
        delta = end - start
        return start + timedelta(days=random.randint(0, delta.days))

    Channels = ["organic_search", "paid_search", "social_media", "email", "referral", "direct"]

    rows = []

    for i in range(1, n + 1):
        first_name = fake.first_name()
        last_name = fake.last_name()
        email = f"{first_name}.{last_name}{random.randint(1, 999)}@{fake.free_email_domain()}"
        phone = fake.phone_number() if random.random() > 0.12 else None
        if random.random() < 0.015:
            email = f"{first_name}. {last_name}"

        reg_date = random_date(datetime(2023, 1, 1), datetime(2025, 12, 31))
        fmt = random.choice(["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"])
        registration_date = reg_date.strftime(fmt)

        acquisition_channel = random.choice(Channels)

        rows.append({
            "customer_id": i,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "city": fake.city(),
            "country": fake.country(),
            "phone": phone,
            "reg_date": registration_date,
            "acquisition_channel": acquisition_channel
        })

    df = pd.DataFrame(rows)

    dup_n = 5
    dup_rows = df.sample(dup_n, random_state=42).copy()
    dup_rows["customer_id"] = range(101, 101 + dup_n)
    dup_rows["email"] = dup_rows["email"].str.lower() + ".1"
    df = pd.concat([df, dup_rows], ignore_index=True)

    return df


customers_df = generate_customers(100)
customers_df.to_csv("data/raw/customers.csv", index=False)


def generate_products(n):
    rows = []
    CATEGORIES = {
        "Electronics": ["Smartphones", "Laptops", "Headphones", "Tablets"],
        "Gaming": ["Consoles", "Controllers", "Games"],
        "Accessories": ["Chargers", "Cases", "Cables"],
    }
    for i in range(1, n + 1):
        category = random.choice(list(CATEGORIES.keys()))
        subcategory = random.choice(CATEGORIES[category])
        product_name = f"{subcategory} {fake.word().capitalize()} {random.choice(['Pro', 'Lite', 'Max', 'Plus', ''])}".strip()

        base_price = np.random.lognormal(mean=4.2, sigma=0.9)
        base_price = round(base_price, 2)
        base_price = max(5.0, min(base_price, 3500.0))

        price = base_price
        if random.random() < 0.03:
            price = f"${base_price}"
        if random.random() < 0.01:
            price = -abs(base_price)

        cost = round(base_price * random.uniform(0.45, 0.75), 2)
        cost = cost if random.random() > 0.04 else None

        rows.append({
            "product_id": i,
            "product_name": product_name,
            "category": category,
            "subcategory": subcategory,
            "price": price,
            "cost": cost,
        })

    return pd.DataFrame(rows)


products_df = generate_products(30)
products_df.to_csv("data/raw/products.csv", index=False)


def generate_orders(n, customer_ids):
    rows = []
    for i in range(1, n + 1):
        cust_id = random.choice(customer_ids)
        if random.random() < 0.008:
            cust_id = None

        order_date = fake.date_between(start_date="-2y", end_date="today")
        fmt = random.choice(["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"])
        order_date = order_date.strftime(fmt)

        status = random.choices(
            ["completed", "cancelled", "returned"], weights=[0.86, 0.09, 0.05], k=1
        )[0]
        if random.random() < 0.05:
            status = status.upper()

        rows.append({
            "order_id": i,
            "customer_id": cust_id,
            "order_date": order_date,
            "status": status,
            "payment_method": random.choice(["credit_card", "debit_card", "paypal", "bank_transfer"]),
        })

    df = pd.DataFrame(rows)
    dup_rows = df.sample(int(n * 0.01), random_state=42)
    df = pd.concat([df, dup_rows], ignore_index=True)
    return df


def generate_order_items(orders_df, products_df):
    rows = []
    item_id = 1
    product_ids = products_df["product_id"].tolist()
    product_price = dict(zip(products_df["product_id"], products_df["price"]))

    for order_id in orders_df["order_id"]:
        n_items = random.choice([1, 1, 2, 2, 3])
        chosen = random.sample(product_ids, k=min(n_items, len(product_ids)))
        for pid in chosen:
            qty = random.choice([1, 1, 2, 2, 3, 4])
            if random.random() < 0.005:
                qty = -qty

            raw_price = product_price.get(pid, 10.0)
            try:
                base_price = float(str(raw_price).replace("$", ""))
            except ValueError:
                base_price = 10.0
            unit_price = round(abs(base_price) * random.uniform(0.95, 1.0), 2)
            discount = random.choice([0, 0, 0, 0.05, 0.1, 0.15])

            rows.append({
                "order_item_id": item_id,
                "order_id": order_id,
                "product_id": pid,
                "quantity": qty,
                "unit_price": unit_price,
                "discount": discount,
            })
            item_id += 1

    return pd.DataFrame(rows)


def generate_marketing_spend(n_days=730):
    rows = []
    base_spend = {"paid_search": 220, "social_media": 180, "email": 25, "referral": 15}
    for d in range(n_days):
        date = (datetime(2024, 1, 1) + timedelta(days=d)).strftime("%Y-%m-%d")
        for channel, base in base_spend.items():
            spend = max(0, round(base * random.uniform(0.7, 1.3), 2))
            rows.append({"date": date, "channel": channel, "spend": spend})
    return pd.DataFrame(rows)


orders_df = generate_orders(500, customers_df["customer_id"].tolist())
orders_df.to_csv("data/raw/orders.csv", index=False)

order_items_df = generate_order_items(orders_df, products_df)
order_items_df.to_csv("data/raw/order_items.csv", index=False)

marketing_df = generate_marketing_spend()
marketing_df.to_csv("data/raw/marketing_spend.csv", index=False)

print("Ready:")
for name in ["customers", "products", "orders", "order_items", "marketing_spend"]:
    n_rows = len(pd.read_csv(f"data/raw/{name}.csv"))
    print(f"  {name}.csv — {n_rows} lines")
