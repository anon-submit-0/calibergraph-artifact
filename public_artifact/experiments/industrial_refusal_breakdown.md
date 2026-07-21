# Industrial Refusal Breakdown

Aggregate-only breakdown; no private query text, metric id, table name, or column name is released.

## Gold Conflict Audit

| Audit item | Count |
|---|---:|
| Cases audited | 159 |
| Exact duplicate query groups | 22 |
| Duplicate groups with answer/refuse conflict | 1 |
| Cases inside conflicting groups | 2 |
| CaliberGraph refusal FNs overlapping conflict groups | 1 |

The audit is aggregate-only. It is used to interpret residual under-specified-request errors without releasing private query text.

## caliber_graph

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| no_recognized_business_vocab | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| off_domain | 3 | 3 | 0 | 0 | 1.000 | 1.000 |
| sql_or_ddl | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| unsupported_or_underconstrained_metric | 2 | 0 | 0 | 2 | 0.000 | 0.000 |

## direct_keyword

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| no_recognized_business_vocab | 2 | 0 | 0 | 2 | 0.000 | 0.000 |
| off_domain | 3 | 0 | 0 | 3 | 0.000 | 0.000 |
| sql_or_ddl | 2 | 0 | 0 | 2 | 0.000 | 0.000 |
| unsupported_or_underconstrained_metric | 2 | 0 | 0 | 2 | 0.000 | 0.000 |

## llm_direct

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| answerable | 9 | 0 | 9 | 0 | 0.000 | 0.000 |
| no_recognized_business_vocab | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| off_domain | 3 | 3 | 0 | 0 | 1.000 | 1.000 |
| sql_or_ddl | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| unsupported_or_underconstrained_metric | 2 | 0 | 0 | 2 | 0.000 | 0.000 |

## llm_graph_rag

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| answerable | 8 | 0 | 8 | 0 | 0.000 | 0.000 |
| no_recognized_business_vocab | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| off_domain | 3 | 3 | 0 | 0 | 1.000 | 1.000 |
| sql_or_ddl | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| unsupported_or_underconstrained_metric | 2 | 0 | 0 | 2 | 0.000 | 0.000 |

## llm_schema_rag

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| answerable | 4 | 0 | 4 | 0 | 0.000 | 0.000 |
| no_recognized_business_vocab | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| off_domain | 3 | 3 | 0 | 0 | 1.000 | 1.000 |
| sql_or_ddl | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| unsupported_or_underconstrained_metric | 2 | 0 | 0 | 2 | 0.000 | 0.000 |

## schema_rag

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| no_recognized_business_vocab | 2 | 0 | 0 | 2 | 0.000 | 0.000 |
| off_domain | 3 | 0 | 0 | 3 | 0.000 | 0.000 |
| sql_or_ddl | 2 | 0 | 0 | 2 | 0.000 | 0.000 |
| unsupported_or_underconstrained_metric | 2 | 0 | 0 | 2 | 0.000 | 0.000 |
