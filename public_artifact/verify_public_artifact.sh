#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

python3 - <<'PY'
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
required = [
    "experiments/enterprise_metric_cases_public_desensitized.jsonl",
    "experiments/enterprise_metric_cases_public_desensitized_labels.jsonl",
    "public_benchmark/industrial_case_text_metric_caliber/source_candidates_public_desensitized.jsonl",
    "public_benchmark/industrial_case_text_metric_caliber/source_candidate_labels_public_desensitized.jsonl",
    "public_benchmark/industrial_case_text_metric_caliber/LABEL_POLICY.md",
    "public_benchmark/industrial_case_text_metric_caliber/blind_cases.jsonl",
    "public_benchmark/industrial_case_text_metric_caliber/gold_labels.jsonl",
    "public_benchmark/iowa_liquor_metric_caliber/blind_cases.jsonl",
    "public_benchmark/iowa_liquor_metric_caliber/gold_labels.jsonl",
    "public_benchmark/govtwin_metric_caliber/blind_cases.jsonl",
    "public_benchmark/govtwin_metric_caliber/gold_labels.jsonl",
    "public_benchmark/multigov_metric_caliber/blind_cases.jsonl",
    "public_benchmark/multigov_metric_caliber/gold_labels.jsonl",
    "public_benchmark/multigov_metric_caliber/contract_profile.json",
    "public_benchmark/multigov_metric_caliber/metric_coverage_bindings.jsonl",
    "experiments/official_baseline_resource_gated/official_upstream_preflight.json",
    "experiments/mechanism_evidence_audit.md",
    "experiments/mechanism_evidence_audit.json",
    "experiments/EXTERNAL_BENCHMARK_BASELINE_AUDIT.md",
    "experiments/external_benchmark_baseline_audit.json",
    "experiments/EXTERNAL_ANCHOR_EXPERIMENT_AUDIT.md",
    "experiments/external_anchor_experiment_audit.json",
    "experiments/LEAKAGE_AND_CIRCULARITY_AUDIT.md",
    "experiments/MODEL_TASK_VALIDITY_AUDIT.md",
    "experiments/GUARANTEE_COMPARISON.md",
    "experiments/EXTERNAL_EVIDENCE_SUMMARY.md",
    "experiments/external_evidence_summary.json",
    "experiments/SPIDER2_DBT_PARSE_AUDIT.md",
    "experiments/trustsql_raw_official_eval/TRUSTSQL_RAW_OFFICIAL_EVAL.md",
    "experiments/databench_subset_eval/DATABENCH_SUBSET_AUDIT.md",
    "experiments/metricflow_validator_control/METRICFLOW_VALIDATOR_CONTROL.md",
    "experiments/lightrag_preflight/LIGHTRAG_PREFLIGHT.md",
    "experiments/METRICCALIBERBENCH_PROTOCOL_CARDS.md",
    "experiments/witness_failure_certificates.jsonl",
    "experiments/model_task_validity_audit/README.md",
    "experiments/model_task_validity_audit/summary.json",
    "scripts/build_industrial_case_text_metric_caliber.py",
    "scripts/build_blind_gold_splits.py",
    "scripts/calibergraph_contract_compiler.py",
    "scripts/normalize_multigov_coverage.py",
    "scripts/run_contract_mutation_suite.py",
    "scripts/run_multigov_binding_negative_suite.py",
    "scripts/run_compiler_trace_audit.py",
    "scripts/run_prompt_token_audit.py",
    "scripts/run_statistical_audit.py",
    "scripts/run_industrial_case_text_eval.py",
    "scripts/run_mechanism_evidence_audit.py",
    "scripts/run_external_benchmark_baseline_audit.py",
    "scripts/run_external_anchor_experiment_audit.py",
    "scripts/run_model_task_validity_audit.py",
    "scripts/run_external_evidence_summary.py",
    "experiments/contract_mutation_suite_results.json",
    "experiments/multigov_metric_binding_negative_suite.json",
    "experiments/compiler_trace_audit.json",
    "experiments/prompt_token_audit.json",
    "experiments/headline_statistical_audit.json",
    "extended_controls/README.md",
    "extended_controls/verify_extended_controls.py",
    "extended_controls/complete_contract_prompting/scores.json",
    "extended_controls/complete_contract_prompting/prompt_provenance_audit.json",
    "extended_controls/strongest_model_prompting/scores_ext.json",
    "extended_controls/strongest_model_prompting/transport_canary_audit.json",
    "extended_controls/validator_feedback_replanning/protocol.md",
    "extended_controls/validator_feedback_replanning/PROTOCOL_EXTENSION_ICT.md",
    "extended_controls/validator_feedback_replanning/scores.json",
    "extended_controls/validator_feedback_multigov_full/protocol.md",
    "extended_controls/validator_feedback_multigov_full/multigov_full_scores.json",
    "extended_controls/metricflow_real_engine/results/scores.json",
    "extended_controls/metricflow_real_engine/results/per_case_results.jsonl",
    "extended_controls/human_label_validation/iaa_results_anonymized.json",
    "extended_controls/human_label_validation/disagreement_sensitivity.json",
    "extended_controls/compiler_latency/compiler_latency_results.json",
    "extended_controls/enterprise_aggregate_control/anonymous_correctness_pairs.jsonl",
    "extended_controls/enterprise_aggregate_control/aggregate_results.json",
    "requirements.txt",
]
missing = [p for p in required if not (root / p).exists()]
if missing:
    raise SystemExit(f"missing required files: {missing}")

