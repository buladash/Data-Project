
-- Business questions against the e-commerce data (ecommerce.db)



-- 1. Preview: first 10 rows of dim_products

SELECT *
FROM dim_products
LIMIT 10;


-- 2. Product names and prices only

SELECT product_name, price
FROM dim_products;


-- 3. Products in the Gaming category

SELECT *
FROM dim_products
WHERE category = 'Gaming';


-- 4. Products sorted by price, most expensive first

SELECT product_name, price
FROM dim_products
ORDER BY price DESC;


-- 5. Product count, average price and average cost by category

SELECT
    category,
    COUNT(*) AS count,
    AVG(price) AS avg_price,
    AVG(cost) AS avg_cost
FROM dim_products
GROUP BY category
ORDER BY AVG(price) DESC;


-- 6. Order line items joined with product details

SELECT f.quantity, f.unit_price, d.product_name, d.category
FROM fact_orders f
JOIN dim_products d ON f.product_id = d.product_id
LIMIT 15;


-- 7. Revenue by product category (completed orders only)

SELECT ROUND(SUM(f.line_revenue), 2) AS revenue, d.category
FROM fact_orders f
JOIN dim_products d ON f.product_id = d.product_id
WHERE status = 'completed'
GROUP BY category
ORDER BY SUM(line_revenue) DESC;


-- 8. Revenue by month

SELECT ROUND(SUM(f.line_revenue), 2) AS revenue, d.year, d.month
FROM fact_orders f
JOIN dim_date d ON f.date_key = d.date_key
WHERE status = 'completed'
GROUP BY year, month
ORDER BY year, month;


-- 9. Revenue by month, rewritten as a CTE

WITH monthly_revenue AS (
    SELECT ROUND(SUM(f.line_revenue), 2) AS revenue, d.year, d.month
    FROM fact_orders f
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE status = 'completed'
    GROUP BY year, month
)
SELECT * FROM monthly_revenue
ORDER BY year, month;


-- 10. Month-over-month revenue growth, %  (LAG window function)

WITH monthly_revenue AS (
    SELECT
        d.year,
        d.month,
        ROUND(SUM(f.line_revenue), 2) AS revenue
    FROM fact_orders f
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.status = 'completed'
    GROUP BY d.year, d.month
)
SELECT
    year, month, revenue,
    LAG(revenue) OVER (ORDER BY year, month) AS prev_month_revenue,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY year, month))
        / LAG(revenue) OVER (ORDER BY year, month) * 100, 1
    ) AS mom_growth_pct
FROM monthly_revenue
ORDER BY year, month;


-- 11. Top 10 customers by revenue, excluding the surrogate "Unknown" customer
--     (RANK window function)

WITH customer_revenue AS (
    SELECT
        a.customer_id,
        SUM(a.line_revenue) AS total_revenue
    FROM fact_orders a
    JOIN dim_customers b ON a.customer_id = b.customer_id
    WHERE status = 'completed' AND a.customer_id <> -1
    GROUP BY a.customer_id
)
SELECT
    customer_id,
    total_revenue,
    RANK() OVER (ORDER BY total_revenue DESC) AS revenue_rank
FROM customer_revenue
ORDER BY total_revenue DESC
LIMIT 10;


-- 12. Customers split into revenue quartiles (Monetary, for RFM segmentation)
--     Quartile 4 = highest-value customers  (NTILE window function)

WITH customer_revenue AS (
    SELECT
        a.customer_id,
        SUM(a.line_revenue) AS total_revenue
    FROM fact_orders a
    JOIN dim_customers b ON a.customer_id = b.customer_id
    WHERE status = 'completed' AND a.customer_id <> -1
    GROUP BY a.customer_id
)
SELECT
    customer_id,
    total_revenue,
    NTILE(4) OVER (ORDER BY total_revenue) AS revenue_quartile
FROM customer_revenue
ORDER BY total_revenue;
