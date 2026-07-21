#!/usr/bin/env python3
"""P1b alias-only deterministic control (rapidfuzz_alias_top1).

Pre-registered protocol: protocol.md (FROZEN, sha256 1e5cddd750ce9b8dcb01b46da
e3293f8255faef502cb3d274ba205521a362f04). Zero LLM calls; pure local rapidfuzz.

Family (1) "has-mechanism" control: alias disambiguation WITHOUT any caliber
witness / governance-graph constraint / policy check. Scoring replicates the
score_rows semantics shared by run_govtwin_eval.py /
run_multigov_metric_caliber_eval.py / run_iowa_liquor_eval.py in the v24
public artifact.
"""

import hashlib
import json
import platform
from collections import Counter
from pathlib import Path

import rapidfuzz
from rapidfuzz import fuzz, utils

BENCH_ROOT = Path(
    "<REPO_ROOT>/releases/"
    "v24_group-B_evidence_fusion_submission_20260712/public_artifact/public_benchmark"
)
OUT_DIR = Path(
    "<REPO_ROOT>/releases/"
    "v28cc_20260714/alias_control"
)

MODE = "rapidfuzz_alias_top1"
THETA_METRIC = 60.0   # frozen in protocol.md section 1.3
THETA_DIM = 85.0      # frozen in protocol.md section 1.4

