#!/usr/bin/env python3
"""Recompute correctness-only enterprise aggregate comparisons."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path


HERE = Path(__file__).resolve().parent
PAIRS = HERE / "anonymous_correctness_pairs.jsonl"
SEED = 20260711
REPLICATES = 10_000


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def exact_mcnemar(left_only, right_only):
    n = left_only + right_only
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(left_only, right_only) + 1))
    return min(1.0, 2.0 * tail * (0.5**n))


def bootstrap(reference, control):
    rng = random.Random(SEED)
    n = len(reference)
    values = []
    for _ in range(REPLICATES):
        indices = [rng.randrange(n) for _ in range(n)]
        values.append((sum(reference[i] for i in indices) - sum(control[i] for i in indices)) / n)
    values.sort()
    return [values[int(0.025 * REPLICATES)], values[min(REPLICATES - 1, int(0.975 * REPLICATES))]]


def compare(reference, control):
    both = sum(a and b for a, b in zip(reference, control))
    reference_only = sum(a and not b for a, b in zip(reference, control))
    control_only = sum((not a) and b for a, b in zip(reference, control))
    both_wrong = len(reference) - both - reference_only - control_only
    return {
        "accuracy_reference": sum(reference) / len(reference),
        "accuracy_control": sum(control) / len(control),
        "delta_reference_minus_control": (sum(reference) - sum(control)) / len(reference),
        "contingency": {
            "both_correct": both,
            "reference_only": reference_only,
            "control_only": control_only,
            "both_wrong": both_wrong,
        },
        "mcnemar_exact_two_sided_p": exact_mcnemar(reference_only, control_only),
        "paired_bootstrap_95ci": bootstrap(reference, control),
        "bootstrap_seed": SEED,
        "bootstrap_replicates": REPLICATES,
    }


def main():
    rows = read_jsonl(PAIRS)
    if len(rows) != 159 or len({row["anonymous_case_id"] for row in rows}) != 159:
        raise SystemExit("expected 159 unique anonymous pairs")
    reference = [bool(row["calibergraph_correct"]) for row in rows]
    fields = {
        "schema_rag_fresh": "schema_rag_fresh_correct",
        "instructed_execution": "instructed_execution_correct",
        "replan_round0": "replan_round0_correct",
        "replan_final": "replan_final_correct",
    }
    report = {
        "source": "anonymous correctness-only enterprise pairs; no query text, labels, or identifiers",
        "n": len(rows),
        "reference": {"name": "CaliberGraph", "accuracy": sum(reference) / len(reference)},
        "comparisons": {
            name: compare(reference, [bool(row[field]) for row in rows])
            for name, field in fields.items()
        },
        "interpretation_guard": (
            "The replan comparison is not statistically significant; do not claim predictive superiority."
        ),
    }
    (HERE / "aggregate_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
