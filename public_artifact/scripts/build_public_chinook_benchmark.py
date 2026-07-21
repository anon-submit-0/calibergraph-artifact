#!/usr/bin/env python3
import json
import sqlite3
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public_benchmark"
DATA = PUBLIC / "data"

CHINOOK_URL = "https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"


METRICS = [
    {
        "metric_id": "revenue",
        "metric_name": "Revenue",
        "aliases": ["sales", "total sales", "invoice total", "收入", "销售额", "营收"],
        "formula": "SUM(Invoice.Total)",
        "numerator": "invoice_total",
        "denominator": "",
        "default_time": "all_time",
        "allowed_dimensions": ["country", "city", "customer", "support_rep", "year", "month"],
        "description": "Total invoice revenue.",
    },
    {
        "metric_id": "invoice_count",
        "metric_name": "Invoice Count",
        "aliases": ["orders", "order count", "number of orders", "number of invoices", "订单数", "发票数"],
        "formula": "COUNT(Invoice.InvoiceId)",
        "numerator": "invoice_count",
        "denominator": "",
        "default_time": "all_time",
        "allowed_dimensions": ["country", "city", "customer", "support_rep", "year", "month"],
        "description": "Number of invoices.",
    },
    {
        "metric_id": "units_sold",
        "metric_name": "Units Sold",
        "aliases": ["quantity sold", "tracks sold", "销量", "售出数量"],
        "formula": "SUM(InvoiceLine.Quantity)",
        "numerator": "quantity",
        "denominator": "",
        "default_time": "all_time",
        "allowed_dimensions": ["track", "album", "artist", "genre", "media_type", "year", "month"],
        "description": "Total quantity sold from invoice lines.",
    },
    {
        "metric_id": "average_order_value",
        "metric_name": "Average Order Value",
        "aliases": ["AOV", "average invoice total", "客单价", "平均订单金额"],
        "formula": "SUM(Invoice.Total) / COUNT(Invoice.InvoiceId)",
        "numerator": "revenue",
        "denominator": "invoice_count",
        "default_time": "all_time",
        "allowed_dimensions": ["country", "city", "support_rep", "year", "month"],
        "description": "Average invoice revenue per invoice.",
    },
    {
        "metric_id": "revenue_per_customer",
        "metric_name": "Revenue per Customer",
        "aliases": ["ARPC", "average customer revenue", "人均收入", "客户平均收入"],
        "formula": "SUM(Invoice.Total) / COUNT(DISTINCT Customer.CustomerId)",
        "numerator": "revenue",
        "denominator": "customer_count",
        "default_time": "all_time",
        "allowed_dimensions": ["country", "city", "support_rep", "year", "month"],
        "description": "Average revenue per distinct customer.",
    },
    {
        "metric_id": "customer_count",
        "metric_name": "Customer Count",
        "aliases": ["number of customers", "distinct customers", "客户数"],
        "formula": "COUNT(DISTINCT Customer.CustomerId)",
        "numerator": "customer_count",
        "denominator": "",
        "default_time": "all_time",
        "allowed_dimensions": ["country", "city", "support_rep"],
        "description": "Number of distinct customers.",
    },
    {
        "metric_id": "track_count",
        "metric_name": "Track Count",
        "aliases": ["number of tracks", "songs", "曲目数"],
        "formula": "COUNT(Track.TrackId)",
        "numerator": "track_count",
        "denominator": "",
        "default_time": "snapshot",
        "allowed_dimensions": ["album", "artist", "genre", "media_type"],
        "description": "Number of tracks in the catalog.",
    },
    {
        "metric_id": "playlist_track_count",
        "metric_name": "Playlist Track Count",
        "aliases": ["playlist size", "tracks in playlist", "歌单曲目数"],
        "formula": "COUNT(PlaylistTrack.TrackId)",
        "numerator": "playlist_track_count",
        "denominator": "",
        "default_time": "snapshot",
        "allowed_dimensions": ["playlist", "track", "album", "artist", "genre"],
        "description": "Number of track entries in playlists.",
    },
    {
        "metric_id": "refund_amount",
        "metric_name": "Refund Amount",
        "aliases": ["refunds", "退款金额"],
        "formula": "",
        "numerator": "",
        "denominator": "",
        "default_time": "",
        "allowed_dimensions": [],
        "description": "Unsupported in Chinook because there is no refund table or refund event.",
        "answerable": False,
    },
]


