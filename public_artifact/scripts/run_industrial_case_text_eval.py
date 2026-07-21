#!/usr/bin/env python3
"""Evaluate public IndustrialCaseText-MetricCaliber artifacts."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from calibergraph_contract_compiler import ContractCompiler


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public_benchmark" / "industrial_case_text_metric_caliber"
OUT = DATA / "results"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def assert_blind(case):
    leaked = [k for k in case if k.startswith("expected_") or k.endswith("_hash")]
    if leaked:
        raise AssertionError(f"blind case leaks gold/private fields: {leaked}")


def normalized_query(text):
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def split_terms(text):
    text = str(text or "").lower()
    return set(re.findall(r"[a-z0-9_]+", text) + re.findall(r"[\u4e00-\u9fff]{2,}", text))


def score_text(query, fields):
    q = str(query or "").lower()
    q_terms = split_terms(q)
    q_bigrams = {q[i : i + 2] for i in range(max(0, len(q) - 1))}
    score = 0.0
    for field, weight in fields:
        f = str(field or "").lower()
        if not f:
            continue
        if f in q:
            score += 4.0 * weight
        f_terms = split_terms(f)
        score += len(q_terms & f_terms) * weight
        f_bigrams = {f[i : i + 2] for i in range(max(0, len(f) - 1))}
        if f_bigrams:
            score += len(q_bigrams & f_bigrams) / math.sqrt(len(f_bigrams)) * 0.1 * weight
    return score


def should_refuse(query, policies):
    q = str(query or "").lower()
    triggers = []
    ambiguous = set()
    for policy in policies:
        triggers.extend(policy.get("refusal_triggers", []))
        ambiguous.update(policy.get("ambiguous_queries", []))
    if str(query or "").strip() in ambiguous:
        return True
    return any(trigger in q for trigger in triggers)


def metric_ids_by_name(metrics):
    return {m["metric_name"]: m["metric_id"] for m in metrics}


def explicit_metric_from_policy(query, metrics):
    q = str(query or "").lower()
    hits = []
    for metric in metrics:
        aliases = [metric["metric_name"], metric["metric_id"], *metric.get("aliases", [])]
        for alias in aliases:
            alias_text = str(alias or "").lower()
            if not alias_text:
                continue
            idx = q.find(alias_text)
            if idx >= 0:
                hits.append((idx, -len(alias_text), metric["metric_id"], alias))
    if not hits:
        return ""
    hits.sort(key=lambda item: (item[0], item[1], item[2]))
    # Governed comparison policy: the first mentioned governed metric is the
    # primary metric; ties prefer the longest released catalog alias.
    return hits[0][2]


def rank_metrics(query, metrics):
    scored = []
    for metric in metrics:
        fields = [(metric["metric_name"], 2.0), (metric["metric_id"], 0.5)] + [
            (alias, 2.5) for alias in metric.get("aliases", [])
        ]
        scored.append((score_text(query, fields), metric["metric_id"]))
    scored.sort(reverse=True)
    return [{"metric_id": metric_id, "score": score} for score, metric_id in scored if score > 0]


def detect_dims(query, dims, finest=True):
    q = str(query or "")
    found = []
    for dim in dims:
        aliases = [dim["name"], dim["dimension_id"], *dim.get("aliases", [])]
        if any(str(alias).lower() in q.lower() for alias in aliases if alias):
            found.append(dim["dimension_id"])
    found_set = set(found)
    if finest:
        parent_by_id = {dim["dimension_id"]: dim.get("parent", "") for dim in dims}
        ancestors = set()
        for dim_id in list(found_set):
            parent = parent_by_id.get(dim_id, "")
            while parent:
                ancestors.add(parent)
                parent = parent_by_id.get(parent, "")
        found_set -= ancestors
    return sorted(found_set)


def predict(case, metrics, dims, policies, mode, compiler=None):
    assert_blind(case)
    query = case["nl_query"]
    ranked = rank_metrics(query, metrics)
    if mode == "safenlidb_guarded" and should_refuse(query, policies):
        return {
            "action": "refuse",
            "pred_metric_id": "",
            "pred_dimensions": [],
            "reason": f"{mode}_policy_refusal",
            "trace": {"candidate_metrics": ranked[:3], "used_gold_label": False},
        }
    if mode == "direct_keyword":
        pred_dims = []
        metric_id = ranked[0]["metric_id"] if ranked else ""
    elif mode == "schema_proxy":
        pred_dims = detect_dims(query, dims, finest=False)
        metric_id = ranked[0]["metric_id"] if ranked else ""
    elif mode == "safenlidb_guarded":
        pred_dims = detect_dims(query, dims, finest=False)
        metric_id = ranked[0]["metric_id"] if ranked else ""
    elif mode == "caliber_graph":
        metric_id = explicit_metric_from_policy(query, metrics) or (ranked[0]["metric_id"] if ranked else "")
        requested = detect_dims(query, dims, finest=False)
        return compiler.compile(
            query,
            metric_id,
            requested_dimensions=requested,
            candidate_metrics=ranked[:3],
        )
    else:
        raise ValueError(mode)
    return {
        "action": "answer",
        "pred_metric_id": metric_id,
        "pred_dimensions": pred_dims,
        "reason": mode,
        "trace": {"candidate_metrics": ranked[:3], "used_gold_label": False},
    }


def score_predictions(rows, gold_by_id):
    summary = {}
    for mode in sorted({row["mode"] for row in rows}):
        subset = [row for row in rows if row["mode"] == mode]
        c = Counter()
        for row in subset:
            gold = gold_by_id[row["case_id"]]
            expected_refusal = gold["expected_action"] == "refuse"
            refused = row["action"] == "refuse" or not row["pred_metric_id"]
            metric_ok = row["pred_metric_id"] == gold["expected_metric_id"]
            dim_ok = set(row["pred_dimensions"]) == set(gold["expected_dimensions"])
            c["metric"] += int(metric_ok)
            c["dim"] += int(dim_ok)
            c["joint"] += int(metric_ok and dim_ok)
            c["tp"] += int(refused and expected_refusal)
            c["fp"] += int(refused and not expected_refusal)
            c["fn"] += int((not refused) and expected_refusal)
        n = len(subset)
        summary[mode] = {
            "n": n,
            "metric_accuracy": c["metric"] / n,
            "dimension_exact_accuracy": c["dim"] / n,
            "joint_metric_dimension_accuracy": c["joint"] / n,
            "refusal_precision": c["tp"] / max(1, c["tp"] + c["fp"]),
            "refusal_recall": c["tp"] / max(1, c["tp"] + c["fn"]),
        }
    return summary


def score_dedup_predictions(rows, gold_by_id):
    dedup_rows = []
    seen = set()
    conflicts = []
    for row in rows:
        key = (row["mode"], normalized_query(row["nl_query"]))
        if key in seen:
            continue
        group = [r for r in rows if r["mode"] == row["mode"] and normalized_query(r["nl_query"]) == key[1]]
        gold_sigs = {
            json.dumps(
                {
                    "action": gold_by_id[g["case_id"]]["expected_action"],
                    "metric": gold_by_id[g["case_id"]]["expected_metric_id"],
                    "dims": sorted(gold_by_id[g["case_id"]]["expected_dimensions"]),
                },
                sort_keys=True,
            )
            for g in group
        }
        if len(gold_sigs) > 1:
            conflicts.append({"mode": row["mode"], "normalized_query": key[1], "case_ids": [g["case_id"] for g in group]})
            continue
        seen.add(key)
        dedup_rows.append(row)
    return score_predictions(dedup_rows, gold_by_id), {
        "dedup_rows": len(dedup_rows),
        "conflicting_groups_after_public_withholding": len(conflicts),
        "conflict_examples": conflicts[:5],
    }


def write_summary(summary, dedup_summary=None, dedup_audit=None):
    labels = {
        "direct_keyword": "Direct keyword",
        "schema_proxy": "Schema proxy",
        "safenlidb_guarded": "SafeNLIDB-derived E3 guard",
        "caliber_graph": "CaliberGraph",
    }
    order = ["direct_keyword", "schema_proxy", "safenlidb_guarded", "caliber_graph"]
    lines = [
        "# IndustrialCaseText-MetricCaliber Results",
        "",
        "Predictors read `blind_cases.jsonl`; `gold_labels.jsonl` is used only for scoring.",
        "",
        "| Method | Metric | Dim. | Joint | Ref.P | Ref.R |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mode in order:
        s = summary[mode]
        lines.append(
            f"| {labels[mode]} | {s['metric_accuracy']:.3f} | {s['dimension_exact_accuracy']:.3f} | {s['joint_metric_dimension_accuracy']:.3f} | {s['refusal_precision']:.3f} | {s['refusal_recall']:.3f} |"
        )
    if dedup_summary:
        lines.extend(
            [
                "",
                "## Deduplicated Normalized-Query Results",
                "",
                f"Groups per mode: {dedup_audit['dedup_rows'] // len(order)}; conflicting groups after withholding: {dedup_audit['conflicting_groups_after_public_withholding']}.",
                "",
                "| Method | Metric | Dim. | Joint | Ref.P | Ref.R |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for mode in order:
            s = dedup_summary[mode]
            lines.append(
                f"| {labels[mode]} | {s['metric_accuracy']:.3f} | {s['dimension_exact_accuracy']:.3f} | {s['joint_metric_dimension_accuracy']:.3f} | {s['refusal_precision']:.3f} | {s['refusal_recall']:.3f} |"
            )
    (OUT / "industrial_case_text_eval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    metrics = read_jsonl(DATA / "metric_catalog.jsonl")
    dims = read_jsonl(DATA / "dimension_catalog.jsonl")
    policies = read_jsonl(DATA / "policy_catalog.jsonl")
    compiler = ContractCompiler(DATA)
    cases = read_jsonl(DATA / "blind_cases.jsonl")
    gold = read_jsonl(DATA / "gold_labels.jsonl")
    for case in cases:
        assert_blind(case)
    gold_by_id = {row["case_id"]: row for row in gold}
    modes = ["direct_keyword", "schema_proxy", "safenlidb_guarded", "caliber_graph"]
    predictions = []
    for case in cases:
        for mode in modes:
            predictions.append({"mode": mode, **case, **predict(case, metrics, dims, policies, mode, compiler=compiler)})
    leaks = sum(any(k.startswith("expected_") or k.endswith("_hash") for k in p) for p in predictions)
    summary = score_predictions(predictions, gold_by_id)
    dedup_summary, dedup_audit = score_dedup_predictions(predictions, gold_by_id)
    write_jsonl(OUT / "industrial_case_text_predictions.jsonl", predictions)
    write_json(
        OUT / "industrial_case_text_eval_results.json",
        {
            "summary": summary,
            "deduplicated_normalized_query_summary": dedup_summary,
            "deduplication_audit": dedup_audit,
            "artifact_counts": {"cases": len(cases), "metrics": len(metrics), "dimensions": len(dims)},
            "blind_protocol": {
                "prediction_input": "blind_cases.jsonl",
                "scoring_input": "gold_labels.jsonl",
                "gold_field_leaks_in_predictions": leaks,
            },
        },
    )
    write_summary(summary, dedup_summary=dedup_summary, dedup_audit=dedup_audit)
    print(json.dumps({"summary": summary, "deduplicated_normalized_query_summary": dedup_summary, "gold_field_leaks": leaks}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