forbidden = re.compile(
    r"(^|/)\.git(/|$)|"
    + "internal" + "_author" + "_evidence|"
    + "source" + "_hash|"
    + r"credential|\.env|"
    + "private" + "_key",
    re.I,
)
forbidden_content = re.compile(
    "source" + "_hash|"
    + "data" + "_source" + "_hash|"
    + "source" + "_case" + "_hash",
    re.I,
)
local_identity_content = re.compile("/" + "Users/|" + "/" + "home/|" + "loc" + "tek", re.I)
constant_trace = "satisfied_by_" + "synthetic_coverage"
for path in root.rglob("*"):
    rel = path.relative_to(root).as_posix()
    if forbidden.search(rel):
        raise SystemExit(f"forbidden public artifact path: {rel}")
    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if forbidden_content.search(text):
            raise SystemExit(f"forbidden public artifact content in: {rel}")
        if local_identity_content.search(text):
            raise SystemExit(f"local path or author identity leaked into public artifact: {rel}")

multigov_root = root / "public_benchmark/multigov_metric_caliber"
for path in multigov_root.glob("*.jsonl"):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        digest_keys = sorted(key for key in row if "hash" in key.lower() or "digest" in key.lower())
        if digest_keys:
            raise SystemExit(f"private-derived digest keys leaked into {path.relative_to(root)}: {digest_keys}")

label_free_sources = [
    root / "experiments/enterprise_metric_cases_public_desensitized.jsonl",
    root / "public_benchmark/industrial_case_text_metric_caliber/source_candidates_public_desensitized.jsonl",
    root / "public_benchmark/industrial_case_text_metric_caliber/blind_cases.jsonl",
    root / "public_benchmark/iowa_liquor_metric_caliber/blind_cases.jsonl",
    root / "public_benchmark/govtwin_metric_caliber/blind_cases.jsonl",
    root / "public_benchmark/multigov_metric_caliber/blind_cases.jsonl",
]
for path in label_free_sources:
    text = path.read_text(encoding="utf-8")
    if "expected_" in text:
        raise SystemExit(f"label-free source file contains expected_* fields: {path.relative_to(root).as_posix()}")

prediction_files = [
    root / "public_benchmark/iowa_liquor_metric_caliber/results/iowa_liquor_predictions.jsonl",
    root / "public_benchmark/govtwin_metric_caliber/results/govtwin_predictions.jsonl",
    root / "public_benchmark/multigov_metric_caliber/results/multigov_predictions.jsonl",
    root / "public_benchmark/industrial_case_text_metric_caliber/results/industrial_case_text_predictions.jsonl",
]
required_checks = {"field", "caliber", "grain", "coverage", "time", "policy"}
for path in prediction_files:
    caliber_rows = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        leaked = [key for key in row if key.startswith("expected_")]
        if leaked:
            raise SystemExit(f"prediction contains gold fields in {path.relative_to(root)}: {leaked}")
        if row.get("mode") == "caliber_graph":
            caliber_rows += 1
            checks = set((row.get("trace") or {}).get("checks", {}))
            if checks != required_checks:
                raise SystemExit(f"incomplete compiler checks in {path.relative_to(root)}: {sorted(checks)}")
    if caliber_rows == 0:
        raise SystemExit(f"missing CaliberGraph rows in {path.relative_to(root)}")

