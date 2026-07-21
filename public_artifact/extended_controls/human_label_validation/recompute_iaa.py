#!/usr/bin/env python3
"""Recompute anonymized human-label agreement from released A/B/C sheets.

The script reads no author-filled gold column from the annotation sheets. Gold
is joined by case_id from the public benchmark release after annotations are
loaded. No annotator name is written to the output.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
RELEASE = HERE.parents[2]
PB = RELEASE / "public_artifact" / "public_benchmark"

ACTION = "标注1_action(answer/refuse)"
METRIC = "标注2_metric_id(按目录)"
DIMS = "标注3_dimensions(分号分隔,按治理粒度)"
UNCERTAIN = "标注4_不确定请打?并写原因"

SHEETS = {
    "A": HERE / "annotation_sheet_v1_annotatorA_anonymized.csv",
    "B": HERE / "annotation_sheet_v1_annotatorB_anonymized.csv",
    "C": HERE / "annotation_sheet_v1_annotatorC_anonymized.csv",
}

GOLD_FILES = {
    "IowaLiquor": PB / "iowa_liquor_metric_caliber" / "gold_labels.jsonl",
    "Chinook": PB / "data" / "chinook_metric_cases.jsonl",
    "GovTwin": PB / "govtwin_metric_caliber" / "gold_labels.jsonl",
    "MultiGov": PB / "multigov_metric_caliber" / "gold_labels.jsonl",
    "IndustrialCaseText": PB / "industrial_case_text_metric_caliber" / "gold_labels.jsonl",
}


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_sheet(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def norm_action(value):
    value = str(value or "").strip().lower()
    if value not in {"answer", "refuse"}:
        raise ValueError(f"invalid action annotation: {value!r}")
    return value


def norm_metric(value):
    return str(value or "").strip()


def norm_dims(value):
    value = str(value or "").strip()
    if not value:
        return tuple()
    return tuple(sorted({item.strip() for item in value.replace(",", ";").split(";") if item.strip()}))


def majority(values):
    counts = Counter(values)
    value, count = counts.most_common(1)[0]
    if count <= len(values) // 2:
        raise ValueError(f"no strict majority: {values}")
    return value


def fleiss_kappa(label_rows, categories):
    n_raters = len(label_rows[0])
    n_items = len(label_rows)
    per_item = []
    totals = Counter()
    for labels in label_rows:
        counts = Counter(labels)
        totals.update(counts)
        per_item.append((sum(counts[c] ** 2 for c in categories) - n_raters) / (n_raters * (n_raters - 1)))
    p_bar = sum(per_item) / n_items
    proportions = {c: totals[c] / (n_items * n_raters) for c in categories}
    p_expected = sum(value * value for value in proportions.values())
    kappa = (p_bar - p_expected) / (1 - p_expected)
    return {"kappa": kappa, "observed_agreement": p_bar, "expected_agreement": p_expected}


def cohen_kappa(left, right, categories):
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    lp = Counter(left)
    rp = Counter(right)
    expected = sum((lp[c] / len(left)) * (rp[c] / len(right)) for c in categories)
    return {"kappa": (observed - expected) / (1 - expected), "raw_agreement": observed}


def load_gold():
    joined = {}
    for layer, path in GOLD_FILES.items():
        for row in read_jsonl(path):
            joined[(layer, row["case_id"])] = {
                "action": row["expected_action"],
                "metric": row["expected_metric_id"],
                "dimensions": tuple(sorted(row["expected_dimensions"])),
            }
    return joined


def main():
    sheets = {key: read_sheet(path) for key, path in SHEETS.items()}
    lengths = {key: len(rows) for key, rows in sheets.items()}
    if len(set(lengths.values())) != 1:
        raise SystemExit(f"sheet length mismatch: {lengths}")
    order = [(row["layer"], row["case_id"], row["nl_query"]) for row in sheets["A"]]
    for annotator, rows in sheets.items():
        candidate_order = [(row["layer"], row["case_id"], row["nl_query"]) for row in rows]
        if candidate_order != order:
            raise SystemExit(f"row order/content mismatch in anonymized sheet {annotator}")

    gold = load_gold()
    action_rows = []
    records = []
    for index, (layer, case_id, query) in enumerate(order):
        annotations = []
        for annotator in sorted(sheets):
            row = sheets[annotator][index]
            annotations.append(
                {
                    "annotator": annotator,
                    "action": norm_action(row[ACTION]),
                    "metric": norm_metric(row[METRIC]),
                    "dimensions": norm_dims(row[DIMS]),
                    "uncertain": str(row[UNCERTAIN] or "").strip(),
                }
            )
        action_rows.append([item["action"] for item in annotations])
        key = (layer, case_id)
        if key not in gold:
            raise SystemExit(f"gold case missing: {key}")
        majority_action = majority([item["action"] for item in annotations])
        answering = [item for item in annotations if item["action"] == "answer"]
        majority_metric = majority([item["metric"] for item in answering]) if majority_action == "answer" else ""
        majority_dims = majority([item["dimensions"] for item in answering]) if majority_action == "answer" else tuple()
        records.append(
            {
                "layer": layer,
                "case_id": case_id,
                "nl_query": query,
                "annotations": annotations,
                "majority": {
                    "action": majority_action,
                    "metric": majority_metric,
                    "dimensions": list(majority_dims),
                },
                "gold": {
                    "action": gold[key]["action"],
                    "metric": gold[key]["metric"],
                    "dimensions": list(gold[key]["dimensions"]),
                },
            }
        )

    action_stats = fleiss_kappa(action_rows, ["answer", "refuse"])
    pairwise = {}
    for left, right in [("A", "B"), ("A", "C"), ("B", "C")]:
        pairwise[f"{left}-{right}"] = cohen_kappa(
            [row[sorted(sheets).index(left)] for row in action_rows],
            [row[sorted(sheets).index(right)] for row in action_rows],
            ["answer", "refuse"],
        )

    answer_records = [row for row in records if row["majority"]["action"] == "answer"]
    disagreements = [
        {
            "layer": row["layer"],
            "case_id": row["case_id"],
            "majority": row["majority"],
            "gold": row["gold"],
        }
        for row in records
        if row["majority"] != row["gold"]
    ]
    result = {
        "provenance": {
            "source": "three frozen anonymized practitioner sheets",
            "recomputed_by": "deterministic release script",
            "annotator_ids": sorted(sheets),
            "gold_joined_after_annotation_load": True,
        },
        "n": len(records),
        "fleiss_action": action_stats,
        "pairwise_action": pairwise,
        "majority_vs_gold": {
            "action_agreement": sum(row["majority"]["action"] == row["gold"]["action"] for row in records) / len(records),
            "action_unanimous_rate": sum(len(set(labels)) == 1 for labels in action_rows) / len(action_rows),
            "metric_agreement_given_majority_answer": sum(row["majority"]["metric"] == row["gold"]["metric"] for row in answer_records) / len(answer_records),
            "dimension_exact_given_majority_answer": sum(row["majority"]["dimensions"] == row["gold"]["dimensions"] for row in answer_records) / len(answer_records),
            "n_majority_answer": len(answer_records),
        },
        "per_layer_action_agreement": {
            layer: sum(row["majority"]["action"] == row["gold"]["action"] for row in records if row["layer"] == layer)
            / sum(row["layer"] == layer for row in records)
            for layer in sorted({row["layer"] for row in records})
        },
        "uncertain_flags": {
            annotator: sum(bool(sheets[annotator][index][UNCERTAIN].strip()) for index in range(len(order)))
            for annotator in sorted(sheets)
        },
        "majority_gold_disagreements": disagreements,
    }
    (HERE / "iaa_results_anonymized.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    safe_records = [
        {
            "layer": row["layer"],
            "case_id": row["case_id"],
            "majority": row["majority"],
            "gold": row["gold"],
            "annotator_actions": [item["action"] for item in row["annotations"]],
            "annotator_metrics": [item["metric"] for item in row["annotations"]],
            "annotator_dimensions": [item["dimensions"] for item in row["annotations"]],
        }
        for row in records
    ]
    with (HERE / "per_case_anonymized.jsonl").open("w", encoding="utf-8") as handle:
        for row in safe_records:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
