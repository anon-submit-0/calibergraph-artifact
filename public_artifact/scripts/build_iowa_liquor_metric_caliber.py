#!/usr/bin/env python3
"""Build IowaLiquor-MetricCaliber from a real public business dataset.

The source is the State of Iowa 2024 Liquor Sales dataset. The builder keeps a
small row-level public snapshot so reviewers can inspect schema, rows, metric
definitions, queries, labels, and executable SQL without private data access.
"""

import csv
import io
import json
import sqlite3
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public_benchmark" / "iowa_liquor_metric_caliber"
DATASET_URL = "https://catalog.data.gov/dataset/iowa-liquor-sales-2024"
COLUMNS_URL = "https://idh-be.iowa.gov/api/v1/datasets/1261/columns.json"
ROWS_CSV_URL = "https://idh-be.iowa.gov/api/v1/datasets/1261/rows.csv"
ROW_LIMIT = 5000


METRICS = [
    {
        "metric_id": "sales_dollars",
        "metric_name": "Sales Dollars",
        "aliases": ["sales", "revenue", "total sales", "sales amount"],
        "formula": "SUM(sales_dollars)",
        "allowed_dimensions": ["ordered_month", "ordered_quarter", "county_name", "store_city", "store_name", "category_name", "vendor_name", "item_desc"],
        "description": "Total public liquor sales dollars.",
        "answerable": True,
    },
    {
        "metric_id": "bottles_sold",
        "metric_name": "Bottles Sold",
        "aliases": ["bottles", "units sold", "volume in bottles"],
        "formula": "SUM(sales_bottles)",
        "allowed_dimensions": ["ordered_month", "ordered_quarter", "county_name", "store_city", "store_name", "category_name", "vendor_name", "item_desc"],
        "description": "Total bottles sold.",
        "answerable": True,
    },
    {
        "metric_id": "liters_sold",
        "metric_name": "Liters Sold",
        "aliases": ["liters", "volume liters", "sales liters"],
        "formula": "SUM(sales_liters)",
        "allowed_dimensions": ["ordered_month", "ordered_quarter", "county_name", "store_city", "store_name", "category_name", "vendor_name", "item_desc"],
        "description": "Total liters sold.",
        "answerable": True,
    },
    {
        "metric_id": "invoice_count",
        "metric_name": "Invoice Count",
        "aliases": ["invoices", "orders", "order count", "transactions"],
        "formula": "COUNT(DISTINCT invoice_id)",
        "allowed_dimensions": ["ordered_month", "ordered_quarter", "county_name", "store_city", "store_name", "category_name", "vendor_name"],
        "description": "Number of distinct public invoice identifiers.",
        "answerable": True,
    },
    {
        "metric_id": "store_count",
        "metric_name": "Store Count",
        "aliases": ["stores", "retailers", "store coverage"],
        "formula": "COUNT(DISTINCT store_no)",
        "allowed_dimensions": ["ordered_month", "ordered_quarter", "county_name", "store_city", "category_name", "vendor_name"],
        "description": "Number of distinct licensed stores in the selected slice.",
        "answerable": True,
    },
    {
        "metric_id": "item_count",
        "metric_name": "Item Count",
        "aliases": ["items", "products", "sku count", "item coverage"],
        "formula": "COUNT(DISTINCT item_no)",
        "allowed_dimensions": ["ordered_month", "ordered_quarter", "county_name", "store_city", "category_name", "vendor_name"],
        "description": "Number of distinct public item numbers.",
        "answerable": True,
    },
    {
        "metric_id": "average_bottle_price",
        "metric_name": "Average Bottle Price",
        "aliases": ["avg bottle price", "price per bottle", "average unit price"],
        "formula": "SUM(sales_dollars) / NULLIF(SUM(sales_bottles), 0)",
        "allowed_dimensions": ["ordered_month", "ordered_quarter", "county_name", "store_city", "store_name", "category_name", "vendor_name", "item_desc"],
        "description": "Sales dollars divided by bottles sold.",
        "answerable": True,
    },
    {
        "metric_id": "average_invoice_value",
        "metric_name": "Average Invoice Value",
        "aliases": ["aov", "average order value", "sales per invoice"],
        "formula": "SUM(sales_dollars) / NULLIF(COUNT(DISTINCT invoice_id), 0)",
        "allowed_dimensions": ["ordered_month", "ordered_quarter", "county_name", "store_city", "store_name", "category_name", "vendor_name"],
        "description": "Sales dollars divided by distinct invoice count.",
        "answerable": True,
    },
    {
        "metric_id": "profit_margin",
        "metric_name": "Profit Margin",
        "aliases": ["margin", "gross margin", "profit rate"],
        "formula": "",
        "allowed_dimensions": [],
        "description": "Unsupported because the public dataset has no cost or profit field.",
        "answerable": False,
    },
]


