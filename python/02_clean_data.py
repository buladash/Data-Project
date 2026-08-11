"""
Очистка "сырых" данных интернет-магазина (data/raw/) и сохранение
готовых к анализу таблиц в data/processed/.

Каждый шаг очистки логируется в отчёт reports/data_cleaning_report.md,
чтобы объяснить (себе, ревьюеру, интервьюеру), какие проблемы были
найдены и какое решение принято по каждой из них.

Запуск:
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

log_lines = ["# Отчёт об очистке данных\n"]


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

    # Дубликаты: один и тот же человек попал в выгрузку дважды с другим email
    # (customer_id и email отличаются, остальные поля совпадают).
    dup_subset = ["first_name", "last_name", "phone", "city", "country", "acquisition_channel"]
    before = len(df)
    df = df.sort_values("customer_id").drop_duplicates(subset=dup_subset, keep="first")
    n_dupes_removed = before - len(df)

    df = df.reset_index(drop=True)

    log(
        "customers.csv",
        f"- Строк на входе: {n_raw}\n"
        f"- Удалено дублей клиентов (совпадение имени/телефона/города/канала): {n_dupes_removed}\n"
        f"- Некорректных email (без @ / без домена) заменено на NaN: {n_invalid_email}\n"
        f"- Пропусков в registration_date после парсинга смешанных форматов: {n_missing_dates}\n"
        f"- Пропуски phone/city заполнены значением 'Unknown'\n"
        f"- Страны приведены к единому написанию (USA/Canada/United Kingdom/Germany/France)\n"
        f"- Строк на выходе: {len(df)}",
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

    # Себестоимость: пропуски восстанавливаем через медианную маржу по категории,
    # а не просто средним по всей таблице — так оценка точнее.
    df["cost_to_price_ratio"] = df["cost"] / df["price"]
    median_ratio_by_cat = df.groupby("category")["cost_to_price_ratio"].transform("median")
    n_missing_cost = int(df["cost"].isna().sum())
    df["cost"] = df["cost"].fillna(df["price"] * median_ratio_by_cat)
    df = df.drop(columns=["cost_to_price_ratio"])
    df["cost"] = df["cost"].round(2)

    log(
        "products.csv",
        f"- Строк на входе: {n_raw}\n"
        f"- Цена приведена к числовому типу (убран символ '$')\n"
        f"- Отрицательных цен исправлено (взято по модулю): {n_negative_price}\n"
        f"- Пропусков в cost восстановлено медианной маржой по категории: {n_missing_cost}\n"
        f"- Строк на выходе: {len(df)}",
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

    # Заказы без customer_id — не выбрасываем (потеряли бы выручку в анализе),
    # а помечаем суррогатным клиентом -1 ("Unknown"), как принято в дименсиональном моделировании.
    n_orphan = int(df["customer_id"].isna().sum())
    df["customer_id"] = df["customer_id"].apply(
        lambda x: -1 if pd.isna(x) or int(x) not in valid_customer_ids else int(x)
    )

    n_missing_dates = int(df["order_date"].isna().sum())
    df = df.dropna(subset=["order_date"]).reset_index(drop=True)

    log(
        "orders.csv",
        f"- Строк на входе: {n_raw}\n"
        f"- Удалено полных дублей order_id: {n_dupes_removed}\n"
        f"- Статус заказа приведён к нижнему регистру (completed/cancelled/returned)\n"
        f"- Заказов без customer_id, привязано к суррогатному клиенту -1 (Unknown): {n_orphan}\n"
        f"- Заказов с некорректной/отсутствующей датой удалено: {n_missing_dates}\n"
        f"- Строк на выходе: {len(df)}",
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
        f"- Строк на входе: {n_raw}\n"
        f"- Отрицательное количество (ошибка ввода) исправлено по модулю: {n_negative_qty}\n"
        f"- Позиций, ссылавшихся на удалённые order_id/product_id, удалено: {n_orphan_removed}\n"
        f"- Добавлен рассчитанный столбец line_revenue = qty * unit_price * (1 - discount)\n"
        f"- Строк на выходе: {len(df)}",
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
        f"- Строк: {len(df)}\n"
        f"- Отрицательных значений расхода скорректировано до 0: {n_negative}",
    )
    return df


def main():
    customers = clean_customers()

    # Добавляем суррогатного клиента "Unknown" для заказов без привязки к клиенту
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

    print(f"\nОчищенные таблицы сохранены в {PROCESSED_DIR}")
    print(f"Отчёт об очистке: {REPORTS_DIR / 'data_cleaning_report.md'}")


if __name__ == "__main__":
    main()
