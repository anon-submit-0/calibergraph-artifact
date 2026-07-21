#!/usr/bin/env python3
"""Extend the validator-replan control from 200 to all 510 MultiGov cases."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "validator_feedback_replanning"
SPEC = importlib.util.spec_from_file_location("release_replan", PARENT / "run_loop.py")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

RAW = HERE / "raw_responses" / "multigov_full_loop_raw.jsonl"
SOURCE_200 = PARENT / "raw_responses" / "multigov_loop_raw.jsonl"
SEED = 20260711
BOOTSTRAPS = 10_000


def all_cases(ctx):
    rows = base.read_jsonl(ctx.cfg["dir"] / "blind_cases.jsonl")
    for row in rows:
        base.assert_blind(row)
    if len(rows) != 510 or len({row["case_id"] for row in rows}) != 510:
        raise SystemExit("MultiGov full-case universe drift")
    return rows


def initialize():
    if RAW.exists():
        print("full raw file already exists; initialization skipped")
        return
    source = base.read_jsonl(SOURCE_200)
    if len(source) != 200 or len({row["case_id"] for row in source}) != 200:
        raise SystemExit("source 200 response histories are incomplete or duplicated")
    with RAW.open("w", encoding="utf-8") as handle:
        for row in source:
            row = {**row, "full_extension_provenance": "preregistered_stratified_200"}
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"initialized {RAW.name} with {len(source)} inherited records")


def audit():
    ctx = base.LayerContext("multigov")
    cases = all_cases(ctx)
    gold = ctx.load_gold()
    flagged = []
    trigger_mismatches = []
    for case in cases:
        g = gold[case["case_id"]]
        violations = base.validate(ctx, base.gold_as_prediction(g), case["nl_query"])
        if violations:
            flagged.append({"case_id": case["case_id"], "violations": violations})
        if bool(ctx.policy_hits(case["nl_query"])) != (g["expected_action"] == "refuse"):
            trigger_mismatches.append(case["case_id"])
    report = {
        "n": len(cases),
        "gold_plans_flagged": flagged,
        "trigger_vs_gold_mismatches": trigger_mismatches,
        "pass": not flagged and not trigger_mismatches,
    }
    (HERE / "full_validator_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def run():
    initialize()
    base.load_env()
    api_key = base.os.environ["LLM_API_KEY"]
    ctx = base.LayerContext("multigov")
    cases = all_cases(ctx)
    records = {row["case_id"]: row for row in base.read_jsonl(RAW)}
    todo = [case for case in cases if case["case_id"] not in records]
    print(f"[multigov-full] cases=510 done={len(records)} todo={len(todo)}", flush=True)
    if not todo:
        return
    write_lock = threading.Lock()
    completed = 0
    with RAW.open("a", encoding="utf-8") as handle:
        with ThreadPoolExecutor(max_workers=base.CONCURRENCY) as pool:
            futures = {pool.submit(base.run_case_loop, ctx, case, api_key): case["case_id"] for case in todo}
            for future in as_completed(futures):
                row = {**future.result(), "full_extension_provenance": "exhaustive_extension_remaining_310"}
                with write_lock:
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    handle.flush()
                completed += 1
                if completed % 10 == 0 or completed == len(todo):
                    print(f"[multigov-full] {completed}/{len(todo)}", flush=True)


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


def exact_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / (2**n))


def percentile(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, max(0, int(q * (len(values) - 1))))]


def cluster_ci(rows):
    clusters = defaultdict(list)
    for row in rows:
        group = f"metric_group_{(int(row['case_id'].rsplit('_', 1)[1]) - 1) // 3:04d}"
        clusters[group].append(row)
    keys = sorted(clusters)
    rng = random.Random(SEED)
    diffs = []
    for _ in range(BOOTSTRAPS):
        sampled = [rng.choice(keys) for _ in keys]
        batch = [row for key in sampled for row in clusters[key]]
        diffs.append(sum(row["compiler"] - row["replan"] for row in batch) / len(batch))
    return [percentile(diffs, 0.025), percentile(diffs, 0.975)], len(keys)


def score():
    ctx = base.LayerContext("multigov")
    cases = all_cases(ctx)
    gold = ctx.load_gold()
    recs = {row["case_id"]: row for row in base.read_jsonl(RAW)}
    missing = [case["case_id"] for case in cases if case["case_id"] not in recs]
    if missing:
        raise SystemExit(f"cannot score; missing {len(missing)} cases")
    per_round = {}
    final_rows = []
    for round_id in range(base.MAX_REPAIR_ROUNDS + 1):
        rows = []
        for case in cases:
            state = base.state_at_round(recs[case["case_id"]]["rounds"], round_id)
            pred = state["prediction"] if state else base.normalize_prediction(None, "missing")
            g = gold[case["case_id"]]
            rows.append(
                {
                    "case_id": case["case_id"],
                    "query_family": g.get("query_family", ""),
                    "expected_action": g["expected_action"],
                    "expected_metric_id": g["expected_metric_id"],
                    "expected_dimensions": g["expected_dimensions"],
                    **pred,
                }
            )
        per_round[f"round_{round_id}"] = base.score_rows([dict(row) for row in rows])
        if round_id == base.MAX_REPAIR_ROUNDS:
            final_rows = rows
    final_by_id = {row["case_id"]: row for row in final_rows}
    compiler_rows = {
        row["case_id"]: row
        for row in base.read_jsonl(ctx.cfg["dir"] / "results" / "multigov_predictions.jsonl")
        if row["mode"] == "caliber_graph"
    }
    paired = []
    invisible = []
    violations = Counter()
    prompt_tokens = completion_tokens = calls = 0
    for case in cases:
        case_id = case["case_id"]
        rec = recs[case_id]
        calls += rec["n_llm_calls"]
        for rd in rec["rounds"]:
            usage = rd.get("usage") or {}
            prompt_tokens += usage.get("prompt_tokens", 0)
            completion_tokens += usage.get("completion_tokens", 0)
        last = rec["rounds"][-1]
        current_violations = base.validate(ctx, last["prediction"], case["nl_query"])
        violations.update(item["type"] for item in current_violations)
        final_ok = correct(final_by_id[case_id], gold[case_id])
        round0_state = base.state_at_round(rec["rounds"], 0)
        round0_ok = correct(round0_state["prediction"], gold[case_id])
        compiler_ok = correct(compiler_rows[case_id], gold[case_id])
        if not current_violations and not final_ok:
            invisible.append(case_id)
        paired.append(
            {
                "case_id": case_id,
                "round0": int(round0_ok),
                "compiler": int(compiler_ok),
                "replan": int(final_ok),
            }
        )
    b = sum(row["compiler"] and not row["replan"] for row in paired)
    c = sum(row["replan"] and not row["compiler"] for row in paired)
    ci, n_clusters = cluster_ci(paired)
    result = {
        "n": len(cases),
        "inherited_response_histories": 200,
        "new_response_histories": 310,
        "per_round": per_round,
        "compiler_accuracy": sum(row["compiler"] for row in paired) / len(paired),
        "replan_final_accuracy": sum(row["replan"] for row in paired) / len(paired),
        "paired_difference_compiler_minus_replan": sum(row["compiler"] - row["replan"] for row in paired) / len(paired),
        "difference_cluster_ci95": ci,
        "cluster_count": n_clusters,
        "mcnemar_compiler_only": b,
        "mcnemar_replan_only": c,
        "mcnemar_exact_two_sided_p": exact_p(b, c),
        "round0_wrong_to_final_right": sum(
            not row["round0"] and row["replan"] for row in paired
        ),
        "round0_right_to_final_wrong": sum(
            row["round0"] and not row["replan"] for row in paired
        ),
        "llm_calls_total": calls,
        "llm_calls_per_case_mean": calls / len(cases),
        "prompt_tokens_total": prompt_tokens,
        "completion_tokens_total": completion_tokens,
        "final_validator_violations": dict(violations),
        "validator_invisible_final_error_count": len(invisible),
        "validator_invisible_case_ids": invisible,
    }
    (HERE / "multigov_full_scores.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["initialize", "audit", "run", "score"])
    args = parser.parse_args()
    {"initialize": initialize, "audit": audit, "run": run, "score": score}[args.cmd]()


if __name__ == "__main__":
    main()
