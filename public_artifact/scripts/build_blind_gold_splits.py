#!/usr/bin/env python3
"""Materialize label-free prediction inputs and scorer-only gold files."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "public_benchmark"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def split_file(source, blind_path, gold_path):
    rows = read_jsonl(source)
    blind_rows = []
    gold_rows = []
    for row in rows:
        blind = {key: value for key, value in row.items() if not key.startswith("expected_")}
        gold = {"case_id": row["case_id"]}
        gold.update({key: value for key, value in row.items() if key.startswith("expected_")})
        for key in ("query_family", "severity", "source_case_id", "perturbation_type"):
            if key in row:
                gold[key] = row[key]
        blind_rows.append(blind)
        gold_rows.append(gold)
    leaked = sorted({key for row in blind_rows for key in row if key.startswith("expected_")})
    if leaked:
        raise AssertionError(f"gold fields leaked into {blind_path}: {leaked}")
    write_jsonl(blind_path, blind_rows)
    write_jsonl(gold_path, gold_rows)
    return len(rows)


def main():
    jobs = [
        (
            BENCH / "iowa_liquor_metric_caliber" / "test_cases.jsonl",
            BENCH / "iowa_liquor_metric_caliber" / "blind_cases.jsonl",
            BENCH / "iowa_liquor_metric_caliber" / "gold_labels.jsonl",
        ),
        (
            BENCH / "govtwin_metric_caliber" / "test_cases.jsonl",
            BENCH / "govtwin_metric_caliber" / "blind_cases.jsonl",
            BENCH / "govtwin_metric_caliber" / "gold_labels.jsonl",
        ),
        (
            BENCH / "govtwin_metric_caliber" / "test_cases_llm_paraphrased.jsonl",
            BENCH / "govtwin_metric_caliber" / "blind_cases_llm_paraphrased.jsonl",
            BENCH / "govtwin_metric_caliber" / "gold_labels_llm_paraphrased.jsonl",
        ),
    ]
    counts = {}
    for source, blind, gold in jobs:
        if source.exists():
            counts[source.name] = split_file(source, blind, gold)
    print(json.dumps({"split_counts": counts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