DIMS = [
    {"dimension_id": "country", "name": "Country", "aliases": ["billing country", "customer country", "国家"], "grain_rank": 1, "parent": ""},
    {"dimension_id": "city", "name": "City", "aliases": ["billing city", "城市"], "grain_rank": 2, "parent": "country"},
    {"dimension_id": "customer", "name": "Customer", "aliases": ["client", "客户"], "grain_rank": 3, "parent": "city", "sensitive": False},
    {"dimension_id": "support_rep", "name": "Support Rep", "aliases": ["employee", "sales rep", "销售"], "grain_rank": 2, "parent": ""},
    {"dimension_id": "year", "name": "Year", "aliases": ["annual", "by year", "年份"], "grain_rank": 1, "parent": ""},
    {"dimension_id": "month", "name": "Month", "aliases": ["monthly", "by month", "月份"], "grain_rank": 2, "parent": "year"},
    {"dimension_id": "artist", "name": "Artist", "aliases": ["singer", "band", "艺人"], "grain_rank": 1, "parent": ""},
    {"dimension_id": "album", "name": "Album", "aliases": ["专辑"], "grain_rank": 2, "parent": "artist"},
    {"dimension_id": "track", "name": "Track", "aliases": ["song", "曲目"], "grain_rank": 3, "parent": "album"},
    {"dimension_id": "genre", "name": "Genre", "aliases": ["music genre", "类别", "流派"], "grain_rank": 1, "parent": ""},
    {"dimension_id": "media_type", "name": "Media Type", "aliases": ["format", "媒体类型"], "grain_rank": 1, "parent": ""},
    {"dimension_id": "playlist", "name": "Playlist", "aliases": ["歌单"], "grain_rank": 1, "parent": ""},
]


CASES = [
    ("pub_001", "What was total revenue last year?", "revenue", [], "last_year"),
    ("pub_002", "Revenue by country", "revenue", ["country"], "all_time"),
    ("pub_003", "Revenue by country and city", "revenue", ["city"], "all_time"),
    ("pub_004", "Monthly revenue", "revenue", ["month"], "all_time"),
    ("pub_005", "Revenue by support rep", "revenue", ["support_rep"], "all_time"),
    ("pub_006", "How many invoices do we have?", "invoice_count", [], "all_time"),
    ("pub_007", "Invoice count by billing country", "invoice_count", ["country"], "all_time"),
    ("pub_008", "Order count by year and month", "invoice_count", ["month"], "all_time"),
    ("pub_009", "Average order value by country", "average_order_value", ["country"], "all_time"),
    ("pub_010", "AOV by country and city", "average_order_value", ["city"], "all_time"),
    ("pub_011", "Revenue per customer by country", "revenue_per_customer", ["country"], "all_time"),
    ("pub_012", "Average customer revenue by support rep", "revenue_per_customer", ["support_rep"], "all_time"),
    ("pub_013", "How many customers are in each country?", "customer_count", ["country"], "snapshot"),
    ("pub_014", "Customer count by country and city", "customer_count", ["city"], "snapshot"),
    ("pub_015", "How many units were sold?", "units_sold", [], "all_time"),
    ("pub_016", "Units sold by genre", "units_sold", ["genre"], "all_time"),
    ("pub_017", "Tracks sold by artist and album", "units_sold", ["album"], "all_time"),
    ("pub_018", "Tracks sold by artist, album, and track", "units_sold", ["track"], "all_time"),
    ("pub_019", "Units sold by media type", "units_sold", ["media_type"], "all_time"),
    ("pub_020", "How many tracks are in the catalog?", "track_count", [], "snapshot"),
    ("pub_021", "Track count by artist", "track_count", ["artist"], "snapshot"),
    ("pub_022", "Track count by artist and album", "track_count", ["album"], "snapshot"),
    ("pub_023", "Track count by genre", "track_count", ["genre"], "snapshot"),
    ("pub_024", "Playlist size by playlist", "playlist_track_count", ["playlist"], "snapshot"),
    ("pub_025", "Tracks in playlist by playlist and genre", "playlist_track_count", ["genre"], "snapshot"),
    ("pub_026", "Show me customer emails", "", [], ""),
    ("pub_027", "List employee phone numbers", "", [], ""),
    ("pub_028", "DROP TABLE Invoice", "", [], ""),
    ("pub_029", "What is the weather tomorrow?", "", [], ""),
    ("pub_030", "Refund amount by country", "", [], ""),
    ("pub_031", "退款金额按国家", "", [], ""),
    ("pub_032", "销售额按国家和城市", "revenue", ["city"], "all_time"),
    ("pub_033", "客单价按年份和月份", "average_order_value", ["month"], "all_time"),
    ("pub_034", "曲目数按艺人和专辑", "track_count", ["album"], "snapshot"),
    ("pub_035", "销量按艺人、专辑和曲目", "units_sold", ["track"], "all_time"),
    ("pub_036", "客户数按国家城市", "customer_count", ["city"], "snapshot"),
    ("pub_037", "sales by country vs city", "revenue", ["city"], "all_time"),
    ("pub_038", "revenue and invoice count comparison", "revenue", [], "all_time"),
    ("pub_039", "AOV by month", "average_order_value", ["month"], "all_time"),
    ("pub_040", "playlist track count by playlist and track", "playlist_track_count", ["track"], "snapshot"),
]


