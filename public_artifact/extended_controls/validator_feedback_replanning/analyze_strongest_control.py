#!/usr/bin/env python3
"""Paired, cluster-aware analysis of release validator-feedback replanning."""

from __future__ import annotations

import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
RELEASE = HERE.parents[2]
PB = RELEASE / "public_artifact" / "public_benchmark"
SEED = 20260711
BOOTSTRAPS = 10_000

LAYERS = {
    "iowa": {
        "dir": PB / "iowa_liquor_metric_caliber",
        "blind": "blind_cases.jsonl",
        "gold": "gold_labels.jsonl",
        "pred": "results/iowa_liquor_predictions.jsonl",
        "mode": "caliber_graph",
    },
    "govtwin": {
        "dir": PB / "govtwin_metric_caliber",
        "blind": "blind_cases.jsonl",
        "gold": "gold_labels.jsonl",
        "pred": "results/govtwin_predictions.jsonl",
        "mode": "caliber_graph",
    },
    "multigov": {
        "dir": PB / "multigov_metric_caliber",
        "blind": "blind_cases.jsonl",
        "gold": "gold_labels.jsonl",
        "pred": "results/multigov_predictions.jsonl",
        "mode": "caliber_graph",
    },
    "ict": {
        "dir": PB / "industrial_case_text_metric_caliber",
        "blind": "blind_cases.jsonl",
        "gold": "gold_labels.jsonl",
        "pred": "results/industrial_case_text_predictions.jsonl",
        "mode": "caliber_graph",
    },
}


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized_query(text):
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def correct(pred, gold):
    expected_refusal = gold["expected_action"] == "refuse"
    predicted_refusal = pred.get("action") == "refuse" or not pred.get("pred_metric_id")
    if expected_refusal:
        return predicted_refusal
    return (
        not predicted_refusal
        and pred.get("pred_metric_id") == gold["expected_metric_id"]
        and set(pred.get("pred_dimensions") or []) == set(gold["expected_dimensions"])
    )


def exact_mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(q * (len(ordered) - 1))))]


def cluster_id(layer, case_id, query):
    if layer == "multigov":
        return f"metric_group_{(int(case_id.rsplit('_', 1)[1]) - 1) // 3:04d}"
    if layer == "ict":
        return normalized_query(query)
    return case_id


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
        diffs.append(sum(row["compiler"] - row["replan"] for row in rows) / len(rows))
    return {
        "cluster_count": len(keys),
        "difference_ci95": [percentile(diffs, 0.025), percentile(diffs, 0.975)],
    }


def main():
    flattened = read_jsonl(HERE / "per_case_rounds.jsonl")
    final = {}
    for row in flattened:
        key = (row["layer"], row["case_id"])
        if key not in final or row["round"] > final[key]["round"]:
            final[key] = row
    score_report = json.loads((HERE / "scores.json").read_text(encoding="utf-8"))
    output = {
        "paired_metric": "action-aware full-case correctness",
        "bootstrap_seed": SEED,
        "bootstrap_replicates": BOOTSTRAPS,
        "layers": {},
    }
    for layer, cfg in LAYERS.items():
        gold = {row["case_id"]: row for row in read_jsonl(cfg["dir"] / cfg["gold"])}
        blind = {row["case_id"]: row for row in read_jsonl(cfg["dir"] / cfg["blind"])}
        compiler = {
            row["case_id"]: row
            for row in read_jsonl(cfg["dir"] / cfg["pred"])
            if row["mode"] == cfg["mode"]
        }
        case_ids = sorted(case_id for row_layer, case_id in final if row_layer == layer)
        records = []
        for case_id in case_ids:
            replan_pred = final[(layer, case_id)]["prediction"]
            records.append(
                {
                    "case_id": case_id,
                    "cluster": cluster_id(layer, case_id, blind[case_id]["nl_query"]),
                    "compiler": int(correct(compiler[case_id], gold[case_id])),
                    "replan": int(correct(replan_pred, gold[case_id])),
                }
            )
        compiler_only = sum(row["compiler"] and not row["replan"] for row in records)
        replan_only = sum(row["replan"] and not row["compiler"] for row in records)
        result = {
            "n": len(records),
            "compiler_accuracy": sum(row["compiler"] for row in records) / len(records),
            "replan_round0_accuracy": score_report[layer]["per_round"]["round_0"]["joint_metric_dimension_accuracy"],
            "replan_final_accuracy": sum(row["replan"] for row in records) / len(records),
            "paired_difference_compiler_minus_replan": sum(row["compiler"] - row["replan"] for row in records) / len(records),
            "mcnemar_compiler_only": compiler_only,
            "mcnemar_replan_only": replan_only,
            "mcnemar_exact_two_sided_p": exact_mcnemar_p(compiler_only, replan_only),
            "llm_calls_total": score_report[layer]["cost"]["llm_calls_total"],
            "llm_calls_per_case_mean": score_report[layer]["cost"]["llm_calls_per_case_mean"],
            "prompt_tokens_total": score_report[layer]["cost"]["total_prompt_tokens"],
            "validator_invisible_final_errors": score_report[layer]["validator_invisible_errors_final"],
        }
        result.update(cluster_bootstrap(records))
        output["layers"][layer] = result
    output["pooled"] = score_report["_pooled"]
    (HERE / "strongest_control_analysis.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# release Public Strongest-Control Analysis",
        "",
        "Validator-feedback replanning is a complete runnable baseline, not an ablation. Intervals use deterministic cluster bootstrap; p-values use exact paired McNemar tests.",
        "",
        "| Layer | N | Round 0 | Replan final | Compiler | Delta | 95% cluster CI | Exact p | Calls/case |",
        "|---|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for layer, row in output["layers"].items():
        lines.append(
            f"| {layer} | {row['n']} | {row['replan_round0_accuracy']:.3f} | {row['replan_final_accuracy']:.3f} | "
            f"{row['compiler_accuracy']:.3f} | {row['paired_difference_compiler_minus_replan']:.3f} | "
            f"[{row['difference_ci95'][0]:.3f}, {row['difference_ci95'][1]:.3f}] | "
            f"{row['mcnemar_exact_two_sided_p']:.3g} | {row['llm_calls_per_case_mean']:.3f} |"
        )
    (HERE / "STRONGEST_CONTROL_ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
