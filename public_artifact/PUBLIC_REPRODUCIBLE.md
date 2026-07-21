# Public Artifact Reproducibility

Date: 2026-07-11

Run from this `public_artifact/` directory:

```bash
bash rebuild_and_verify_public_artifact.sh
```

The IndustrialCaseText builder reads the released label-free desensitized source-candidate file plus separated rebuild labels by default and does not require DataHub or private mappings. CaliberGraph and non-oracle comparators use only `blind_cases.jsonl` plus public catalogs/policies. Candidate labels and gold labels are used only by rebuild/scoring scripts. The explicitly marked oracle-candidate diagnostic receives the scorer metric by definition and is excluded from headline paired tests.

The artifact also includes public benchmark evaluators for MultiGov, IowaLiquor, Chinook, GovTwin, and BIRD diagnostics.

MultiGov coverage is joined through released current-metric dependency-to-asset bindings. The rebuild runs a five-case isolation suite that keeps other metrics' same-domain edges and bindings while removing only the selected metric's numerator, denominator, or coverage binding.

The mechanism audit writes semantic-layer validator, post-hoc answerability validator, residual-failure, circularity, protocol-card, and failure-certificate reports from released public files only. The external benchmark/baseline audit writes the reviewer-facing mapping from BIS, BI-Bench, TrustSQL, Spider 2.0, BIRD, AutoLink, SafeNLIDB, and SQL-agent baselines to the current evidence boundary. The external-anchor experiment audit counts released external records and public split sizes, then writes a baseline capability matrix that separates empirical failures from N/A-by-design coverage gaps.

Executed external evidence supplements those audits: Spider2-DBT dbt-parse coverage, TrustSQL raw official scorer outputs, a DataBench fixed subset audit, a dbt MetricFlow validator control, and a LightRAG custom-KG preflight. Heavy upstream clones and raw downloads are represented by fixed commit/source manifests plus compact derived evidence.

The public deterministic commands do not require private rows, DataHub, private mappings, or LLM keys.

The optional model-based task-validity audit under `experiments/model_task_validity_audit/` requires model/API access, is not human inter-annotator evidence, and is not part of the key-free rebuild path.

`bash verify_public_artifact.sh` is read-only. `bash rebuild_and_verify_public_artifact.sh` intentionally regenerates public outputs before verification.