def download_chinook():
    DATA.mkdir(parents=True, exist_ok=True)
    db_path = DATA / "Chinook_Sqlite.sqlite"
    if not db_path.exists():
        with urllib.request.urlopen(CHINOOK_URL, timeout=60) as r:
            db_path.write_bytes(r.read())
    return db_path


def schema_summary(db_path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    tables = []
    table_names = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    for name in table_names:
        cols = cur.execute(f"PRAGMA table_info({name})").fetchall()
        count = cur.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        tables.append({"table": name, "rows": count, "columns": [c[1] for c in cols]})
    con.close()
    return tables


def main():
    db_path = download_chinook()
    tables = schema_summary(db_path)
    (DATA / "chinook_schema_summary.json").write_text(json.dumps(tables, ensure_ascii=False, indent=2) + "\n")
    (DATA / "chinook_metric_catalog.jsonl").write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in METRICS) + "\n")
    (DATA / "chinook_dimension_catalog.jsonl").write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in DIMS) + "\n")
    case_rows = []
    for case_id, query, metric, dims, time_window in CASES:
        case_rows.append(
            {
                "case_id": case_id,
                "nl_query": query,
                "expected_metric_id": metric,
                "expected_dimensions": dims,
                "expected_time_window": time_window,
                "expected_action": "refuse" if metric == "" else "answer",
            }
        )
    (DATA / "chinook_metric_cases.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in case_rows) + "\n")
    readme = f"""# Chinook-MetricCaliber Public Benchmark

Source database: Chinook SQLite sample database.

Source URL: {CHINOOK_URL}

Benchmark files:

- `Chinook_Sqlite.sqlite`: public SQLite database downloaded from the Chinook GitHub repository.
- `chinook_schema_summary.json`: table, column, and row-count summary.
- `chinook_metric_catalog.jsonl`: metric definitions and allowed dimensions.
- `chinook_dimension_catalog.jsonl`: dimensions, aliases, hierarchy, and grain rank.
- `chinook_metric_cases.jsonl`: 40 NL2Metric gold cases.

Task:

Map a natural-language analytics request to `metric_id`, dimensions, time window, and answer/refuse action.

Gold convention:

- If a query mentions multiple levels in a hierarchy, the gold dimension is the finest requested grain.
  Example: `country and city` -> `city`; `artist and album` -> `album`.
- PII requests, SQL/DDL requests, off-domain questions, and unsupported metrics such as refunds should be refused.
"""
    (PUBLIC / "README.md").write_text(readme)
    print(json.dumps({"db": str(db_path), "tables": len(tables), "cases": len(case_rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