LAYERS = {
    "govtwin": "govtwin_metric_caliber",
    "multigov": "multigov_metric_caliber",
    "iowa": "iowa_liquor_metric_caliber",
}


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sha256(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def score_text(query, alias):
    return fuzz.token_set_ratio(query, alias, processor=utils.default_process)


def best_metric(query, metrics):
    """Top-1 metric by max-over-aliases token_set_ratio.

    Tie-break (deterministic, frozen): higher score -> longer normalized
    matched alias -> lexicographically smallest metric_id.
    """
    best = None  # (score, alias_norm_len, neg_id_rank) via explicit compare
    for m in sorted(metrics, key=lambda x: x["metric_id"]):
        for alias in m.get("aliases", []):
            s = score_text(query, alias)
            alias_norm_len = len(utils.default_process(alias))
            cand = {
                "metric_id": m["metric_id"],
                "score": s,
                "alias": alias,
                "alias_norm_len": alias_norm_len,
            }
            if best is None:
                best = cand
                continue
            if s > best["score"]:
                best = cand
            elif s == best["score"]:
                if alias_norm_len > best["alias_norm_len"]:
                    best = cand
                elif (
                    alias_norm_len == best["alias_norm_len"]
                    and cand["metric_id"] < best["metric_id"]
                ):
                    best = cand
    return best


def matched_dimensions(query, dims):
    """All dimensions whose max-over-aliases score >= THETA_DIM."""
    hits = []
    for d in sorted(dims, key=lambda x: x["dimension_id"]):
        best_s, best_alias = -1.0, ""
        for alias in d.get("aliases", []):
            s = score_text(query, alias)
            if s > best_s:
                best_s, best_alias = s, alias
        if best_s >= THETA_DIM:
            hits.append(
                {
                    "dimension_id": d["dimension_id"],
                    "score": best_s,
                    "alias": best_alias,
                }
            )
    return hits


def predict_layer(layer_dir):
    blind = read_jsonl(layer_dir / "blind_cases.jsonl")
    metrics = read_jsonl(layer_dir / "metric_catalog.jsonl")
    dims = read_jsonl(layer_dir / "dimension_catalog.jsonl")
    rows = []
    for case in blind:
        q = case["nl_query"]
        top = best_metric(q, metrics)
        if top is None or top["score"] < THETA_METRIC:
            action, pred_metric, metric_score, metric_alias = "refuse", "", (
                top["score"] if top else 0.0
            ), ""
        else:
            action, pred_metric = "answer", top["metric_id"]
            metric_score, metric_alias = top["score"], top["alias"]
        dim_hits = matched_dimensions(q, dims)
        row = {
            "case_id": case["case_id"],
            "nl_query": q,
            "mode": MODE,
            "action": action,
            "pred_metric_id": pred_metric,
            "pred_dimensions": [h["dimension_id"] for h in dim_hits],
            "metric_match_score": metric_score,
            "metric_match_alias": metric_alias,
            "dimension_match_detail": dim_hits,
            "reason": "rapidfuzz_token_set_ratio_alias_only_no_witness",
        }
        if "query_family" in case:
            row["query_family"] = case["query_family"]
        rows.append(row)
    return rows


def score_rows(rows, gold_by_id):
    """Same-caliber scoring as v24 artifact eval scripts."""
    counts = Counter()
    for row in rows:
        gold = gold_by_id[row["case_id"]]
        expected_refusal = gold["expected_action"] == "refuse"
        refused = row["action"] == "refuse" or not row["pred_metric_id"]
        metric_ok = row["pred_metric_id"] == gold["expected_metric_id"]
        dim_ok = set(row["pred_dimensions"]) == set(gold["expected_dimensions"])
        dim_recall = set(gold["expected_dimensions"]).issubset(
            set(row["pred_dimensions"])
        )
        counts["metric_ok"] += int(metric_ok)
        counts["dimension_exact_ok"] += int(dim_ok)
        counts["dimension_recall_ok"] += int(dim_recall)
        counts["joint_ok"] += int(metric_ok and dim_ok)
        counts["refusal_tp"] += int(refused and expected_refusal)
        counts["refusal_fp"] += int(refused and not expected_refusal)
        counts["refusal_fn"] += int((not refused) and expected_refusal)
        row["metric_ok"] = metric_ok
        row["dimension_exact_ok"] = dim_ok
        row["dimension_recall_ok"] = dim_recall
        row["joint_ok"] = metric_ok and dim_ok
    n = len(rows)
    return {
        "n": n,
        "metric_accuracy": counts["metric_ok"] / n,
        "dimension_exact_accuracy": counts["dimension_exact_ok"] / n,
        "dimension_recall_accuracy": counts["dimension_recall_ok"] / n,
        "joint_metric_dimension_accuracy": counts["joint_ok"] / n,
        "refusal_precision": counts["refusal_tp"]
        / max(1, counts["refusal_tp"] + counts["refusal_fp"]),
        "refusal_recall": counts["refusal_tp"]
        / max(1, counts["refusal_tp"] + counts["refusal_fn"]),
        "refusal_tp": counts["refusal_tp"],
        "refusal_fp": counts["refusal_fp"],
        "refusal_fn": counts["refusal_fn"],
    }


def main():
    results = {
        "mode": MODE,
        "protocol_sha256": sha256(OUT_DIR / "protocol.md"),
        "rapidfuzz_version": rapidfuzz.__version__,
        "python_version": platform.python_version(),
        "scorer": "fuzz.token_set_ratio + utils.default_process",
        "theta_metric": THETA_METRIC,
        "theta_dim": THETA_DIM,
        "llm_calls": 0,
        "blind_protocol": {
            "prediction_input": "blind_cases.jsonl",
            "scoring_input": "gold_labels.jsonl",
            "gold_fields_read_at_prediction_time": [],
        },
        "input_sha256": {},
        "layers": {},
    }
    for layer, sub in LAYERS.items():
        layer_dir = BENCH_ROOT / sub
        for fn in ("blind_cases.jsonl", "gold_labels.jsonl",
                   "metric_catalog.jsonl", "dimension_catalog.jsonl"):
            results["input_sha256"][f"{layer}/{fn}"] = sha256(layer_dir / fn)

        rows = predict_layer(layer_dir)  # prediction: blind + catalogs only
        gold = read_jsonl(layer_dir / "gold_labels.jsonl")  # scoring phase
        gold_by_id = {g["case_id"]: g for g in gold}
        assert set(gold_by_id) == {r["case_id"] for r in rows}

        overall = score_rows(rows, gold_by_id)
        fam_summary = {}
        families = sorted({r.get("query_family", "") for r in rows} - {""})
        for fam in families:
            subset = [r for r in rows if r.get("query_family") == fam]
            fam_summary[fam] = score_rows(subset, gold_by_id)
        results["layers"][layer] = {
            "overall": overall,
            "family_breakdown": fam_summary,
        }

        pred_path = OUT_DIR / f"predictions_{layer}.jsonl"
        with open(pred_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        # blind-protocol audit: no gold field names may appear in predictions
        leak = sum(
            1 for r in rows for k in r if k.startswith("expected_")
        )
        results["layers"][layer]["gold_field_leaks_in_predictions"] = leak
        print(f"[{layer}] n={overall['n']} "
              f"metric={overall['metric_accuracy']:.3f} "
              f"dim_exact={overall['dimension_exact_accuracy']:.3f} "
              f"joint={overall['joint_metric_dimension_accuracy']:.3f} "
              f"refP={overall['refusal_precision']:.3f} "
              f"refR={overall['refusal_recall']:.3f}")

    with open(OUT_DIR / "scores.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, sort_keys=True)
    print("scores.json written")


if __name__ == "__main__":
    main()
