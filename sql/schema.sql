-- ============================================================================
-- Data schema: star schema for an electronics e-commerce store
-- ============================================================================
-- Compatible with SQLite (used in this project, file data/ecommerce.db).
-- For PostgreSQL: replace AUTOINCREMENT -> GENERATED ALWAYS AS IDENTITY,
-- TEXT -> VARCHAR if desired, the rest of the syntax is identical.
--
-- Tables are actually created and populated from pandas
-- (python/03_build_star_schema.py, df.to_sql). This file is the reference
-- schema description for documentation and for manually deploying to
-- another DBMS.
-- ============================================================================

-- -------------------------------------------------------------- dim_customers
CREATE TABLE dim_customers (
    customer_id            INTEGER PRIMARY KEY,   -- -1 = surrogate "Unknown" customer
    first_name             TEXT,
    last_name              TEXT,
    full_name              TEXT,
    email                  TEXT,
    phone                  TEXT,
    city                   TEXT,
    country                TEXT,
    registration_date      DATE,
    acquisition_channel    TEXT,
    acquisition_channel_id INTEGER REFERENCES dim_channel(channel_id)
);

-- --------------------------------------------------------------- dim_products
CREATE TABLE dim_products (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT,
    category      TEXT,
    subcategory   TEXT,
    price         REAL,
    cost          REAL,
    margin        REAL,   -- price - cost
    margin_pct    REAL    -- margin / price * 100
);

-- ---------------------------------------------------------------- dim_channel
CREATE TABLE dim_channel (
    channel_id    INTEGER PRIMARY KEY,
    channel_name  TEXT UNIQUE   -- organic_search / paid_search / social_media / email / referral / direct / unknown
);

-- ------------------------------------------------------------------- dim_date
CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,   -- YYYYMMDD
    date          DATE,
    year          INTEGER,
    quarter       INTEGER,
    month         INTEGER,
    month_name    TEXT,
    day           INTEGER,
    day_of_week   INTEGER,               -- 1 = Monday
    day_name      TEXT,
    is_weekend    BOOLEAN,
    year_month    TEXT                   -- 'YYYY-MM'
);

-- ----------------------------------------------------------------- fact_orders
-- Grain: one row = one order line item
CREATE TABLE fact_orders (
    order_item_id  INTEGER PRIMARY KEY,
    order_id       INTEGER,
    customer_id    INTEGER REFERENCES dim_customers(customer_id),
    product_id     INTEGER REFERENCES dim_products(product_id),
    date_key       INTEGER REFERENCES dim_date(date_key),
    channel_id     INTEGER REFERENCES dim_channel(channel_id),
    quantity       INTEGER,
    unit_price     REAL,
    discount       REAL,          -- discount share, 0.1 = 10%
    line_revenue   REAL,          -- quantity * unit_price * (1 - discount)
    order_status   TEXT,          -- completed / cancelled / returned
    payment_method TEXT
);

-- ------------------------------------------------------- fact_marketing_spend
-- Grain: day x channel (a separate fact at a different grain, linked to
-- the same dim_date / dim_channel — a classic star schema pattern)
CREATE TABLE fact_marketing_spend (
    date_key    INTEGER REFERENCES dim_date(date_key),
    channel_id  INTEGER REFERENCES dim_channel(channel_id),
    spend       REAL
);

CREATE INDEX idx_fact_orders_customer ON fact_orders(customer_id);
CREATE INDEX idx_fact_orders_product ON fact_orders(product_id);
CREATE INDEX idx_fact_orders_date ON fact_orders(date_key);
CREATE INDEX idx_fact_marketing_date ON fact_marketing_spend(date_key);
