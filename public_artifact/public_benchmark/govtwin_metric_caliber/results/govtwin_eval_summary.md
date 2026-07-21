# GovTwin-MetricCaliber Evaluation

## Plan Accuracy

| Method | Metric | Dim. | Joint | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|
| Direct keyword | 0.667 | 0.591 | 0.415 | 0.000 | 0.000 |
| Schema proxy | 0.943 | 0.736 | 0.679 | 0.000 | 0.000 |
| AutoLink-derived E3 | 0.943 | 0.736 | 0.679 | 0.000 | 0.000 |
| SafeNLIDB-derived E3 | 1.000 | 0.736 | 0.736 | 1.000 | 1.000 |
| Oracle-candidate prompt | 1.000 | 0.736 | 0.736 | 1.000 | 1.000 |
| CaliberGraph | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Candidate Recall

- Answerable cases: 150
- Metric candidate recall@3: 1.000
- Dimension candidate recall: 1.000
- Joint candidate recall: 1.000

Interpretation: GovTwin preserves the paper's central failure mode. Candidate discovery is not the bottleneck; final governed planning fails when prompt-style baselines keep every hierarchy level or answer policy-refusal cases.

## Perturbation Robustness

| Method | Metric | Dim. | Joint | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|
| Direct keyword | 0.688 | 0.583 | 0.365 | 0.000 | 0.000 |
| Schema proxy | 0.949 | 0.724 | 0.679 | 0.000 | 0.000 |
| AutoLink-derived E3 | 0.949 | 0.724 | 0.679 | 0.000 | 0.000 |
| SafeNLIDB-derived E3 | 0.987 | 0.731 | 0.718 | 1.000 | 1.000 |
| Oracle-candidate prompt | 1.000 | 0.731 | 0.731 | 1.000 | 1.000 |
| CaliberGraph | 0.987 | 1.000 | 0.987 | 1.000 | 1.000 |

## LLM Paraphrase Robustness

| Method | Metric | Dim. | Joint | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|
| Direct keyword | 0.943 | 0.591 | 0.535 | 0.000 | 0.000 |
| Schema proxy | 0.943 | 0.736 | 0.679 | 0.000 | 0.000 |
| AutoLink-derived E3 | 0.943 | 0.736 | 0.679 | 0.000 | 0.000 |
| SafeNLIDB-derived E3 | 1.000 | 0.736 | 0.736 | 1.000 | 1.000 |
| Oracle-candidate prompt | 1.000 | 0.736 | 0.736 | 1.000 | 1.000 |
| CaliberGraph | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## CaliberGraph Ablations

| Variant | Metric | Dim. | Joint | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|
| CaliberGraph | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| No grain compiler | 1.000 | 0.736 | 0.736 | 1.000 | 1.000 |
| No graph constraints | 0.943 | 0.736 | 0.679 | 0.000 | 0.000 |
| No policy compiler | 0.943 | 1.000 | 0.943 | 0.000 | 0.000 |

## Query-Family Joint Accuracy

| Family | AutoLink-derived E3 | SafeNLIDB-derived E3 | CaliberGraph |
|---|---:|---:|---:|
| hierarchy | 0.344 | 0.344 | 1.000 |
| single_or_flat_dimension | 1.000 | 1.000 | 1.000 |
| synthetic_refusal | 0.000 | 1.000 | 1.000 |
