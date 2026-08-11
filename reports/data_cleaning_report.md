# Data Cleaning Report

## customers.csv

- Rows in: 9225
- Duplicate customers removed (matching name/phone/city/channel): 225
- Invalid emails (no @ / no domain) replaced with NaN: 124
- Missing registration_date after parsing mixed formats: 0
- Missing phone/city filled with 'Unknown'
- Countries normalized to a single spelling (USA/Canada/United Kingdom/Germany/France)
- Rows out: 9000

## products.csv

- Rows in: 160
- Price converted to a numeric type (stripped the '$' symbol)
- Negative prices fixed (took the absolute value): 1
- Missing cost backfilled via median margin per category: 6
- Rows out: 160

## orders.csv

- Rows in: 16160
- Exact order_id duplicates removed: 160
- Order status normalized to lowercase (completed/cancelled/returned)
- Orders with no customer_id, mapped to surrogate customer -1 (Unknown): 131
- Orders with an invalid/missing date removed: 0
- Rows out: 16000

## order_items.csv

- Rows in: 27187
- Negative quantities (data entry error) fixed via absolute value: 140
- Line items referencing removed order_id/product_id, dropped: 0
- Added computed column line_revenue = qty * unit_price * (1 - discount)
- Rows out: 27187

## marketing_spend.csv

- Rows: 2924
- Negative spend values clipped to 0: 0
