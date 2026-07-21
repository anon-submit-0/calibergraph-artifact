#!/usr/bin/env python3
"""Compiler arm (arm A of protocol.md) on the external_mf_metric_caliber layer.

Provenance / minimal-adaptation statement:
- calibergraph_contract_compiler.py in this directory is a BYTE-IDENTICAL copy of
  v24_group-B_evidence_fusion_submission_20260712/public_artifact/scripts/
  calibergraph_contract_compiler.py (sha256
  2404288f8a663d1de8454be65d993a911fdce6df004cbdfc64f4a7dc9b2385ee). No v24/v21 file was
  modified.
- This runner replaces v24's run_iowa_liquor_eval.py entry because that script is
  Iowa-specific (hard-coded dataset path, Iowa keyword boosts in rank_metrics, Iowa
  refusal keyword list, Iowa SQLite execution). The adaptation is minimal and label-free:
    * candidate metric linking, config "longest_alias" (primary): pick the catalog metric
      whose full name/alias phrase has the longest word-boundary match in the query;
      generic maximal-match entity linking, no per-dataset boosts;
    * candidate metric linking, config "iowa_text_score" (secondary, reported for
      transparency): the iowa text_score ranker verbatim minus its Iowa-specific boosts;
    * no SQL execution column: the third-party manifest ships no rows (schema_name is the
      `$source_schema` placeholder), so there is nothing to execute against;
    * scoring formulas (joint metric+dimension, refusal P/R) are copied unchanged from
      run_iowa_liquor_eval.py::score.
- Blind protocol: predictions read blind_cases.jsonl only (assert_blind enforced);
  gold_labels.jsonl is used exclusively for scoring afterwards.

Run:  python3 run_compiler_arm.py
Outputs: compiler_arm_results.json (summary) and
         external_mf_metric_caliber/results/compiler_arm_predictions.jsonl (per case).
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from calibergraph_contract_compiler import ContractCompiler

HERE = Path(__file__).resolve().parent
DATA = HERE / "external_mf_metric_caliber"
OUT = DATA / "results"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def assert_blind(case):
    leaked = sorted(key for key in case if key.startswith("expected_"))
    if leaked:
        raise AssertionError(f"blind case contains gold fields: {leaked}")


# ---------- linker config 1: longest word-boundary alias match (label-free) ----------
def word_match(needle, haystack):
    needle = re.sub(r"\s+", " ", str(needle).lower()).strip()
    haystack = re.sub(r"\s+", " ", str(haystack).lower()).strip()
    if not needle:
        return False
    return re.search(rf"(?<![a-z0-9_]){re.escape(needle)}(?![a-z0-9_])", haystack) is not None


def link_longest_alias(query, metrics):
    best = ("", -1, "")
    for metric_id, metric in metrics.items():
        phrases = [metric.get("metric_name", ""), metric_id.replace("_", " ")] + list(metric.get("aliases", []))
        for p in phrases:
            if word_match(p, query) and (len(p) > best[1] or (len(p) == best[1] and metric_id < best[0])):
                best = (metric_id, len(p), p)
    return best[0]


# ---------- linker config 2: iowa text_score ranker minus Iowa-specific boosts ----------
def norm(value):
    return "" if value is None else str(value).strip()


def split_terms(text):
    text = norm(text).lower()
    return set(re.findall(r"[a-z0-9_]+", text) + re.findall(r"[一-鿿]{2,}", text))


def char_bigrams(text):
    text = re.sub(r"\s+", "", norm(text).lower())
    return {text[i: i + 2] for i in range(max(0, len(text) - 1))}


def text_score(query, fields):
    q = norm(query).lower()
    q_terms = split_terms(q)
    q_bigrams = char_bigrams(q)
    score = 0.0
    for field, weight in fields:
        f = norm(field).lower()
        if not f:
            continue
        if f in q:
            score += 5.0 * weight
        f_terms = split_terms(f)
        score += weight * len(q_terms & f_terms)
        f_bigrams = char_bigrams(f)
        if f_bigrams:
            score += weight * len(q_bigrams & f_bigrams) / math.sqrt(len(f_bigrams))
    return score


def link_text_score(query, metrics):
    scored = []
    for metric_id, metric in metrics.items():
        fields = [
            (metric.get("metric_id"), 2.5),
            (metric.get("metric_name"), 3.0),
            (metric.get("formula"), 1.0),
            (metric.get("description"), 1.0),
            *[(alias, 2.5) for alias in metric.get("aliases", [])],
        ]
        scored.append((text_score(query, fields), metric_id))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return scored[0][1] if scored and scored[0][0] > 0 else ""


# ---------- scoring: copied unchanged from run_iowa_liquor_eval.py::score ----------
def score(rows, gold_by_id):
    summary = {}
    for mode in sorted({r["mode"] for r in rows}):
        subset = [r for r in rows if r["mode"] == mode]
        counts = Counter()
        for row in subset:
            gold = gold_by_id[row["case_id"]]
            expected_refusal = gold["expected_action"] == "refuse"
            refused = row["action"] == "refuse" or not row["pred_metric_id"]
            metric_ok = row["pred_metric_id"] == gold["expected_metric_id"]
            dim_ok = set(row["pred_dimensions"]) == set(gold["expected_dimensions"])
            if metric_ok:
                counts["metric_ok"] += 1
            if dim_ok:
                counts["dimension_exact_ok"] += 1
            if metric_ok and dim_ok:
                counts["joint_ok"] += 1
            if refused and expected_refusal:
                counts["refusal_tp"] += 1
            if refused and not expected_refusal:
                counts["refusal_fp"] += 1
            if (not refused) and expected_refusal:
                counts["refusal_fn"] += 1
            row["metric_ok"] = metric_ok
            row["dimension_exact_ok"] = dim_ok
            row["joint_ok"] = metric_ok and dim_ok
        n = len(subset)
        summary[mode] = {
            "n": n,
            "metric_accuracy": counts["metric_ok"] / n,
            "dimension_exact_accuracy": counts["dimension_exact_ok"] / n,
            "joint_metric_dimension_accuracy": counts["joint_ok"] / n,
            "refusal_precision": counts["refusal_tp"] / max(1, counts["refusal_tp"] + counts["refusal_fp"]),
            "refusal_recall": counts["refusal_tp"] / max(1, counts["refusal_tp"] + counts["refusal_fn"]),
        }
    return summary


def per_stratum(rows, gold_by_id, strata_of):
    out = {}
    for mode in sorted({r["mode"] for r in rows}):
        subset = [r for r in rows if r["mode"] == mode]
        by = {}
        for row in subset:
            by.setdefault(strata_of[row["case_id"]], []).append(row)
        out[mode] = {}
        for stratum, srows in sorted(by.items()):
            n = len(srows)
            out[mode][stratum] = {
                "n": n,
                "joint_metric_dimension_accuracy": sum(r["joint_ok"] for r in srows) / n,
                "metric_accuracy": sum(r["metric_ok"] for r in srows) / n,
                "dimension_exact_accuracy": sum(r["dimension_exact_ok"] for r in srows) / n,
            }
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    metrics = {m["metric_id"]: m for m in read_jsonl(DATA / "metric_catalog.jsonl")}
    cases = read_jsonl(DATA / "blind_cases.jsonl")
    gold = read_jsonl(DATA / "gold_labels.jsonl")
    gold_by_id = {g["case_id"]: g for g in gold}
    audit = json.loads((DATA / "generation_audit.json").read_text(encoding="utf-8"))
    strata_of = {cid: s for s, ids in audit["strata_case_ids"].items() for cid in ids}
    compiler = ContractCompiler(DATA)

    rows = []
    for mode, linker in (
        ("caliber_graph_longest_alias", link_longest_alias),
        ("caliber_graph_iowa_text_score", link_text_score),
    ):
        for case in cases:
            assert_blind(case)
            q = case["nl_query"]
            metric_id = linker(q, metrics)
            plan = compiler.compile(q, metric_id, candidate_metrics=[metric_id] if metric_id else [])
            rows.append(
                {
                    "mode": mode,
                    "case_id": case["case_id"],
                    "nl_query": q,
                    "linked_metric_id": metric_id,
                    "action": plan["action"],
                    "pred_metric_id": plan["pred_metric_id"],
                    "pred_dimensions": plan["pred_dimensions"],
                    "reason": plan["reason"],
                    "trace_primary_failure": (plan["trace"]["certificate"] or {}).get("primary_failure", ""),
                    "used_gold_label": plan["trace"]["used_gold_label"],
                }
            )
    summary = score(rows, gold_by_id)
    strata = per_stratum(rows, gold_by_id, strata_of)

    (OUT / "compiler_arm_predictions.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n", encoding="utf-8")
    payload = {
        "dataset_id": "external_mf_metric_caliber",
        "arm": "A_compiler (protocol.md pre-registered)",
        "compiler_sha256": "2404288f8a663d1de8454be65d993a911fdce6df004cbdfc64f4a7dc9b2385ee",
        "n_cases": len(cases),
        "plan": summary,
        "per_stratum": strata,
        "blind_protocol": {
            "prediction_input": "blind_cases.jsonl",
            "scoring_input": "gold_labels.jsonl",
            "gold_field_leaks_in_predictions": sum(any(k.startswith("expected_") for k in r) for r in rows),
            "used_gold_label_flags": sum(r["used_gold_label"] for r in rows),
        },
        "repro": [
            "python3 convert_mf_manifest.py",
            "python3 generate_cases.py",
            "python3 run_compiler_arm.py",
        ],
    }
    (HERE / "compiler_arm_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"plan": summary, "per_stratum": strata}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
