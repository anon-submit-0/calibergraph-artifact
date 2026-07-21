#!/usr/bin/env python3
"""Recompute action-aware accuracy by released coverage-check activity."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parents[1]


def rows(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


LAYERS = {
    "iowa": {
        "gold": PUBLIC / "public_benchmark/iowa_liquor_metric_caliber/gold_labels.jsonl",
        "compiler": PUBLIC / "public_benchmark/iowa_liquor_metric_caliber/results/iowa_liquor_predictions.jsonl",
        "h1": PUBLIC / "extended_controls/complete_contract_prompting/predictions_iowa.jsonl",
    },
    "multigov": {
        "gold": PUBLIC / "public_benchmark/multigov_metric_caliber/gold_labels.jsonl",
        "compiler": PUBLIC / "public_benchmark/multigov_metric_caliber/results/multigov_predictions.jsonl",
        "h1": PUBLIC / "extended_controls/complete_contract_prompting/predictions_multigov.jsonl",
    },
    "ict": {
        "gold": PUBLIC / "public_benchmark/industrial_case_text_metric_caliber/gold_labels.jsonl",
        "compiler": PUBLIC / "public_benchmark/industrial_case_text_metric_caliber/results/industrial_case_text_predictions.jsonl",
        "h1": PUBLIC / "extended_controls/complete_contract_prompting/predictions_ict.jsonl",
    },
}


def normalize_prediction(prediction):
    return {
        "action": prediction.get("action", "refuse"),
        "metric": prediction.get("pred_metric_id", prediction.get("metric_id", "")),
        "dimensions": sorted(prediction.get("pred_dimensions", prediction.get("dimensions", [])) or []),
    }


def correct(prediction, gold):
    pred = normalize_prediction(prediction)
    if gold["expected_action"] == "refuse":
        return pred["action"] == "refuse"
    return (
        pred["action"] == "answer"
        and pred["metric"] == gold["expected_metric_id"]
        and pred["dimensions"] == sorted(gold.get("expected_dimensions", []) or [])
    )


def final_shared_validator_predictions():
    grouped = {}
    path = PUBLIC / "extended_controls/validator_feedback_replanning/per_case_rounds.jsonl"
    for row in rows(path):
        if row["layer"] not in {"iowa", "ict"}:
            continue
        key = (row["layer"], row["case_id"])
        if key not in grouped or row["round"] > grouped[key]["round"]:
            grouped[key] = row

    out = defaultdict(dict)
    for (layer, case_id), row in grouped.items():
        out[layer][case_id] = row["prediction"]

    multi_path = PUBLIC / "extended_controls/validator_feedback_multigov_full/raw_responses/multigov_full_loop_raw.jsonl"
    for row in rows(multi_path):
        out["multigov"][row["case_id"]] = row["rounds"][-1]["prediction"]
    return out


def summarize(flags, outcomes):
    result = {}
    for status in ("active", "inactive"):
        case_ids = sorted(case_id for case_id, active in flags.items() if active == (status == "active"))
        method_rows = {}
        for method, method_outcomes in outcomes.items():
            values = [bool(method_outcomes[case_id]) for case_id in case_ids]
            method_rows[method] = {
                "correct": sum(values),
                "n": len(values),
                "accuracy": sum(values) / len(values) if values else None,
            }
        result[status] = {"n": len(case_ids), "methods": method_rows}
    return result


def main():
    shared = final_shared_validator_predictions()
    layer_results = {}
    pooled_flags = {}
    pooled_outcomes = defaultdict(dict)

    for layer, paths in LAYERS.items():
        gold = {row["case_id"]: row for row in rows(paths["gold"])}
        compiler_rows = {
            row["case_id"]: row
            for row in rows(paths["compiler"])
            if row.get("mode") == "caliber_graph"
        }
        h1_rows = {row["case_id"]: row for row in rows(paths["h1"])}
        if set(gold) != set(compiler_rows) or set(gold) != set(h1_rows) or set(gold) != set(shared[layer]):
            raise AssertionError(f"case-set mismatch for {layer}")

        flags = {
            case_id: bool(row["trace"]["checks"]["coverage"]["active"])
            for case_id, row in compiler_rows.items()
        }
        outcomes = {
            "complete_contract_deepseek": {
                case_id: bool(h1_rows[case_id]["joint_ok"]) for case_id in gold
            },
            "shared_validator_repair": {
                case_id: correct(shared[layer][case_id], gold[case_id]) for case_id in gold
            },
            "calibergraph_reference": {
                case_id: correct(compiler_rows[case_id], gold[case_id]) for case_id in gold
            },
        }
        layer_results[layer] = summarize(flags, outcomes)

        for case_id, active in flags.items():
            pooled_id = f"{layer}:{case_id}"
            pooled_flags[pooled_id] = active
            for method, values in outcomes.items():
                pooled_outcomes[method][pooled_id] = values[case_id]

    output = {
        "scope": "headline base cases only: Iowa-32, MultiGov-510, IndustrialCaseText-157",
        "definition": "coverage activity is read from each released CaliberGraph trace; inactive means the public contract exposes no required physical binding and is never counted as an active coverage test",
        "layers": layer_results,
        "pooled": summarize(pooled_flags, pooled_outcomes),
    }
    (HERE / "coverage_activity_results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