mutation = json.loads((root / "experiments/contract_mutation_suite_results.json").read_text(encoding="utf-8"))
if mutation.get("case_count") != 7 or mutation.get("passed_count") != 7 or not mutation.get("all_passed"):
    raise SystemExit("contract mutation suite did not pass all seven cases")

binding_suite = json.loads((root / "experiments/multigov_metric_binding_negative_suite.json").read_text(encoding="utf-8"))
if binding_suite.get("case_count") != 5 or binding_suite.get("passed_count") != 5 or not binding_suite.get("all_passed"):
    raise SystemExit("MultiGov metric-specific binding negative suite did not pass all five cases")
retained = binding_suite.get("same_domain_other_metric_evidence_retained", {})
if not all(retained.get(key, 0) > 0 for key in ("numerator_edges", "denominator_edges", "coverage_bindings")):
    raise SystemExit("MultiGov isolation suite did not retain all same-domain distractor evidence types")

multigov = root / "public_benchmark/multigov_metric_caliber"
metrics = [json.loads(line) for line in (multigov / "metric_catalog.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
edges = [json.loads(line) for line in (multigov / "governance_edges.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
bindings = [json.loads(line) for line in (multigov / "metric_coverage_bindings.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
if len(bindings) != 178 or sum(bool(metric.get("coverage_nodes")) for metric in metrics) != 142:
    raise SystemExit("MultiGov metric-binding cardinalities differ from the frozen release contract")
for metric in metrics:
    metric_id = metric["metric_id"]
    if metric.get("scoped_ratio"):
        numerator = set(metric.get("numerator_nodes", []))
        denominator = set(metric.get("denominator_nodes", []))
        if not numerator or not denominator:
            raise SystemExit(f"ratio metric lacks explicit dependencies: {metric_id}")
        edge_num = {row.get("src") for row in edges if row.get("metric_id") == metric_id and row.get("edge_type") == "numerator_of"}
        edge_den = {row.get("src") for row in edges if row.get("metric_id") == metric_id and row.get("edge_type") == "denominator_of"}
        if numerator != edge_num or denominator != edge_den:
            raise SystemExit(f"ratio metric dependency edges are not metric-specific: {metric_id}")
    required = set(metric.get("coverage_nodes", []))
    if required:
        bound = {row.get("dependency_node_id") for row in bindings if row.get("metric_id") == metric_id}
        if not required.issubset(bound):
            raise SystemExit(f"metric coverage requirements lack metric-specific bindings: {metric_id}")

multigov_predictions = root / "public_benchmark/multigov_metric_caliber/results/multigov_predictions.jsonl"
coverage_active = 0
coverage_inactive = 0
for row in (json.loads(line) for line in multigov_predictions.read_text(encoding="utf-8").splitlines() if line.strip()):
    if row.get("mode") != "caliber_graph":
        continue
    coverage_check = row["trace"]["checks"]["coverage"]
    if coverage_check.get("active"):
        coverage_active += 1
        if not coverage_check.get("required_nodes"):
            raise SystemExit(f"active MultiGov coverage check has an empty required set: {row.get('case_id')}")
    else:
        coverage_inactive += 1
if (coverage_active, coverage_inactive) != (426, 84):
    raise SystemExit(
        f"MultiGov coverage activity differs from the frozen contract: active={coverage_active}, inactive={coverage_inactive}"
    )

stats = json.loads((root / "experiments/headline_statistical_audit.json").read_text(encoding="utf-8"))
for row in stats.get("results", []):
    if row["difference_ci95"][0] <= 0 or row["mcnemar_exact_two_sided_p"] > 0.05:
        raise SystemExit(f"headline statistical evidence failed for {row['dataset']}")

for path in root.rglob("*"):
    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if constant_trace in text:
            raise SystemExit(f"constant synthetic coverage trace remains in {path.relative_to(root)}")

manifest = root / "PUBLIC_MANIFEST.files"
if manifest.exists():
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rel = line.removeprefix("./")
        path = root / rel
        if not path.exists():
            raise SystemExit(f"manifest entry missing: {rel}")

sha_file = root / "PUBLIC_SHA256SUMS"
if sha_file.exists():
    for line in sha_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        expected = parts[0]
        rel = parts[-1].lstrip("*")
        path = root / rel
        if not path.exists():
            raise SystemExit(f"checksum entry missing: {rel}")
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != expected:
            raise SystemExit(f"checksum mismatch for {rel}: {got} != {expected}")

print("Public artifact read-only verification passed.")
PY

python3 extended_controls/verify_extended_controls.py
