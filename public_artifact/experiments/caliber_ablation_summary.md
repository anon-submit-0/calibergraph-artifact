# CaliberGraph Ablation Evaluation

## Enterprise GovGraph

| Variant | Metric Acc. | Dimension Exact | Joint | Refusal P | Refusal R |
|---|---:|---:|---:|---:|---:|
| caliber_graph | 0.925 | 0.994 | 0.925 | 1.000 | 0.778 |
| no_dimension_resolver | 0.925 | 0.403 | 0.371 | 1.000 | 0.778 |
| no_graph_constraints | 0.881 | 0.403 | 0.352 | 0.000 | 0.000 |
| no_policy_compiler | 0.881 | 0.994 | 0.881 | 0.000 | 0.000 |

## Public Chinook-MetricCaliber

| Variant | Metric Acc. | Dimension Exact | Joint | Refusal P | Refusal R |
|---|---:|---:|---:|---:|---:|
| no_dimension_resolver | 1.000 | 0.525 | 0.525 | 1.000 | 1.000 |
| no_graph_constraints | 0.850 | 0.950 | 0.850 | 0.000 | 0.000 |
| no_policy_compiler | 0.850 | 0.950 | 0.850 | 0.000 | 0.000 |
| public_caliber_graph | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
