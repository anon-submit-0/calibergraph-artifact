#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export LC_ALL=C
export LANG=C

python3 scripts/build_industrial_case_text_metric_caliber.py --source public
python3 scripts/build_blind_gold_splits.py
python3 scripts/normalize_multigov_coverage.py
python3 scripts/run_industrial_case_text_eval.py
python3 scripts/run_iowa_liquor_eval.py
python3 scripts/run_multigov_metric_caliber_eval.py
python3 scripts/run_govtwin_eval.py
python3 scripts/run_public_chinook_eval.py
python3 scripts/run_compiler_trace_audit.py
python3 scripts/run_contract_mutation_suite.py
python3 scripts/run_multigov_binding_negative_suite.py
python3 scripts/run_prompt_token_audit.py
python3 scripts/run_statistical_audit.py
python3 scripts/run_official_baseline_preflight.py
python3 scripts/run_policy_sensitivity_audit.py
python3 scripts/run_mechanism_evidence_audit.py
python3 scripts/run_external_benchmark_baseline_audit.py
python3 scripts/run_external_anchor_experiment_audit.py
python3 scripts/run_external_evidence_summary.py

# Recompute all key-free extended-control outputs from stored responses.
python3 extended_controls/complete_contract_prompting/run_h1.py crosscheck
python3 extended_controls/complete_contract_prompting/run_h1.py score
python3 extended_controls/complete_contract_prompting/audit_prompt_provenance.py
python3 extended_controls/strongest_model_prompting/run_h1_ext.py score
python3 extended_controls/strongest_model_prompting/audit_transport_canaries.py
python3 extended_controls/validator_feedback_replanning/run_loop.py audit
python3 extended_controls/validator_feedback_replanning/run_loop.py compat
python3 extended_controls/validator_feedback_replanning/run_loop.py score
python3 extended_controls/validator_feedback_multigov_full/run_multigov_full.py audit
python3 extended_controls/validator_feedback_multigov_full/run_multigov_full.py score
python3 extended_controls/human_label_validation/recompute_iaa.py
python3 extended_controls/human_label_validation/run_disagreement_sensitivity.py
python3 extended_controls/coverage_activity_analysis/recompute.py
python3 extended_controls/enterprise_aggregate_control/recompute.py
python3 extended_controls/verify_extended_controls.py

find . -type d -name __pycache__ -prune -exec rm -rf {} +
find . -type f ! -name PUBLIC_SHA256SUMS ! -path '*/__pycache__/*' -print | LC_ALL=C sort > PUBLIC_MANIFEST.files
: > PUBLIC_SHA256SUMS
while IFS= read -r rel; do
  clean="${rel#./}"
  shasum -a 256 "$clean" >> PUBLIC_SHA256SUMS
done < PUBLIC_MANIFEST.files

bash verify_public_artifact.sh
