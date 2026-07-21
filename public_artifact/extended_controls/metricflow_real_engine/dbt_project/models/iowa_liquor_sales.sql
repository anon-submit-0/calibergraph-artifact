-- Physical base model for the MetricFlow semantic layer.
-- Adds a surrogate line-item key (sale_line_id) because the public snapshot's grain
-- (invoice line item) has no natural single-column key.
select
    row_number() over (order by invoice_id, item_no) as sale_line_id,
    invoice_id,
    ordered_on,
    store_no,
    store_name,
    store_address,
    store_city,
    store_zip_code,
    county_fips_code,
    county_name,
    category_code,
    category_name,
    vendor_number,
    vendor_name,
    item_no,
    im_desc,
    pack,
    bottle_volume_ml,
    sales_bottles,
    sales_dollars,
    sales_liters,
    sales_gallons
from raw_iowa_liquor_sales
