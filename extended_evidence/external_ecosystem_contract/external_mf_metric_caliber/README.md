# ExternalMF-MetricCaliber

MetricCaliberBench contract layer mechanically converted from a **third-party** semantic
layer that the paper authors did not write: the dbt Labs MetricFlow test manifest
`metricflow_semantics/test_helpers/semantic_manifest_yamls/simple_manifest`
(upstream: https://github.com/dbt-labs/metricflow, Apache-2.0; authored and maintained by
dbt Labs engineers). Frozen local copy used as the only input:
`v21_external_baseline_runs_20260708/public_artifact/external_runs/metricflow/` (see its
ATTRIBUTION.md / LICENSE).

Built under the pre-registered protocol `../protocol.md` (frozen 2026-07-12, before any
conversion/generation/eval).

- Converter: `../convert_mf_manifest.py` (mechanical, no randomness, no LLM; mapping rules
  frozen in its docstring: semantic_models -> physical bindings; entities/dimensions ->
  dimension catalog + hierarchy edges; simple/ratio/derived metrics -> metric definitions
  with ratio numerator/denominator explicit in the contract; agg_time_dimension -> the
  metric_time grain ladder).
- Case generator: `../generate_cases.py` (deterministic, seed=20260712, fixed NL template
  families only; gold labels derived mechanically from the contract).
- Refusal policy is **protocol-added, not in the source manifest** (three classes:
  undefined metric / SQL-DDL request / unauthorized dimension combination); every such
  artifact is flagged with provenance strings in the files below.

Files (field structure aligned with the v24 `public_benchmark` layers):

- `metric_catalog.jsonl`: 119 metrics (89 answerable: 40 simple, 9 ratio, 40 derived;
  24 manifest metrics not expressible in the contract format kept as answerable=false;
  6 protocol-added undefined-metric refusal stubs).
- `dimension_catalog.jsonl`: 10 categorical entity-qualified dimensions + 6 metric_time
  grains with hierarchy.
- `governance_edges.jsonl`: measures_of / rolls_up_to / numerator_of / denominator_of /
  governed_by.
- `physical_coverage.jsonl`, `metric_coverage_bindings.jsonl`: semantic->physical binding
  per semantic_model node_relation.
- `policy_catalog.jsonl`, `contract_profile.json`: protocol-added refusal policies.
- `blind_cases.jsonl` (122 cases, no gold fields), `gold_labels.jsonl`,
  `test_cases.jsonl` (merged + stratum), `generation_audit.json` (strata counts, seed,
  template inventory, ambiguity-guard log).
- `conversion_stats.json`: converter output statistics.
- `results/compiler_arm_predictions.jsonl`: per-case compiler-arm predictions
  (`../run_compiler_arm.py`).

No row-level data ships with this layer: the source manifest binds tables under the
`$source_schema` placeholder and contains no rows, so there is no SQL-execution column.

Reproduce:

```
python3 ../convert_mf_manifest.py
python3 ../generate_cases.py
python3 ../run_compiler_arm.py
```