DIMS = [
    {"dimension_id": "ordered_month", "name": "Order Month", "aliases": ["month", "monthly", "ordered month"], "parent": "ordered_quarter", "grain_rank": 2, "sql": "substr(ordered_on, 1, 7)"},
    {"dimension_id": "ordered_quarter", "name": "Order Quarter", "aliases": ["quarter", "quarterly", "ordered quarter"], "parent": "", "grain_rank": 1, "sql": "strftime('%Y', ordered_on) || '-Q' || ((cast(strftime('%m', ordered_on) as integer) + 2) / 3)"},
    {"dimension_id": "county_name", "name": "County", "aliases": ["county"], "parent": "", "grain_rank": 1, "sql": "county_name"},
    {"dimension_id": "store_city", "name": "Store City", "aliases": ["city", "store city"], "parent": "county_name", "grain_rank": 2, "sql": "store_city"},
    {"dimension_id": "store_name", "name": "Store Name", "aliases": ["store", "retailer", "store name"], "parent": "store_city", "grain_rank": 3, "sql": "store_name"},
    {"dimension_id": "category_name", "name": "Category", "aliases": ["category", "liquor category"], "parent": "", "grain_rank": 1, "sql": "category_name"},
    {"dimension_id": "vendor_name", "name": "Vendor", "aliases": ["vendor", "supplier"], "parent": "", "grain_rank": 1, "sql": "vendor_name"},
    {"dimension_id": "item_desc", "name": "Item Description", "aliases": ["item", "product", "sku", "item description"], "parent": "category_name", "grain_rank": 2, "sql": "im_desc"},
]


BASE_CASES = [
    ("iowa_001", "What were total liquor sales dollars?", "sales_dollars", []),
    ("iowa_002", "Sales dollars by county", "sales_dollars", ["county_name"]),
    ("iowa_003", "Sales by county and city", "sales_dollars", ["store_city"]),
    ("iowa_004", "Sales by category and item", "sales_dollars", ["item_desc"]),
    ("iowa_005", "Monthly liquor sales", "sales_dollars", ["ordered_month"]),
    ("iowa_006", "Quarterly sales dollars by county", "sales_dollars", ["ordered_quarter", "county_name"]),
    ("iowa_007", "How many bottles were sold?", "bottles_sold", []),
    ("iowa_008", "Bottles sold by vendor", "bottles_sold", ["vendor_name"]),
    ("iowa_009", "Bottles by category and item", "bottles_sold", ["item_desc"]),
    ("iowa_010", "Liters sold by county", "liters_sold", ["county_name"]),
    ("iowa_011", "Volume in liters by county and city", "liters_sold", ["store_city"]),
    ("iowa_012", "How many invoices are in the public liquor data?", "invoice_count", []),
    ("iowa_013", "Invoice count by month", "invoice_count", ["ordered_month"]),
    ("iowa_014", "Order count by county and city", "invoice_count", ["store_city"]),
    ("iowa_015", "How many stores sold liquor?", "store_count", []),
    ("iowa_016", "Store count by county", "store_count", ["county_name"]),
    ("iowa_017", "Retailer count by city", "store_count", ["store_city"]),
    ("iowa_018", "How many products appear in the sales data?", "item_count", []),
    ("iowa_019", "Item count by category", "item_count", ["category_name"]),
    ("iowa_020", "Product count by vendor", "item_count", ["vendor_name"]),
    ("iowa_021", "Average bottle price by category", "average_bottle_price", ["category_name"]),
    ("iowa_022", "Price per bottle by category and item", "average_bottle_price", ["item_desc"]),
    ("iowa_023", "Average order value by county", "average_invoice_value", ["county_name"]),
    ("iowa_024", "AOV by county and city", "average_invoice_value", ["store_city"]),
    ("iowa_025", "Average invoice value by vendor", "average_invoice_value", ["vendor_name"]),
    ("iowa_026", "Show raw invoice ids", "", []),
    ("iowa_027", "List store addresses", "", []),
    ("iowa_028", "DROP TABLE iowa_liquor_sales", "", []),
    ("iowa_029", "What is the weather in Iowa tomorrow?", "", []),
    ("iowa_030", "Profit margin by category", "", []),
    ("iowa_031", "Gross margin by vendor", "", []),
    ("iowa_032", "Customer phone numbers for liquor buyers", "", []),
]


