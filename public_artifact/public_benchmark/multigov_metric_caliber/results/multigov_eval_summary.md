# MultiGov-MetricCaliber Results

Blind protocol: predictors read `blind_cases.jsonl` plus public catalogs; `gold_labels.jsonl` is used only by the scorer. The oracle-candidate row is explicitly a gold-metric upper-bound diagnostic.

## Main Results

| Method | Metric | Dim. | Joint | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|
| Direct keyword | 0.639 | 0.361 | 0.000 | 0.000 | 0.000 |
| Schema proxy | 0.639 | 0.680 | 0.320 | 0.000 | 0.000 |
| AutoLink-derived E3 | 0.639 | 0.680 | 0.320 | 0.000 | 0.000 |
| SafeNLIDB-derived E3 | 1.000 | 0.680 | 0.680 | 1.000 | 1.000 |
| Oracle-candidate | 1.000 | 0.680 | 0.680 | 1.000 | 1.000 |
| CaliberGraph | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Candidate Recall

- Answerable cases: 326
- Metric candidate recall@3: 1.000
- Dimension candidate recall: 1.000
- Joint candidate recall: 1.000

## Query-Family Joint Accuracy

| Family | AutoLink-derived E3 | SafeNLIDB-derived E3 | CaliberGraph |
|---|---:|---:|---:|
| answerable_direct | 1.000 | 1.000 | 1.000 |
| denominator_caliber | 1.000 | 1.000 | 1.000 |
| finest_grain_trap | 0.000 | 0.000 | 1.000 |
| policy_refusal | 0.000 | 1.000 | 1.000 |
| temporal_anchor | 1.000 | 1.000 | 1.000 |
