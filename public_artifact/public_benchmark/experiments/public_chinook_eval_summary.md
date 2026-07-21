# Public Chinook-MetricCaliber Evaluation

Cases: 40

| Mode | Metric Acc. | Dimension Exact | Joint Metric+Dim | Refusal P | Refusal R |
|---|---:|---:|---:|---:|---:|
| direct_keyword | 0.600 | 0.275 | 0.150 | 0.167 | 0.167 |
| llm_direct | 0.975 | 0.775 | 0.750 | 0.857 | 1.000 |
| llm_graph_rag | 0.975 | 0.950 | 0.925 | 0.857 | 1.000 |
| llm_schema_rag | 0.975 | 0.625 | 0.600 | 0.857 | 1.000 |
| public_caliber_graph | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| schema_rag | 0.850 | 0.950 | 0.850 | 0.000 | 0.000 |
