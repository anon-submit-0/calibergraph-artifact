# release Leakage and Circularity Audit

This audit separates reproducibility from independent validity. Public reproducibility means another method can run on label-free inputs and be scored; it does not pretend that authored governance contracts are external human labels.

## Separation of Files

- Prediction inputs: blind cases, public catalogs, graph/policy files, public row data where applicable.
- Scorer-only files: `gold_labels.jsonl` or test-case `expected_*` fields.
- Generated predictions: include `used_gold_label: false` where traces are available; oracle-candidate rows are explicitly flagged as diagnostics.
- Private state: private DataHub rows, source ids, private table/column names, and private-to-public mappings are absent from public artifacts.

## Rule Visibility

| Rule family | Used by labels | Visible to baselines | Used by CaliberGraph | Leakage risk and control |
|---|---|---|---|---|
| Metric identity/aliases | Yes | Yes, via public metric catalogs | Yes | Shared contract; not a hidden label leak because catalogs are legal prediction inputs. |
| Dimension hierarchy | Yes | Yes, via dimension catalogs/edges | Yes | Shared contract; mechanism audit compares prompt/validator baselines that see it but do not compile witness repair. |
| Refusal/disclosure | Yes | Yes, via public policy files or trigger text where released | Yes | Scored as answer/refuse; gold labels are not prediction inputs. |
| Physical coverage | Yes | Partly visible through released coverage records where public | Yes | Claims are contract-bound; no private coverage names are released. |
| Gold expected ids | Yes | No | No during prediction | Verified by blind/gold split and label-free source checks. |

## Held-out or Stress Evidence

- GovTwin deterministic perturbations and LLM paraphrases stress the same policy contract outside base-case wording.
- IndustrialCaseText conflict-free and deduplicated subsets test whether label conflicts or duplicate weighting drive the result.
- release mechanism baselines show that seeing semantic-layer rules is insufficient without witness construction.

## release Mechanism Summary

| Dataset | Method | Joint | Ref.P | Ref.R |
|---|---|---|---|---|
| iowa | semantic_layer_validator | 0.781 | 1.000 | 1.000 |
| iowa | posthoc_answerability_validator | 0.781 | 0.500 | 1.000 |
| iowa | caliber_graph | 1.000 | 1.000 | 1.000 |
| ict | semantic_layer_validator | 0.809 | 0.235 | 0.500 |
| ict | posthoc_answerability_validator | 0.809 | 0.148 | 0.500 |
| ict | caliber_graph | 1.000 | 1.000 | 1.000 |
| multigov | semantic_layer_validator | 0.680 | 1.000 | 1.000 |
| multigov | posthoc_answerability_validator | 0.680 | 0.530 | 1.000 |
| multigov | caliber_graph | 1.000 | 1.000 | 1.000 |

## Remaining Boundary

The public benchmark is a governed-contract benchmark. The claim supported by these files is not universal NL2BI SOTA; it is that after candidate discovery is available, constructing an executable witness removes specific post-linking failures that retrieval, prompt finalization, semantic-layer validation, and post-hoc SQL validation leave unresolved.
