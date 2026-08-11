-- ============================================================================
-- Бизнес-вопросы к данным интернет-магазина (data/ecommerce.db)
-- ============================================================================
-- Выполнить: sqlite3 data/ecommerce.db < sql/business_questions.sql
-- либо построчно в любом SQL-клиенте / DBeaver / DataGrip.
--
-- Все запросы учитывают только успешно завершённые заказы
-- (order_status = 'completed'), если явно не сказано иное — так выручка
-- не искажается отменами и возвратами.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. Выручка, число заказов и средний чек (AOV) по месяцам
-- ----------------------------------------------------------------------------
SELECT
    d.year_month,
    ROUND(SUM(f.line_revenue), 2)                              AS revenue,
    COUNT(DISTINCT f.order_id)                                 AS orders_count,
    ROUND(SUM(f.line_revenue) * 1.0 / COUNT(DISTINCT f.order_id), 2) AS avg_order_value
FROM fact_orders f
JOIN dim_date d ON f.date_key = d.date_key
WHERE f.order_status = 'completed'
GROUP BY d.year_month
ORDER BY d.year_month;


-- ----------------------------------------------------------------------------
-- 2. Помесячный рост выручки (MoM, %) — оконная функция LAG
-- ----------------------------------------------------------------------------
WITH monthly_revenue AS (
    SELECT d.year_month, SUM(f.line_revenue) AS revenue
    FROM fact_orders f
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.order_status = 'completed'
    GROUP BY d.year_month
)
SELECT
    year_month,
    ROUND(revenue, 2) AS revenue,
    ROUND(revenue - LAG(revenue) OVER (ORDER BY year_month), 2) AS revenue_change,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY year_month)) * 100.0
        / LAG(revenue) OVER (ORDER BY year_month), 1
    ) AS mom_growth_pct
FROM monthly_revenue
ORDER BY year_month;


-- ----------------------------------------------------------------------------
-- 3. Топ-10 товаров по выручке
-- ----------------------------------------------------------------------------
SELECT
    p.product_name,
    p.category,
    SUM(f.quantity)                    AS units_sold,
    ROUND(SUM(f.line_revenue), 2)      AS revenue
FROM fact_orders f
JOIN dim_products p ON f.product_id = p.product_id
WHERE f.order_status = 'completed'
GROUP BY p.product_id, p.product_name, p.category
ORDER BY revenue DESC
LIMIT 10;


-- ----------------------------------------------------------------------------
-- 4. Выручка и маржа по категориям товаров
-- ----------------------------------------------------------------------------
SELECT
    p.category,
    ROUND(SUM(f.line_revenue), 2)                                       AS revenue,
    ROUND(SUM(f.quantity * (f.unit_price * (1 - f.discount) - p.cost)), 2) AS estimated_profit,
    ROUND(
        SUM(f.quantity * (f.unit_price * (1 - f.discount) - p.cost)) * 100.0
        / SUM(f.line_revenue), 1
    ) AS profit_margin_pct
FROM fact_orders f
JOIN dim_products p ON f.product_id = p.product_id
WHERE f.order_status = 'completed'
GROUP BY p.category
ORDER BY revenue DESC;


-- ----------------------------------------------------------------------------
-- 5. RFM-сегментация клиентов (Recency, Frequency, Monetary)
-- ----------------------------------------------------------------------------
WITH customer_orders AS (
    SELECT
        f.customer_id,
        MAX(d.date)                    AS last_order_date,
        COUNT(DISTINCT f.order_id)     AS frequency,
        SUM(f.line_revenue)            AS monetary
    FROM fact_orders f
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.order_status = 'completed' AND f.customer_id <> -1
    GROUP BY f.customer_id
),
rfm_scores AS (
    SELECT
        customer_id,
        CAST(julianday((SELECT MAX(date) FROM dim_date)) - julianday(last_order_date) AS INTEGER) AS recency_days,
        frequency,
        ROUND(monetary, 2) AS monetary,
        NTILE(4) OVER (ORDER BY julianday(last_order_date) DESC) AS r_score,  -- 4 = самые недавние
        NTILE(4) OVER (ORDER BY frequency ASC)                   AS f_score,
        NTILE(4) OVER (ORDER BY monetary ASC)                    AS m_score
    FROM customer_orders
)
SELECT
    customer_id,
    recency_days,
    frequency,
    monetary,
    r_score, f_score, m_score,
    CASE
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Champions'
        WHEN r_score >= 3 AND f_score <= 2                  THEN 'New / Promising'
        WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN 'At Risk (Valuable)'
        WHEN r_score <= 2 AND f_score <= 2                  THEN 'Lost / Hibernating'
        ELSE 'Regular'
    END AS rfm_segment
