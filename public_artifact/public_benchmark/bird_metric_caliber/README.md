# BIRD-MetricCaliber Diagnostic Benchmark

Derived from BIRD Mini-Dev public `mini_dev_prompt.jsonl`.

- Source records: 500
- Aggregate metric-caliber cases: 206
- Unique metric signatures: 166
- Dimension columns parsed from schemas: 782

Gold labels are derived from the public SQL:

- metric signature: aggregate expression(s) in the SELECT clause;
- measure columns: columns used inside aggregate expressions;
- dimensions: GROUP BY expressions;
- tables: tables referenced by the SQL.

This split is a diagnostic benchmark for metric-caliber planning and verification, not a replacement for full SQL execution evaluation.
