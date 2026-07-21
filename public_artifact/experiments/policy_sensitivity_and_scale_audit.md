# Public Scale and Label-Policy Sensitivity Audit

This audit is generated from released public files only. It is intended to answer two strong-review questions: whether the public evidence is too small, and whether the conclusion is only a byproduct of exact finest-grain dimension scoring.

## Public Evidence Scale

| Public layer | Cases | Evidence type |
|---|---:|---|
| BIRD-MetricCaliber | 206 | public NL/SQL/schema diagnostics |
| IowaLiquor-MetricCaliber | 32 | real public row-level business data |
| Chinook-MetricCaliber | 40 | public SQLite stress benchmark |
| GovTwin base | 159 | public anonymized structural stress test |
| GovTwin perturbations | 468 | deterministic robustness cases |
| GovTwin LLM paraphrases | 159 | frozen public paraphrases |
| MultiGov-MetricCaliber | 510 | production-derived anonymized governance cases |
| IndustrialCaseText scored | 157 | real desensitized enterprise case text |
| **Total public scored/diagnostic cases** | **1731** | across public diagnostics, row-level data, anonymized governance, and real desensitized case text |

## Headline Public Result Cross-Check

| Dataset | Schema/RAG joint | SafeNLIDB-derived E3 joint | CaliberGraph joint |
|---|---:|---:|---:|
| IowaLiquor | 0.562 | 0.781 | 1.000 |
| Chinook | 0.850 | -- | 1.000 |
| GovTwin | 0.679 | 0.736 | 1.000 |
| MultiGov | 0.320 | 0.680 | 1.000 |
| IndustrialCaseText | 0.866 | 0.904 | 1.000 |

## IndustrialCaseText Label-Policy Sensitivity

Exact dimension scoring follows the released label policy. Lenient-superset scoring additionally accepts predictions that include the governed finest grain plus extra parent dimensions. CaliberGraph remains best under both policies, and non-witness baselines still lose on action/refusal or coverage-caliber witness construction.

| Method | Action | Metric | Exact Dim. | Lenient Dim. | Exact Full | Lenient Full |
|---|---:|---:|---:|---:|---:|---:|
| Direct keyword | 0.962 | 0.936 | 0.586 | 0.586 | 0.522 | 0.522 |
| Schema proxy | 0.962 | 0.936 | 0.930 | 1.000 | 0.866 | 0.936 |
| SafeNLIDB-derived E3 | 1.000 | 0.975 | 0.930 | 1.000 | 0.904 | 0.975 |
| CaliberGraph | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Interpretation

- The public evidence is not a single 32-case public benchmark: the released artifact contains 1731 public scored or diagnostic cases, including 510 MultiGov cases and 157 real desensitized IndustrialCaseText cases.
- The exact finest-grain rule is not the only source of the result. Under lenient-superset scoring, Schema proxy and SafeNLIDB-derived E3 improve on dimension matching, but they still do not match CaliberGraph's full action+metric+dimension correctness.
- The evidence remains conservative: IndustrialCaseText releases case text and labels, not raw enterprise rows; official AutoLink/SafeNLIDB full-chain runs remain resource-gated and are not copied into result tables.
