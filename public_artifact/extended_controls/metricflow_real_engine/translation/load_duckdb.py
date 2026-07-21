#!/usr/bin/env python3
"""Load the public Iowa Liquor CSV snapshot into DuckDB and parity-check against the SQLite file.

MetricFlow has no SQLite adapter, so the benchmark data is copied into DuckDB.
Parity checks (row count, SUM(sales_dollars), COUNT(DISTINCT invoice_id/store_no/item_no),
min/max ordered_on) between the shipped SQLite file and the DuckDB copy are written to
data_parity.json. Any mismatch raises and aborts the experiment.
"""

import json
import sqlite3
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
RUN_ROOT = HERE.parent
BENCH = (
    RUN_ROOT.parents[2]
    / "public_artifact"
    / "public_benchmark"
    / "iowa_liquor_metric_caliber"
)
CSV = BENCH / "iowa_liquor_2024_sample.csv"
SQLITE = BENCH / "iowa_liquor_2024_sample.sqlite"
DUCKDB_PATH = RUN_ROOT / "dbt_project" / "data" / "iowa.duckdb"

CHECKS = {
    "row_count": "SELECT COUNT(*) FROM {t}",
    "sum_sales_dollars": "SELECT ROUND(SUM(sales_dollars), 2) FROM {t}",
    "sum_sales_bottles": "SELECT ROUND(SUM(sales_bottles), 2) FROM {t}",
    "sum_sales_liters": "SELECT ROUND(SUM(sales_liters), 2) FROM {t}",
    "distinct_invoice_id": "SELECT COUNT(DISTINCT invoice_id) FROM {t}",
    "distinct_store_no": "SELECT COUNT(DISTINCT store_no) FROM {t}",
    "distinct_item_no": "SELECT COUNT(DISTINCT item_no) FROM {t}",
    "min_ordered_on": "SELECT MIN(CAST(ordered_on AS TEXT)) FROM {t}",
    "max_ordered_on": "SELECT MAX(CAST(ordered_on AS TEXT)) FROM {t}",
}


def main():
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DUCKDB_PATH.exists():
        DUCKDB_PATH.unlink()

    con = duckdb.connect(str(DUCKDB_PATH))
    con.execute(
        f"""
        CREATE TABLE raw_iowa_liquor_sales AS
        SELECT
            CAST(invoice_id AS VARCHAR) AS invoice_id,
            CAST(ordered_on AS DATE) AS ordered_on,
            CAST(store_no AS VARCHAR) AS store_no,
            CAST(store_name AS VARCHAR) AS store_name,
            CAST(store_address AS VARCHAR) AS store_address,
            CAST(store_city AS VARCHAR) AS store_city,
            CAST(store_zip_code AS VARCHAR) AS store_zip_code,
            CAST(county_fips_code AS VARCHAR) AS county_fips_code,
            CAST(county_name AS VARCHAR) AS county_name,
            CAST(category_code AS VARCHAR) AS category_code,
            CAST(category_name AS VARCHAR) AS category_name,
            CAST(vendor_number AS VARCHAR) AS vendor_number,
            CAST(vendor_name AS VARCHAR) AS vendor_name,
            CAST(item_no AS VARCHAR) AS item_no,
            CAST(im_desc AS VARCHAR) AS im_desc,
            CAST(pack AS INTEGER) AS pack,
            CAST(bottle_volume_ml AS DOUBLE) AS bottle_volume_ml,
            CAST(sales_bottles AS DOUBLE) AS sales_bottles,
            CAST(sales_dollars AS DOUBLE) AS sales_dollars,
            CAST(sales_liters AS DOUBLE) AS sales_liters,
            CAST(sales_gallons AS DOUBLE) AS sales_gallons
        FROM read_csv(?, header=true)
        """,
        [str(CSV)],
    )

    sq = sqlite3.connect(str(SQLITE))
    parity = {"sqlite_table": "iowa_liquor_sales", "duckdb_table": "raw_iowa_liquor_sales", "checks": {}, "all_match": True}
    for name, sql in CHECKS.items():
        sqlite_val = sq.execute(sql.format(t="iowa_liquor_sales")).fetchone()[0]
        duck_val = con.execute(sql.format(t="raw_iowa_liquor_sales")).fetchone()[0]
        match = str(sqlite_val) == str(duck_val)
        parity["checks"][name] = {"sqlite": sqlite_val, "duckdb": duck_val, "match": match}
        if not match:
            parity["all_match"] = False
    sq.close()
    con.close()

    out = HERE / "data_parity.json"
    out.write_text(json.dumps(parity, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(parity, indent=2, default=str))
    if not parity["all_match"]:
        raise SystemExit("PARITY MISMATCH between SQLite source and DuckDB copy — aborting.")


if __name__ == "__main__":
    main()