FROM rfm_scores
ORDER BY monetary DESC
LIMIT 20;


-- ----------------------------------------------------------------------------
-- 6. Когортный анализ удержания (retention) по месяцу первой покупки
-- ----------------------------------------------------------------------------
WITH first_purchase AS (
    SELECT customer_id, MIN(d.year_month) AS cohort_month
    FROM fact_orders f
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.order_status = 'completed' AND f.customer_id <> -1
    GROUP BY customer_id
),
orders_with_cohort AS (
    SELECT
        f.customer_id,
        fp.cohort_month,
        d.year_month AS order_month,
        (CAST(SUBSTR(d.year_month, 1, 4) AS INTEGER) - CAST(SUBSTR(fp.cohort_month, 1, 4) AS INTEGER)) * 12
            + (CAST(SUBSTR(d.year_month, 6, 2) AS INTEGER) - CAST(SUBSTR(fp.cohort_month, 6, 2) AS INTEGER))
            AS month_offset
    FROM fact_orders f
    JOIN dim_date d ON f.date_key = d.date_key
    JOIN first_purchase fp ON f.customer_id = fp.customer_id
    WHERE f.order_status = 'completed' AND f.customer_id <> -1
),
cohort_size AS (
    SELECT cohort_month, COUNT(DISTINCT customer_id) AS cohort_customers
    FROM first_purchase
    GROUP BY cohort_month
)
SELECT
    o.cohort_month,
    o.month_offset,
    COUNT(DISTINCT o.customer_id)                                          AS active_customers,
    cs.cohort_customers,
    ROUND(COUNT(DISTINCT o.customer_id) * 100.0 / cs.cohort_customers, 1)  AS retention_pct
FROM orders_with_cohort o
JOIN cohort_size cs ON o.cohort_month = cs.cohort_month
WHERE o.month_offset BETWEEN 0 AND 6
GROUP BY o.cohort_month, o.month_offset, cs.cohort_customers
ORDER BY o.cohort_month, o.month_offset;