def fetch_columns():
    request = urllib.request.Request(COLUMNS_URL, headers={"User-Agent": "CaliberGraph research artifact builder"})
    with urllib.request.urlopen(request, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_rows(limit):
    request = urllib.request.Request(ROWS_CSV_URL, headers={"User-Agent": "CaliberGraph research artifact builder"})
    with urllib.request.urlopen(request, timeout=120) as resp:
        wrapper = io.TextIOWrapper(resp, encoding="utf-8", newline="")
        reader = csv.DictReader(wrapper)
        rows = []
        for row in reader:
            rows.append(row)
            if len(rows) >= limit:
                break
    return rows


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n", encoding="utf-8")


def coerce_float(value):
    try:
        return float(value)
    except Exception:
        return None


def build_sqlite(rows):
    db_path = OUT / "iowa_liquor_2024_sample.sqlite"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE iowa_liquor_sales (
            invoice_id TEXT,
            ordered_on TEXT,
            store_no TEXT,
            store_name TEXT,
            store_address TEXT,
            store_city TEXT,
            store_zip_code TEXT,
            county_fips_code TEXT,
            county_name TEXT,
            category_code TEXT,
            category_name TEXT,
            vendor_number TEXT,
            vendor_name TEXT,
            item_no TEXT,
            im_desc TEXT,
            pack INTEGER,
            bottle_volume_ml REAL,
            sales_bottles REAL,
            sales_dollars REAL,
            sales_liters REAL,
            sales_gallons REAL
        )
        """
    )
    for row in rows:
        conn.execute(
            """
            INSERT INTO iowa_liquor_sales VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("invoice_id"),
                (row.get("ordered_on") or "")[:10],
                row.get("store_no"),
                row.get("store_name"),
                row.get("store_address"),
                row.get("store_city"),
                row.get("store_zip_code"),
                row.get("county_fips_code"),
                row.get("county_name"),
                row.get("category_code"),
                row.get("category_name"),
                row.get("vendor_number"),
                row.get("vendor_name"),
                row.get("item_no"),
                row.get("im_desc"),
                int(float(row.get("pack") or 0)),
                coerce_float(row.get("bottle_volume_ml")),
                coerce_float(row.get("sales_bottles")),
                coerce_float(row.get("sales_dollars")),
                coerce_float(row.get("sales_liters")),
                coerce_float(row.get("sales_gallons")),
            ),
        )
    conn.commit()
    conn.close()


def cases():
    out = []
    for case_id, query, metric_id, dims in BASE_CASES:
        out.append(
            {
                "case_id": case_id,
                "nl_query": query,
                "expected_action": "answer" if metric_id else "refuse",
                "expected_metric_id": metric_id,
                "expected_dimensions": dims,
                "expected_time_window": "2024",
                "source": "author_labeled_over_public_iowa_liquor_schema",
            }
        )
    return out


def edges():
    rows = []
    for metric in METRICS:
        for dim in metric.get("allowed_dimensions", []):
            rows.append({"src": metric["metric_id"], "dst": dim, "edge_type": "measures_of"})
    for dim in DIMS:
        if dim.get("parent"):
            rows.append({"src": dim["dimension_id"], "dst": dim["parent"], "edge_type": "rolls_up_to"})
    for metric in METRICS:
        if metric["answerable"]:
            rows.append({"src": metric["metric_id"], "dst": "aggregate_only_policy", "edge_type": "governed_by"})
    rows.extend(
        [
            {"src": "invoice_id", "dst": "aggregate_only_policy", "edge_type": "governed_by"},
            {"src": "store_address", "dst": "aggregate_only_policy", "edge_type": "governed_by"},
            {"src": "profit_margin", "dst": "unsupported_metric_policy", "edge_type": "governed_by"},
        ]
    )
    return rows


def write_readme(row_count):
    text = f"""# IowaLiquor-MetricCaliber

This benchmark is built from the real public State of Iowa 2024 Liquor Sales dataset.

- Source catalog: {DATASET_URL}
- Columns API: {COLUMNS_URL}
- Rows API: {ROWS_CSV_URL}
- License: Creative Commons Attribution 4.0 as listed by Data.gov for the source dataset.
- Public row snapshot: `{ROW_LIMIT}` streamed rows, preserved in `iowa_liquor_2024_sample.csv` and `iowa_liquor_2024_sample.sqlite`.

Unlike GovTwin, this benchmark is not a semantic twin of private enterprise data. The schema and row values are publicly inspectable, and all metric definitions, dimension policies, natural-language test cases, gold labels, and executable SQL generation rules are released.

Boundary: the row-level data is externally public; the metric-caliber semantic layer and NL2Metric labels are author-defined over that public schema to test governed metric planning.

Files:

- `schema_columns.json`: public source schema returned by the State of Iowa API.
- `iowa_liquor_2024_sample.csv`: row-level public snapshot.
- `iowa_liquor_2024_sample.sqlite`: executable SQLite copy of the snapshot.
- `metric_catalog.jsonl`: governed metrics and formulas.
- `dimension_catalog.jsonl`: dimensions, hierarchy, and SQL expressions.
- `governance_edges.jsonl`: metric-dimension, hierarchy, and policy edges.
- `test_cases.jsonl`: public queries and labels.

Rows included in the local snapshot: {row_count}.
"""
    (OUT / "README.md").write_text(text, encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    columns = fetch_columns()
    rows = fetch_rows(ROW_LIMIT)
    (OUT / "schema_columns.json").write_text(json.dumps(columns, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (OUT / "iowa_liquor_2024_sample.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[c["name"] for c in columns])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    build_sqlite(rows)
    write_jsonl(OUT / "metric_catalog.jsonl", METRICS)
    write_jsonl(OUT / "dimension_catalog.jsonl", DIMS)
    write_jsonl(OUT / "governance_edges.jsonl", edges())
    write_jsonl(OUT / "test_cases.jsonl", cases())
    write_readme(len(rows))
    print(json.dumps({"benchmark": str(OUT), "rows": len(rows), "cases": len(BASE_CASES)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
