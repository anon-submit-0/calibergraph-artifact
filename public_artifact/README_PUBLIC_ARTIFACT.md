# CaliberGraph Public Artifact

This is the reviewer-facing public artifact for the coverage-caliber witness release.

## Included

- IndustrialCaseText-MetricCaliber public desensitized case text, anonymized labels, blind/gold split, audits, and results.
- IndustrialCaseText label-free public desensitized source-candidate file plus separated rebuild/scorer labels for key-free rebuild.
- Public benchmark files for IowaLiquor, Chinook, GovTwin, MultiGov, and BIRD-derived diagnostics.
- MultiGov metric-specific numerator/denominator edges, dependency-to-asset bindings, and a five-case isolation suite that retains same-domain distractor evidence.
- Public deterministic evaluator scripts.
- Official AutoLink/SafeNLIDB resource-gated run-contract outputs.
- Mechanism, external benchmark/baseline, and external-anchor experiment audits generated from released evidence.
- Executed external evidence summary for Spider2-DBT, TrustSQL raw, DataBench, dbt MetricFlow, and LightRAG preflight.
- 12-model IndustrialCaseText LLM GraphRAG panel outputs.
- Complete-contract DeepSeek responses for all 898 cases, strongest-model
  MultiGov-200 responses, and transport-canary evidence.
- Validator-feedback replanning with the original preregistered 391-case scope,
  full IndustrialCaseText transfer, and exhaustive MultiGov-510 extension.
- Real MetricFlow 0.211.0 per-case results, path-sanitized logs, translated dbt
  project, and nine capability probes.
- Three anonymized practitioner annotation sheets, deterministic agreement and
  all-disagreement sensitivity scripts.
- Compiler replay/latency evidence and correctness-only enterprise aggregate
  pairs with an explicit non-significance guard.

## Not Included

Raw enterprise rows, private enterprise source ids, private table/column names, private metric ids, private-to-public mappings, credentials, local model-router keys, and private provenance digests.

## Key-Free Reproduction

```bash
bash rebuild_and_verify_public_artifact.sh
```

The builder defaults to the public label-free desensitized source-candidate file and separated label file. CaliberGraph and non-oracle comparators use only `blind_cases.jsonl` plus public catalogs/policies; labels are used only by rebuild/scoring scripts. The explicitly marked oracle-candidate diagnostic receives the scorer metric by definition and is excluded from headline paired tests. The external-evidence summary is the reviewer-facing entry point for executed adjacent evidence. `PUBLIC_MANIFEST.files` and `PUBLIC_SHA256SUMS` describe the public artifact payload after packaging.

`extended_controls/README.md` is the entry point for the strongest runnable
controls. Their stored responses can be rescored key-free. Repeating proprietary
model calls is optional and requires the reviewer's own compatible endpoint;
the artifact contains no internal endpoint or credential.

`bash verify_public_artifact.sh` performs read-only integrity and content checks. `bash rebuild_and_verify_public_artifact.sh` intentionally regenerates public outputs before running the read-only verifier.
