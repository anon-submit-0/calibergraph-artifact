# GovTwin Refusal Breakdown

## Direct keyword

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| sensitive_or_identifier | 1 | 0 | 0 | 1 | 0.000 | 0.000 |
| sql_or_ddl | 7 | 0 | 0 | 7 | 0.000 | 0.000 |
| unsupported_metric | 1 | 0 | 0 | 1 | 0.000 | 0.000 |

## Schema proxy

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| sensitive_or_identifier | 1 | 0 | 0 | 1 | 0.000 | 0.000 |
| sql_or_ddl | 7 | 0 | 0 | 7 | 0.000 | 0.000 |
| unsupported_metric | 1 | 0 | 0 | 1 | 0.000 | 0.000 |

## AutoLink-derived E3

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| sensitive_or_identifier | 1 | 0 | 0 | 1 | 0.000 | 0.000 |
| sql_or_ddl | 7 | 0 | 0 | 7 | 0.000 | 0.000 |
| unsupported_metric | 1 | 0 | 0 | 1 | 0.000 | 0.000 |

## SafeNLIDB-derived E3

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| sensitive_or_identifier | 1 | 1 | 0 | 0 | 1.000 | 1.000 |
| sql_or_ddl | 7 | 7 | 0 | 0 | 1.000 | 1.000 |
| unsupported_metric | 1 | 1 | 0 | 0 | 1.000 | 1.000 |

## Oracle-candidate prompt

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| sensitive_or_identifier | 1 | 1 | 0 | 0 | 1.000 | 1.000 |
| sql_or_ddl | 7 | 7 | 0 | 0 | 1.000 | 1.000 |
| unsupported_metric | 1 | 1 | 0 | 0 | 1.000 | 1.000 |

## CaliberGraph

| Category | N | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| sensitive_or_identifier | 1 | 1 | 0 | 0 | 1.000 | 1.000 |
| sql_or_ddl | 7 | 7 | 0 | 0 | 1.000 | 1.000 |
| unsupported_metric | 1 | 1 | 0 | 0 | 1.000 | 1.000 |
