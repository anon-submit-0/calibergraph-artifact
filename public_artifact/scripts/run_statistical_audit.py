#!/usr/bin/env python3
"""Paired and cluster-bootstrap tests for the three headline public datasets."""

from __future__ import annotations

import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "public_benchmark"
OUT = ROOT / "experiments"
SEED = 20260711
BOOTSTRAPS = 10000


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized_query(text):
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def correct(pred, gold):
    expected_refuse = gold["expected_action"] == "refuse"
    predicted_refuse = pred.get("action") == "refuse" or pred.get("pred_action") == "refuse" or not pred.get("pred_metric_id")
    if expected_refuse:
        return predicted_refuse
    return (
        not predicted_refuse
        and pred.get("pred_metric_id") == gold.get("expected_metric_id")
        and set(pred.get("pred_dimensions", [])) == set(gold.get("expected_dimensions", []))
    )


def exact_mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def percentile(values, q):
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(q * (len(ordered) - 1))))
    return ordered[index]


def cluster_bootstrap(records):
    clusters = defaultdict(list)
    for row in records:
        clusters[row["cluster"]].append(row)
    keys = sorted(clusters)
    rng = random.Random(SEED)
    diffs = []
    for _ in range(BOOTSTRAPS):
        sampled = [rng.choice(keys) for _ in keys]
        rows = [row for key in sampled for row in clusters[key]]
        diffs.append(sum(row["new"] - row["base"] for row in rows) / len(rows))
    return {
        "cluster_count": len(keys),
        "bootstrap_replicates": BOOTSTRAPS,
        "difference_ci95": [percentile(diffs, 0.025), percentile(diffs, 0.975)],
    }


def evaluate_dataset(name, path, pred_file, gold_file, cluster_fn):
    predictions = read_jsonl(path / pred_file)
    gold_by_id = {row["case_id"]: row for row in read_jsonl(path / gold_file)}
    by_mode = defaultdict(dict)
    query_by_id = {}
    for row in predictions:
        by_mode[row["mode"]][row["case_id"]] = row
        query_by_id[row["case_id"]] = row.get("nl_query", "")
    records = []
    for case_id, gold in gold_by_id.items():
        base = by_mode["safenlidb_guarded"][case_id]
        new = by_mode["caliber_graph"][case_id]
        records.append(
            {
                "case_id": case_id,
                "cluster": cluster_fn(case_id, query_by_id.get(case_id, ""), gold),
                "base": int(correct(base, gold)),
                "new": int(correct(new, gold)),
            }
        )
    b = sum(row["new"] and not row["base"] for row in records)
    c = sum(row["base"] and not row["new"] for row in records)
    result = {
        "dataset": name,
        "n": len(records),
        "baseline": "safenlidb_guarded",
        "method": "caliber_graph",
        "baseline_full_case_accuracy": sum(row["base"] for row in records) / len(records),
        "method_full_case_accuracy": sum(row["new"] for row in records) / len(records),
        "paired_difference": sum(row["new"] - row["base"] for row in records) / len(records),
        "mcnemar_discordant_method_only": b,
        "mcnemar_discordant_baseline_only": c,
        "mcnemar_exact_two_sided_p": exact_mcnemar_p(b, c),
    }
    result.update(cluster_bootstrap(records))
    return result


def main():
    results = [
        evaluate_dataset(
            "IowaLiquor",
            BENCH / "iowa_liquor_metric_caliber",
            "results/iowa_liquor_predictions.jsonl",
            "gold_labels.jsonl",
            lambda case_id, query, gold: case_id,
        ),
        evaluate_dataset(
            "MultiGov",
            BENCH / "multigov_metric_caliber",
            "results/multigov_predictions.jsonl",
            "gold_labels.jsonl",
            lambda case_id, query, gold: f"metric_group_{(int(case_id.rsplit('_', 1)[1]) - 1) // 3:04d}",
        ),
        evaluate_dataset(
            "IndustrialCaseText",
            BENCH / "industrial_case_text_metric_caliber",
            "results/industrial_case_text_predictions.jsonl",
            "gold_labels.jsonl",
            lambda case_id, query, gold: normalized_query(query),
        ),
    ]
    payload = {
        "seed": SEED,
        "bootstrap_replicates": BOOTSTRAPS,
        "paired_metric": "action-aware full-case correctness",
        "results": results,
    }
    (OUT / "headline_statistical_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Headline Statistical Audit",
        "",
        "Paired exact McNemar tests compare CaliberGraph with the SafeNLIDB-derived E3 protocol. Confidence intervals use 10,000 deterministic cluster bootstrap replicates.",
        "",
        "| Dataset | N | Baseline | CaliberGraph | Difference | 95% cluster CI | Exact p |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for row in results:
        lo, hi = row["difference_ci95"]
        lines.append(
            f"| {row['dataset']} | {row['n']} | {row['baseline_full_case_accuracy']:.3f} | {row['method_full_case_accuracy']:.3f} | {row['paired_difference']:.3f} | [{lo:.3f}, {hi:.3f}] | {row['mcnemar_exact_two_sided_p']:.3g} |"
        )
    (OUT / "HEADLINE_STATISTICAL_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
