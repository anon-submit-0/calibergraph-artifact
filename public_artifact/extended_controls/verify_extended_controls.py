#!/usr/bin/env python3
"""Read-only consistency checks for the released extended controls."""

from __future__ import annotations

import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads((HERE / path).read_text(encoding="utf-8"))


def rows(path):
    return [
        json.loads(line)
        for line in (HERE / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def close(value, expected, tolerance=1e-12):
    if not math.isclose(value, expected, rel_tol=0, abs_tol=tolerance):
        raise AssertionError(f"{value} != {expected}")


def main():
    h1 = load("complete_contract_prompting/scores.json")
    expected_h1 = {
        "iowa": (32, 0.875),
        "chinook": (40, 0.925),
        "govtwin": (159, 0.7358490566037735),
        "multigov": (510, 0.8549019607843137),
        "ict": (157, 0.821656050955414),
    }
    for layer, (n, joint) in expected_h1.items():
        if h1[layer]["n"] != n:
            raise AssertionError(f"{layer}: wrong n")
        close(h1[layer]["joint_metric_dimension_accuracy"], joint)
        raw = rows(f"complete_contract_prompting/raw_responses/{layer}_raw.jsonl")
        if len(raw) != n or any(row.get("error") for row in raw):
            raise AssertionError(f"{layer}: incomplete H1 raw responses")
    provenance = load("complete_contract_prompting/prompt_provenance_audit.json")
    if not provenance.get("overall_complete"):
        raise AssertionError("complete-contract prompt provenance failed")

    strongest = load("strongest_model_prompting/scores_ext.json")["multigov"]
    close(strongest["claude-opus-4-6"]["joint_metric_dimension_accuracy"], 0.985)
    close(strongest["gpt-5.5"]["joint_metric_dimension_accuracy"], 1.0)
    canaries = load("strongest_model_prompting/transport_canary_audit.json")
    if not canaries.get("overall_pass"):
        raise AssertionError("strongest-model transport canary failed")

    replan = load("validator_feedback_replanning/scores.json")
    primary = replan["_primary_preregistered"]
    if primary["n"] != 391 or primary["preregistered_branch"] != "b_significant_improvement_not_closed":
        raise AssertionError("preregistered replan scope/branch drift")
    close(primary["round0_joint"], 0.8260869565217391)
    close(primary["final_joint"], 0.969309462915601)
    combined = replan["_pooled"]
    if combined["n"] != 548 or "descriptive" not in combined["scope_status"]:
        raise AssertionError("combined replan scope mislabeled")
    close(combined["round0_joint"], 0.8102189781021898)
    close(combined["final_joint"], 0.9434306569343066)

    full = load("validator_feedback_multigov_full/multigov_full_scores.json")
    if full["n"] != 510 or full["validator_invisible_final_error_count"] != 15:
        raise AssertionError("full MultiGov extension drift")
    close(full["replan_final_accuracy"], 0.9705882352941176)
    close(full["mcnemar_exact_two_sided_p"], 6.103515625e-05)
    if full["round0_wrong_to_final_right"] != 39 or full["round0_right_to_final_wrong"] != 0:
        raise AssertionError("full MultiGov transitions drift")

    iaa = load("human_label_validation/iaa_results_anonymized.json")
    if iaa["n"] != 120:
        raise AssertionError("human-label sample drift")
    close(iaa["fleiss_action"]["kappa"], 0.9675661065813776)
    sensitivity = load("human_label_validation/disagreement_sensitivity.json")
    if any(
        layer["released_rank"] != layer["sensitivity_rank"]
        for layer in sensitivity["layers"].values()
    ):
        raise AssertionError("human-label sensitivity ranking changed")

    metricflow_rows = rows("metricflow_real_engine/results/per_case_results.jsonl")
    if len(metricflow_rows) != 64:
        raise AssertionError("MetricFlow per-case result count drift")
    mf = load("metricflow_real_engine/results/scores.json")["metricflow_modes"]
    close(mf["metricflow_lexical"]["joint_metric_dimension_accuracy"], 0.625)
    close(mf["metricflow_oracle_metric"]["joint_metric_dimension_accuracy"], 0.78125)
    for path in list((HERE / "metricflow_real_engine/raw_outputs").rglob("*")) + list(
        (HERE / "metricflow_real_engine/probes").rglob("*")
    ):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        local_markers = ("/" + "Users/", "/private/" + "tmp/", "/var/" + "folders/")
        if any(marker in text for marker in local_markers):
            raise AssertionError(f"unsanitized MetricFlow path in {path.relative_to(HERE)}")

    latency = load("compiler_latency/compiler_latency_results.json")
    if latency["pooled"]["n_timed_calls"] != 17160:
        raise AssertionError("compiler latency call count drift")
    if any(value["replay_mismatches"] for value in latency["layers"].values()):
        raise AssertionError("compiler replay mismatch")

    coverage = load("coverage_activity_analysis/coverage_activity_results.json")["pooled"]
    if coverage["active"]["n"] != 458 or coverage["inactive"]["n"] != 241:
        raise AssertionError("headline coverage-activity counts drift")
    close(
        coverage["active"]["methods"]["shared_validator_repair"]["accuracy"],
        0.9737991266375546,
    )
    close(
        coverage["inactive"]["methods"]["shared_validator_repair"]["accuracy"],
        0.9087136929460581,
    )

    enterprise = load("enterprise_aggregate_control/aggregate_results.json")
    if enterprise["n"] != 159:
        raise AssertionError("enterprise aggregate pair count drift")
    close(enterprise["comparisons"]["replan_final"]["mcnemar_exact_two_sided_p"], 0.3876953125)

    forbidden = [
        "Co" + "dex",
        "Claude" + "Code",
        "/" + "Users/",
        "/private/" + "tmp/",
        "/var/" + "folders/",
    ]
    for path in HERE.rglob("*"):
        if not path.is_file() or path.suffix == ".duckdb" or path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(term in text for term in forbidden):
            raise AssertionError(f"workline or local-path marker in {path.relative_to(HERE)}")

    print("Extended-control verification passed.")


if __name__ == "__main__":
    main()
