"""
Готовит две дополнительные таблицы для Power BI, которые проще посчитать
в pandas один раз, чем воспроизводить сложной DAX-логикой в отчёте:

  - dim_customer_rfm.csv        — RFM-сегмент на каждого клиента (1:1 к dim_customers)
  - fact_cohort_retention.csv   — таблица retention по когортам (для матрицы/heatmap)

Запуск:
    python python/04_export_powerbi_extras.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "ecommerce.db"
POWERBI_DIR = ROOT / "data" / "powerbi"


def main():
    conn = sqlite3.connect(DB_PATH)

    orders = pd.read_sql(
        """
        SELECT f.customer_id, f.order_id, f.line_revenue, d.date
        FROM fact_orders f
        JOIN dim_date d ON f.date_key = d.date_key
        WHERE f.order_status = 'completed' AND f.customer_id <> -1
        """,
        conn,
        parse_dates=["date"],
    )

    # ------------------------------------------------------------------- RFM
    snapshot_date = orders["date"].max() + pd.Timedelta(days=1)
    rfm = orders.groupby("customer_id").agg(
        recency_days=("date", lambda x: (snapshot_date - x.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("line_revenue", "sum"),
    ).reset_index()

    rfm["r_score"] = pd.qcut(rfm["recency_days"], 4, labels=[4, 3, 2, 1]).astype(int)
    rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["m_score"] = pd.qcut(rfm["monetary"], 4, labels=[1, 2, 3, 4]).astype(int)

    def segment(row):
        if row.r_score >= 3 and row.f_score >= 3 and row.m_score >= 3:
            return "Champions"
        if row.r_score >= 3 and row.f_score <= 2:
            return "New / Promising"
        if row.r_score <= 2 and row.f_score >= 3 and row.m_score >= 3:
            return "At Risk (Valuable)"
        if row.r_score <= 2 and row.f_score <= 2:
            return "Lost / Hibernating"
        return "Regular"

    rfm["monetary"] = rfm["monetary"].round(2)
    rfm["rfm_segment"] = rfm.apply(segment, axis=1)
    rfm.to_csv(POWERBI_DIR / "dim_customer_rfm.csv", index=False)
    print(f"dim_customer_rfm.csv -> {len(rfm)} строк")

    # ------------------------------------------------------------- COHORTS
    cohort_base = orders.copy()
    cohort_base["order_month"] = cohort_base["date"].dt.to_period("M")
    cohort_base["cohort_month"] = cohort_base.groupby("customer_id")["order_month"].transform("min")
    cohort_base["month_offset"] = (
        cohort_base["order_month"] - cohort_base["cohort_month"]
    ).apply(lambda x: x.n)

    cohort_size = (
        cohort_base[cohort_base["month_offset"] == 0]
        .groupby("cohort_month")["customer_id"].nunique()
        .rename("cohort_customers")
    )

    cohort_counts = (
        cohort_base[cohort_base["month_offset"].between(0, 6)]
        .groupby(["cohort_month", "month_offset"])["customer_id"].nunique()
        .rename("active_customers")
        .reset_index()
    )
    cohort_counts = cohort_counts.merge(cohort_size, on="cohort_month")
    cohort_counts["retention_pct"] = (
        cohort_counts["active_customers"] / cohort_counts["cohort_customers"] * 100
    ).round(1)
    cohort_counts["cohort_month"] = cohort_counts["cohort_month"].astype(str)

    cohort_counts.to_csv(POWERBI_DIR / "fact_cohort_retention.csv", index=False)
    print(f"fact_cohort_retention.csv -> {len(cohort_counts)} строк")


if __name__ == "__main__":
    main()
