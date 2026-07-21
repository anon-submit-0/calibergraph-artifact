# release Mechanism Evidence Audit

Generated from released public prediction/gold files only. This audit answers the toxic-review concern that the paper reports perfect contract scores without isolating mechanism.

## Fair Mechanism Baselines

Semantic-layer validator sees public catalogs/policies and validates retrieved candidates, but does not construct a finest-grain coverage witness. Post-hoc answerability validator refuses invalid retrieved/SQL plans but does not re-plan to a repaired answer.

| Dataset | Method | Joint | Action | Ref.P | Ref.R |
|---|---|---|---|---|---|
| iowa | semantic_layer_validator | 0.781 | 1.000 | 1.000 | 1.000 |
| iowa | posthoc_answerability_validator | 0.781 | 0.781 | 0.500 | 1.000 |
| iowa | caliber_graph | 1.000 | 1.000 | 1.000 | 1.000 |
| ict | semantic_layer_validator | 0.809 | 0.892 | 0.235 | 0.500 |
| ict | posthoc_answerability_validator | 0.809 | 0.828 | 0.148 | 0.500 |
| ict | caliber_graph | 1.000 | 1.000 | 1.000 | 1.000 |
| multigov | semantic_layer_validator | 0.680 | 1.000 | 1.000 | 1.000 |
| multigov | posthoc_answerability_validator | 0.680 | 0.680 | 0.530 | 1.000 |
| multigov | caliber_graph | 1.000 | 1.000 | 1.000 | 1.000 |

## Residual Failures After Candidate Availability

| Dataset | Mode | Candidate available | Residual fail given candidate | Residual families |
|---|---|---|---|---|
| iowa | schema_proxy | 1.000 | 0.280 | {"hierarchy_overexpansion": 7} |
| iowa | open_sql_end_to_end | 1.000 | 0.280 | {"hierarchy_overexpansion": 7} |
| iowa | autolink_iterative | 1.000 | 0.280 | {"hierarchy_overexpansion": 7} |
| iowa | safenlidb_guarded | 1.000 | 0.280 | {"hierarchy_overexpansion": 7} |
| iowa | oracle_candidate_prompt | 1.000 | 0.280 | {"hierarchy_overexpansion": 7} |
| ict | schema_proxy | 0.973 | 0.076 | {"hierarchy_overexpansion": 11} |
| ict | safenlidb_guarded | 0.973 | 0.076 | {"hierarchy_overexpansion": 11} |
| multigov | schema_proxy | 1.000 | 0.500 | {"hierarchy_overexpansion": 163} |
| multigov | autolink_iterative | 1.000 | 0.500 | {"hierarchy_overexpansion": 163} |
| multigov | safenlidb_guarded | 1.000 | 0.500 | {"hierarchy_overexpansion": 163} |
| multigov | oracle_candidate_prompt | 1.000 | 0.500 | {"hierarchy_overexpansion": 163} |

## Released Failure Certificates

- `witness_failure_certificates.jsonl` contains 20 public cases with baseline prediction, missing witness type, and CaliberGraph decision; 21 certificates were generated before applying the fixed release cap.
- These certificates are evidence for mechanism, not additional benchmark cases.
