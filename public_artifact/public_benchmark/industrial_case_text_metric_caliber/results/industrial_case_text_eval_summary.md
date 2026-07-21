# IndustrialCaseText-MetricCaliber Results

Predictors read `blind_cases.jsonl`; `gold_labels.jsonl` is used only for scoring.

| Method | Metric | Dim. | Joint | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|
| Direct keyword | 0.936 | 0.586 | 0.522 | 1.000 | 0.250 |
| Schema proxy | 0.936 | 0.930 | 0.866 | 1.000 | 0.250 |
| SafeNLIDB-derived E3 guard | 0.975 | 0.930 | 0.904 | 1.000 | 1.000 |
| CaliberGraph | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Deduplicated Normalized-Query Results

Groups per mode: 114; conflicting groups after withholding: 0.

| Method | Metric | Dim. | Joint | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|
| Direct keyword | 0.912 | 0.623 | 0.535 | 1.000 | 0.250 |
| Schema proxy | 0.912 | 0.904 | 0.816 | 1.000 | 0.250 |
| SafeNLIDB-derived E3 guard | 0.965 | 0.904 | 0.868 | 1.000 | 1.000 |
| CaliberGraph | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