-- ----------------------------------------------------------------------------
-- 7. Доля повторных покупателей (repeat purchase rate)
-- ----------------------------------------------------------------------------
WITH orders_per_customer AS (
    SELECT customer_id, COUNT(DISTINCT order_id) AS n_orders
    FROM fact_orders
    WHERE order_status = 'completed' AND customer_id <> -1
    GROUP BY customer_id
)
SELECT
    COUNT(*)                                             AS total_customers,
    SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END)         AS repeat_customers,
    ROUND(SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS repeat_rate_pct
FROM orders_per_customer;


-- ----------------------------------------------------------------------------
-- 8. Топ-15 клиентов по LTV (пожизненной ценности) — оконная функция RANK
-- ----------------------------------------------------------------------------
SELECT *
FROM (
    SELECT
        c.customer_id,
        c.full_name,
        c.country,
        ROUND(SUM(f.line_revenue), 2)               AS lifetime_value,
        COUNT(DISTINCT f.order_id)                   AS orders_count,
        RANK() OVER (ORDER BY SUM(f.line_revenue) DESC) AS ltv_rank
    FROM fact_orders f
    JOIN dim_customers c ON f.customer_id = c.customer_id
    WHERE f.order_status = 'completed' AND c.customer_id <> -1
    GROUP BY c.customer_id, c.full_name, c.country
)
WHERE ltv_rank <= 15
ORDER BY ltv_rank;


-- ----------------------------------------------------------------------------
-- 9. Доля заказов по статусам (completed / cancelled / returned)
-- ----------------------------------------------------------------------------
SELECT
    order_status,
    COUNT(DISTINCT order_id)                                                    AS orders_count,
    ROUND(COUNT(DISTINCT order_id) * 100.0 / (SELECT COUNT(DISTINCT order_id) FROM fact_orders), 1) AS pct_of_total
FROM fact_orders
GROUP BY order_status
ORDER BY orders_count DESC;


-- ----------------------------------------------------------------------------
-- 10. Маркетинг: расход и выручка по каналам, приблизительный ROAS
-- ----------------------------------------------------------------------------
WITH spend_by_channel AS (
    SELECT ch.channel_name, ROUND(SUM(m.spend), 2) AS total_spend
    FROM fact_marketing_spend m
    JOIN dim_channel ch ON m.channel_id = ch.channel_id
    GROUP BY ch.channel_name
),
revenue_by_channel AS (
    SELECT ch.channel_name, ROUND(SUM(f.line_revenue), 2) AS total_revenue
    FROM fact_orders f
    JOIN dim_channel ch ON f.channel_id = ch.channel_id
    WHERE f.order_status = 'completed'
    GROUP BY ch.channel_name
)
SELECT
    r.channel_name,
    r.total_revenue,
    COALESCE(s.total_spend, 0)                                             AS total_spend,
    CASE WHEN s.total_spend > 0
         THEN ROUND(r.total_revenue / s.total_spend, 2)
         ELSE NULL END                                                     AS roas   -- выручка на 1 у.е. расходов
FROM revenue_by_channel r
LEFT JOIN spend_by_channel s ON r.channel_name = s.channel_name
ORDER BY r.total_revenue DESC;


-- ----------------------------------------------------------------------------
-- 11. Средний чек по способу оплаты
-- ----------------------------------------------------------------------------
SELECT
    payment_method,
    COUNT(DISTINCT order_id)                                          AS orders_count,
    ROUND(SUM(line_revenue) / COUNT(DISTINCT order_id), 2)            AS avg_order_value
FROM fact_orders
WHERE order_status = 'completed'
GROUP BY payment_method
ORDER BY avg_order_value DESC;


-- ----------------------------------------------------------------------------
-- 12. Выручка по странам клиентов
-- ----------------------------------------------------------------------------
SELECT
    c.country,
    ROUND(SUM(f.line_revenue), 2) AS revenue,
    ROUND(SUM(f.line_revenue) * 100.0 / SUM(SUM(f.line_revenue)) OVER (), 1) AS pct_of_total
FROM fact_orders f
JOIN dim_customers c ON f.customer_id = c.customer_id
WHERE f.order_status = 'completed'
GROUP BY c.country
ORDER BY revenue DESC;


-- ----------------------------------------------------------------------------
-- 13. Накопленная (running total) выручка по месяцам
-- ----------------------------------------------------------------------------
WITH monthly_revenue AS (
    SELECT d.year_month, SUM(f.line_revenue) AS revenue
    FROM fact_orders f
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.order_status = 'completed'
    GROUP BY d.year_month
)
SELECT
    year_month,
    ROUND(revenue, 2) AS revenue,
    ROUND(SUM(revenue) OVER (ORDER BY year_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2) AS cumulative_revenue
FROM monthly_revenue
ORDER BY year_month;


-- ----------------------------------------------------------------------------
-- 14. Топ-10 товаров по маржинальности (% margin), продано хотя бы 20 шт.
-- ----------------------------------------------------------------------------
SELECT
    p.product_name,
    p.category,
    p.margin_pct,
    SUM(f.quantity) AS units_sold
FROM fact_orders f
JOIN dim_products p ON f.product_id = p.product_id
WHERE f.order_status = 'completed'
GROUP BY p.product_id, p.product_name, p.category, p.margin_pct
HAVING SUM(f.quantity) >= 20
ORDER BY p.margin_pct DESC
LIMIT 10;


-- ----------------------------------------------------------------------------
-- 15. Клиенты "в зоне риска оттока": последняя покупка > 90 дней назад,
--     но раньше покупали 2+ раза (были ценными)
-- ----------------------------------------------------------------------------
WITH customer_stats AS (
    SELECT
        f.customer_id,
        MAX(d.date)                AS last_order_date,
        COUNT(DISTINCT f.order_id) AS orders_count,
        SUM(f.line_revenue)        AS lifetime_value
    FROM fact_orders f
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.order_status = 'completed' AND f.customer_id <> -1
    GROUP BY f.customer_id
),
max_date AS (SELECT MAX(date) AS d FROM dim_date WHERE date_key IN (SELECT date_key FROM fact_orders))
SELECT
    cs.customer_id,
    c.full_name,
    cs.last_order_date,
    CAST(julianday((SELECT d FROM max_date)) - julianday(cs.last_order_date) AS INTEGER) AS days_since_last_order,
    cs.orders_count,
    ROUND(cs.lifetime_value, 2) AS lifetime_value
FROM customer_stats cs
JOIN dim_customers c ON cs.customer_id = c.customer_id
WHERE cs.orders_count >= 2
  AND julianday((SELECT d FROM max_date)) - julianday(cs.last_order_date) > 90
ORDER BY cs.lifetime_value DESC
LIMIT 20;


-- ----------------------------------------------------------------------------
-- 16. Выручка по дням недели (где чаще всего покупают)
-- ----------------------------------------------------------------------------
SELECT
    d.day_name,
    d.day_of_week,
    ROUND(SUM(f.line_revenue), 2)  AS revenue,
    COUNT(DISTINCT f.order_id)     AS orders_count
FROM fact_orders f
JOIN dim_date d ON f.date_key = d.date_key
WHERE f.order_status = 'completed'
GROUP BY d.day_name, d.day_of_week
ORDER BY d.day_of_week;
