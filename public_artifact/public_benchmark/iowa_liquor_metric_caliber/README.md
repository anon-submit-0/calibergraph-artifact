# IowaLiquor-MetricCaliber

This benchmark is built from the real public State of Iowa 2024 Liquor Sales dataset.

- Source catalog: https://catalog.data.gov/dataset/iowa-liquor-sales-2024
- Columns API: https://idh-be.iowa.gov/api/v1/datasets/1261/columns.json
- Rows API: https://idh-be.iowa.gov/api/v1/datasets/1261/rows.csv
- License: Creative Commons Attribution 4.0 as listed by Data.gov for the source dataset.
- Public row snapshot: `5000` streamed rows, preserved in `iowa_liquor_2024_sample.csv` and `iowa_liquor_2024_sample.sqlite`.

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

Rows included in the local snapshot: 5000.
