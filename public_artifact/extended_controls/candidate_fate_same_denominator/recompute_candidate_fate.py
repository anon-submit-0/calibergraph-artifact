#!/usr/bin/env python3
"""Re-score the released ICT candidate-budget arms on one denominator.

This is a post-hoc mechanism diagnostic. Gold is used only to select the 149
released answerable cases and to score the stored final predictions. No model
or retrieval call is issued.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parents[1]
BUDGET = HERE.parent / "candidate_budget_sensitivity"
ICT = PUBLIC / "public_benchmark" / "industrial_case_text_metric_caliber"
K_VALUES = (1, 3, 5, 10)


def read_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def final_round(record):
    usable = [
        round_record
        for round_record in record.get("rounds", [])
        if round_record.get("prediction") is not None
    ]
    if not usable:
        return {
            "prediction": {
                "action": "answer",
                "pred_metric_id": "__missing__",
                "pred_dimensions": [],
                "parse_status": "missing",
            },
            "validator_verdict": {"pass": False, "violations": []},
        }
    return usable[-1]


def primary_joint_correct(prediction, gold):
    """Mirror the released primary action/metric/dimension scorer."""
    return bool(
        prediction.get("action") == "answer"
        and prediction.get("pred_metric_id") == gold["expected_metric_id"]
        and set(prediction.get("pred_dimensions") or [])
        == set(gold["expected_dimensions"])
    )


def main():
    gold_path = ICT / "gold_labels.jsonl"
    blind_path = ICT / "blind_cases.jsonl"
    metric_path = ICT / "metric_catalog.jsonl"
    gold_rows = read_jsonl(gold_path)
    blind_rows = read_jsonl(blind_path)
    metric_ids = {row["metric_id"] for row in read_jsonl(metric_path)}
    gold_by_id = {row["case_id"]: row for row in gold_rows}
    if len(gold_by_id) != len(gold_rows):
        raise AssertionError("duplicate ICT gold case ids")

    answerable_ids = [
        row["case_id"] for row in gold_rows if row["expected_action"] == "answer"
    ]
    if len(answerable_ids) != 149:
        raise AssertionError(f"expected 149 answerable cases, found {len(answerable_ids)}")

    per_case = []
    arms = {}
    blind_ids = {row["case_id"] for row in blind_rows}
    if blind_ids != set(gold_by_id):
        raise AssertionError("ICT blind/gold case-id sets differ")
    input_hashes = {
        str(gold_path.relative_to(PUBLIC)): sha256(gold_path),
        str(blind_path.relative_to(PUBLIC)): sha256(blind_path),
        str(metric_path.relative_to(PUBLIC)): sha256(metric_path),
    }
    for k in K_VALUES:
        raw_path = BUDGET / "raw_responses" / f"k_{k}.jsonl"
        records_list = read_jsonl(raw_path)
        records = {row["case_id"]: row for row in records_list}
        if len(records) != len(records_list):
            raise AssertionError(f"duplicate records in k={k}")
        if len(records) != 157:
            raise AssertionError(f"k={k}: expected 157 records, found {len(records)}")
        if set(records) != blind_ids:
            raise AssertionError(f"k={k}: raw/blind case-id sets differ")
        input_hashes[str(raw_path.relative_to(PUBLIC))] = sha256(raw_path)

        counts = Counter()
        strict_counts = Counter()
        cross_tab = Counter()
        for case_id in answerable_ids:
            record = records[case_id]
            gold = gold_by_id[case_id]
            retrieved_ids = record.get("retrieved_metric_ids") or []
            if len(retrieved_ids) > k or len(retrieved_ids) != len(set(retrieved_ids)):
                raise AssertionError(f"k={k}/{case_id}: malformed retrieved ids")
            if not set(retrieved_ids).issubset(metric_ids):
                raise AssertionError(f"k={k}/{case_id}: unknown retrieved metric id")
            for round_record in record.get("rounds", []):
                if round_record.get("error") is not None:
                    raise AssertionError(f"k={k}/{case_id}: stored API error")
            selected_round = final_round(record)
            prediction = selected_round["prediction"]
            validator_pass = bool(
                (selected_round.get("validator_verdict") or {}).get("pass")
            )
            candidate_present = gold["expected_metric_id"] in set(
                retrieved_ids
            )
            joint_correct = primary_joint_correct(prediction, gold)
            md_plus_validator_correct = joint_correct and validator_pass
            cross_tab[(candidate_present, joint_correct)] += 1
            if not candidate_present:
                fate = "candidate_missing"
            elif joint_correct:
                fate = "candidate_present_joint_correct"
            else:
                fate = "candidate_present_final_wrong"
            counts[fate] += 1
            if not candidate_present:
                strict_fate = "candidate_missing"
            elif md_plus_validator_correct:
                strict_fate = "candidate_present_md_correct_validator_pass"
            else:
                strict_fate = "candidate_present_final_error"
            strict_counts[strict_fate] += 1
            per_case.append(
                {
                    "k": k,
                    "case_id": case_id,
                    "candidate_present": candidate_present,
                    "primary_joint_correct": joint_correct,
                    "final_validator_pass": validator_pass,
                    "md_plus_validator_correct": md_plus_validator_correct,
                    "fate": fate,
                    "strict_fate": strict_fate,
                    "expected_metric_id": gold["expected_metric_id"],
                    "expected_dimensions": gold["expected_dimensions"],
                    "retrieved_metric_ids": retrieved_ids,
                    "final_action": prediction.get("action"),
                    "final_metric_id": prediction.get("pred_metric_id"),
                    "final_dimensions": prediction.get("pred_dimensions") or [],
                }
            )

        if sum(counts.values()) != 149:
            raise AssertionError(f"k={k}: fate counts do not sum to 149")
        if sum(strict_counts.values()) != 149:
            raise AssertionError(f"k={k}: strict fate counts do not sum to 149")
        arms[str(k)] = {
            "n_answerable": 149,
            "counts": dict(sorted(counts.items())),
            "rates": {
                key: value / 149 for key, value in sorted(counts.items())
            },
            "candidate_presence_x_joint_correct": {
                f"candidate_{'present' if present else 'missing'}__joint_{'correct' if correct else 'wrong'}": value
                for (present, correct), value in sorted(cross_tab.items())
            },
            "md_plus_final_validator_partition": {
                "counts": dict(sorted(strict_counts.items())),
                "rates": {
                    key: value / 149
                    for key, value in sorted(strict_counts.items())
                },
            },
        }

    output_jsonl = HERE / "per_case_candidate_fate.jsonl"
    output_jsonl.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in per_case
        ),
        encoding="utf-8",
    )
    report = {
        "experiment_id": "ict-candidate-fate-same-denominator",
        "status": "deterministic post-hoc diagnostic over released raw responses",
        "new_model_calls": 0,
        "denominator": {
            "definition": "released IndustrialCaseText cases with expected_action=answer",
            "n": 149,
        },
        "primary_outcome": (
            "action=answer and exact expected metric id and exact expected dimension set; "
            "this mirrors the released primary joint scorer and does not add time/caliber "
            "fields to the headline outcome"
        ),
        "figure_outcome": (
            "candidate present, exact action/metric/dimension, and pass by the stored "
            "final released validator; this remains a governed proxy because the LLM "
            "record does not predict every gold caliber/policy slot"
        ),
        "fate_precedence": (
            "candidate_missing is assigned first; candidate-present cases then split by "
            "the released primary joint outcome"
        ),
        "arms": arms,
        "input_sha256": dict(sorted(input_hashes.items())),
        "per_case_file": output_jsonl.name,
        "invariants": {
            "answerable_cases": 149,
            "records_per_arm": 157,
            "per_case_rows": len(per_case),
            "expected_per_case_rows": 149 * len(K_VALUES),
        },
    }
    (HERE / "candidate_fate_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
