#!/usr/bin/env python3
"""Re-score affected public layers after replacing disputed gold with human majority."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
RELEASE = HERE.parents[2]
PB = RELEASE / "public_artifact" / "public_benchmark"

PREDICTION_FILES = {
    "Chinook": PB / "experiments" / "public_chinook_predictions.jsonl",
    "IndustrialCaseText": PB / "industrial_case_text_metric_caliber" / "results" / "industrial_case_text_predictions.jsonl",
}

GOLD_FILES = {
    "Chinook": PB / "data" / "chinook_metric_cases.jsonl",
    "IndustrialCaseText": PB / "industrial_case_text_metric_caliber" / "gold_labels.jsonl",
}


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def prediction_ok(pred, label):
    predicted_action = pred.get("action") or ("refuse" if not pred.get("pred_metric_id") else "answer")
    return (
        predicted_action == label["action"]
        and pred.get("pred_metric_id", "") == label["metric"]
        and set(pred.get("pred_dimensions") or []) == set(label["dimensions"])
    )


def main():
    annotated = read_jsonl(HERE / "per_case_anonymized.jsonl")
    disagreements = {
        (row["layer"], row["case_id"]): row
        for row in annotated
        if row["majority"] != row["gold"]
    }
    result = {
        "policy": "replace all four majority-vs-released-gold disagreements; no cherry-picking",
        "n_disagreements": len(disagreements),
        "layers": {},
    }
    for layer, pred_path in PREDICTION_FILES.items():
        rows = read_jsonl(pred_path)
        released_gold = {
            row["case_id"]: {
                "action": row["expected_action"],
                "metric": row["expected_metric_id"],
                "dimensions": row["expected_dimensions"],
            }
            for row in read_jsonl(GOLD_FILES[layer])
        }
        by_mode = defaultdict(list)
        for row in rows:
            by_mode[row["mode"]].append(row)
        layer_report = {"n": len(next(iter(by_mode.values()))), "n_disputed": 0, "methods": {}}
        layer_disputes = {case_id: row for (row_layer, case_id), row in disagreements.items() if row_layer == layer}
        layer_report["n_disputed"] = len(layer_disputes)
        for mode, mode_rows in sorted(by_mode.items()):
            original_correct = 0
            sensitivity_correct = 0
            changed_case_outcomes = []
            for pred in mode_rows:
                case_id = pred["case_id"]
                if case_id in layer_disputes:
                    original_label = layer_disputes[case_id]["gold"]
                    sensitivity_label = layer_disputes[case_id]["majority"]
                    original_ok = prediction_ok(pred, original_label)
                    sensitivity_ok = prediction_ok(pred, sensitivity_label)
                    if original_ok != sensitivity_ok:
                        changed_case_outcomes.append(
                            {"case_id": case_id, "original_ok": original_ok, "human_majority_ok": sensitivity_ok}
                        )
                else:
                    original_label = released_gold[case_id]
                    sensitivity_label = original_label
                    original_ok = prediction_ok(pred, original_label)
                    sensitivity_ok = original_ok
                original_correct += int(original_ok)
                sensitivity_correct += int(sensitivity_ok)
            layer_report["methods"][mode] = {
                "released_gold_accuracy": original_correct / len(mode_rows),
                "human_majority_sensitivity_accuracy": sensitivity_correct / len(mode_rows),
                "delta": (sensitivity_correct - original_correct) / len(mode_rows),
                "changed_case_outcomes": changed_case_outcomes,
            }
        released_rank = sorted(
            layer_report["methods"],
            key=lambda mode: (-layer_report["methods"][mode]["released_gold_accuracy"], mode),
        )
        sensitivity_rank = sorted(
            layer_report["methods"],
            key=lambda mode: (-layer_report["methods"][mode]["human_majority_sensitivity_accuracy"], mode),
        )
        layer_report["released_rank"] = released_rank
        layer_report["sensitivity_rank"] = sensitivity_rank
        layer_report["top_method_set_unchanged"] = {
            mode
            for mode in released_rank
            if layer_report["methods"][mode]["released_gold_accuracy"]
            == layer_report["methods"][released_rank[0]]["released_gold_accuracy"]
        } == {
            mode
            for mode in sensitivity_rank
            if layer_report["methods"][mode]["human_majority_sensitivity_accuracy"]
            == layer_report["methods"][sensitivity_rank[0]]["human_majority_sensitivity_accuracy"]
        }
        result["layers"][layer] = layer_report
    (HERE / "disagreement_sensitivity.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
