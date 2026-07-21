# IowaLiquor-MetricCaliber Evaluation

Real public row-level business data from the State of Iowa 2024 Liquor Sales dataset.

| Method | Metric | Dim. | Joint | Ref.P | Ref.R | SQL exec. (ans.) |
|---|---:|---:|---:|---:|---:|---:|
| Direct keyword | 0.750 | 0.375 | 0.156 | 0.000 | 0.000 | 1.000 |
| Schema proxy | 0.781 | 0.719 | 0.562 | 0.000 | 0.000 | 1.000 |
| Open SQL end-to-end | 0.781 | 0.719 | 0.562 | 0.000 | 0.000 | 1.000 |
| AutoLink-derived E3 | 0.781 | 0.719 | 0.562 | 0.000 | 0.000 | 1.000 |
| SafeNLIDB-derived E3 | 1.000 | 0.781 | 0.781 | 1.000 | 1.000 | 1.000 |
| Oracle-candidate prompt | 1.000 | 0.781 | 0.781 | 1.000 | 1.000 | 1.000 |
| CaliberGraph | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Candidate Recall

- Answerable cases: 25
- Metric candidate recall@3: 1.000
- Dimension candidate recall: 1.000
- Joint candidate recall: 1.000

Interpretation: the open SQL baseline can generate executable SQLite queries, but executable SQL is not sufficient for governed metric caliber. The largest remaining gaps are finest-grain hierarchy resolution and refusal of unsupported or row-level requests.
