# Closest Baseline Protocol Results

These results operationalize the two closest AAAI-26 baseline families on CaliberGraph's task.

## Public Chinook-MetricCaliber

| Method | Metric Acc. | Dim Exact | Dim Recall | Joint | Refusal P | Refusal R |
|---|---:|---:|---:|---:|---:|---:|
| autolink_iterative_public | 0.850 | 0.525 | 1.000 | 0.425 | 0.000 | 0.000 |
| caliber_graph_public | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| safenlidb_guarded_public | 1.000 | 0.575 | 1.000 | 0.575 | 1.000 | 1.000 |

AutoLink-derived E3 public linking recall:

- Metric candidate recall: 1.000
- Dimension candidate recall: 1.000
- Joint candidate recall: 1.000

## Enterprise GovGraph

| Method | Metric Acc. | Dim Exact | Dim Recall | Joint | Refusal P | Refusal R |
|---|---:|---:|---:|---:|---:|---:|
| autolink_iterative_enterprise | 0.893 | 0.302 | 1.000 | 0.283 | 1.000 | 0.222 |
| caliber_graph_enterprise | 0.925 | 0.994 | 0.994 | 0.925 | 1.000 | 0.778 |
| safenlidb_guarded_enterprise | 0.925 | 0.428 | 1.000 | 0.396 | 1.000 | 0.778 |

AutoLink-derived E3 enterprise linking recall:

- Metric candidate recall: 1.000
- Dimension candidate recall: 1.000
- Joint candidate recall: 1.000

## Paired Bootstrap

- Public CaliberGraph - AutoLink joint delta: 0.575 [0.425, 0.725]
- Public CaliberGraph - SafeNLIDB-guarded joint delta: 0.425 [0.275, 0.575]
- Enterprise CaliberGraph - AutoLink joint delta: 0.642 [0.566, 0.717]
- Enterprise CaliberGraph - SafeNLIDB-guarded joint delta: 0.528 [0.453, 0.610]

Interpretation: AutoLink-derived E3 retrieval achieves high candidate recall, but the final plan still needs coverage-caliber witness construction. SafeNLIDB-derived E3 guarding improves refusal behavior but does not resolve finest-grain dimension semantics.
