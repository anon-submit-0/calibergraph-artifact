#!/usr/bin/env python3
"""Evaluate public MultiGov-MetricCaliber artifacts with blind prediction.

The predictor reads only released anonymous catalogs, graph/policy files, and
blind cases. Gold labels are loaded only by the scorer after predictions have
been written. This keeps the public evaluator from turning into label replay.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from calibergraph_contract_compiler import ContractCompiler


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public_benchmark" / "multigov_metric_caliber"
OUT = DATA / "results"

GOLD_KEYS = {
    "expected_action",
    "expected_metric_id",
    "expected_dimensions",
    "expected_policy_id",
    "expected_time_binding",
    "source_provenance_id",
}


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def blind_case(case):
    return {k: v for k, v in case.items() if k not in GOLD_KEYS}


def gold_label(case):
    return {
        "case_id": case["case_id"],
        "expected_action": case["expected_action"],
        "expected_metric_id": case["expected_metric_id"],
        "expected_dimensions": case["expected_dimensions"],
        "expected_policy_id": case.get("expected_policy_id", ""),
        "expected_time_binding": case.get("expected_time_binding", ""),
        "query_family": case["query_family"],
    }


def assert_blind(case):
    leaked = sorted(k for k in case if k in GOLD_KEYS or k.startswith("expected_"))
    if leaked:
        raise AssertionError(f"blind case contains gold fields: {leaked}")


def split_terms(text: str):
    text = str(text or "").lower()
    return set(re.findall(r"[a-z0-9_]+", text) + re.findall(r"[\u4e00-\u9fff]{2,}", text))


def score_text(query: str, fields) -> float:
    query = str(query or "").lower()
    q_terms = split_terms(query)
    q_bigrams = {query[i : i + 2] for i in range(max(0, len(query) - 1))}
    score = 0.0
    for field, weight in fields:
        field = str(field or "").lower()
        if not field:
            continue
        if field in query:
            score += 4.0 * weight
        f_terms = split_terms(field)
        score += len(q_terms & f_terms) * weight
        f_bigrams = {field[i : i + 2] for i in range(max(0, len(field) - 1))}
        if f_bigrams:
            score += len(q_bigrams & f_bigrams) / math.sqrt(len(f_bigrams)) * 0.1 * weight
    return score


def should_refuse(query: str):
    q = str(query or "").lower()
    triggers = [
        "raw row",
        "identifier",
        "private-to-public",
        "private mapping",
        "select ",
        "hidden",
        "customer contact",
    ]
    matched = [trigger for trigger in triggers if trigger in q]
    return bool(matched), matched


def rank_metrics(query: str, metrics):
    scored = []
    for metric in metrics:
        fields = [
            (metric["metric_name"], 2.0),
            (metric["metric_id"], 1.0),
            (metric.get("metric_type"), 0.8),
            (metric.get("formula_role"), 0.8),
            *[(a, 2.5) for a in metric.get("aliases", [])],
        ]
        scored.append((score_text(query, fields), metric["metric_id"]))
    scored.sort(reverse=True)
    return [{"metric_id": metric_id, "score": score} for score, metric_id in scored if score > 0]


def explicit_dims(query: str, domain_id: str):
    query = str(query or "").lower()
    candidates = []
    if "summary scope" in query or "coarse scope" in query or "level one scope" in query:
        candidates.append(f"{domain_id}_summary_scope")
    if "fine scope" in query or "finest scope" in query or "level two scope" in query:
        candidates.append(f"{domain_id}_fine_scope")
    asks_time_dimension = (
        "valid time anchor" in query
        or "valid time" in query
        or "as-of anchor" in query
        or re.search(r"\b(by|per|across|group by)\s+time anchor\b", query)
    )
    if asks_time_dimension:
        candidates.append(f"{domain_id}_time_anchor")
    if "policy scope" in query or "release scope" in query or "disclosure scope" in query:
        candidates.append(f"{domain_id}_policy_scope")
    return list(dict.fromkeys(candidates))


def finest_dims(dims, rollup_parent):
    dims = list(dims)
    dim_set = set(dims)
    parents_shadowed_by_child = {parent for child, parent in rollup_parent.items() if child in dim_set}
    return [dim for dim in dims if dim not in parents_shadowed_by_child]


def domain_for_metric(metric_id, metric_by_id):
    metric = metric_by_id.get(metric_id) or {}
    return metric.get("domain_id") or "mg_domain_01"


def candidate_metric(case, metrics):
    ranked = rank_metrics(case["nl_query"], metrics)
    return ranked[0]["metric_id"] if ranked else "", ranked


def predict_public(case, metric_by_id, metrics, rollup_parent, mode, compiler):
    assert_blind(case)
    query = case["nl_query"]
    refused, policy_hits = should_refuse(query)
    ranked_metric_id, ranked = candidate_metric(case, metrics)
    domain_id = domain_for_metric(ranked_metric_id, metric_by_id)
    dims = compiler.detect_dimensions(query, domain_id=domain_id)

    if mode in {"safenlidb_guarded", "no_grain_compiler"} and refused:
        return {
            "action": "refuse",
            "pred_metric_id": "",
            "pred_dimensions": [],
            "reason": f"{mode}_policy_refusal",
            "trace": {"policy_hits": policy_hits, "candidate_metrics": ranked[:3], "used_gold_label": False},
        }

    if mode == "direct_keyword":
        pred_dims = []
    elif mode in {"schema_proxy", "autolink_iterative", "safenlidb_guarded", "no_grain_compiler"}:
        pred_dims = dims
    elif mode == "no_policy_compiler":
        pred_dims = finest_dims(dims, rollup_parent)
    elif mode == "caliber_graph":
        return compiler.compile(
            query,
            ranked_metric_id,
            requested_dimensions=dims,
            candidate_metrics=ranked[:3],
        )
    else:
        raise ValueError(mode)

    return {
        "action": "answer",
        "pred_metric_id": ranked_metric_id,
        "pred_dimensions": pred_dims,
        "reason": mode,
        "trace": {
            "candidate_metrics": ranked[:3],
            "explicit_dimensions": dims,
            "resolved_dimensions": pred_dims,
            "policy_hits": policy_hits,
            "used_gold_label": False,
        },
    }


def predict_oracle_metric(case, gold, metric_by_id, rollup_parent, compiler):
    assert_blind(case)
    query = case["nl_query"]
    refused, policy_hits = should_refuse(query)
    if refused:
        return {
            "action": "refuse",
            "pred_metric_id": "",
            "pred_dimensions": [],
            "reason": "oracle_candidate_prompt_policy_refusal",
            "trace": {"policy_hits": policy_hits, "used_gold_metric_candidate": True},
        }
    metric_id = gold["expected_metric_id"]
    domain_id = domain_for_metric(metric_id, metric_by_id)
    dims = compiler.detect_dimensions(query, domain_id=domain_id)
    return {
        "action": "answer",
        "pred_metric_id": metric_id,
        "pred_dimensions": dims,
            "reason": "oracle_metric_without_grain_compiler",
        "trace": {
            "explicit_dimensions": dims,
            "used_gold_metric_candidate": True,
            "used_gold_dimensions": False,
        },
    }


def score_predictions(predictions, gold_by_id):
    summary = {}
    scored_rows = []
    for mode in sorted({row["mode"] for row in predictions}):
        subset = [row for row in predictions if row["mode"] == mode]
        c = Counter()
        for row in subset:
            gold = gold_by_id[row["case_id"]]
            expected_refusal = gold["expected_action"] == "refuse"
            refused = row["action"] == "refuse" or row["pred_metric_id"] == ""
            metric_ok = row["pred_metric_id"] == gold["expected_metric_id"]
            dim_ok = set(row["pred_dimensions"]) == set(gold["expected_dimensions"])
            dim_recall = set(gold["expected_dimensions"]).issubset(set(row["pred_dimensions"]))
            c["metric_ok"] += int(metric_ok)
            c["dimension_exact_ok"] += int(dim_ok)
            c["dimension_recall_ok"] += int(dim_recall)
            c["joint_ok"] += int(metric_ok and dim_ok)
            c["refusal_tp"] += int(refused and expected_refusal)
            c["refusal_fp"] += int(refused and not expected_refusal)
            c["refusal_fn"] += int((not refused) and expected_refusal)
            scored_rows.append(
                {
                    "case_id": row["case_id"],
                    "mode": mode,
                    "metric_ok": metric_ok,
                    "dimension_exact_ok": dim_ok,
                    "dimension_recall_ok": dim_recall,
                    "joint_ok": metric_ok and dim_ok,
                    "refusal_tp": bool(refused and expected_refusal),
                    "refusal_fp": bool(refused and not expected_refusal),
                    "refusal_fn": bool((not refused) and expected_refusal),
                }
            )
        n = len(subset)
        summary[mode] = {
            "n": n,
            "metric_accuracy": c["metric_ok"] / n,
            "dimension_exact_accuracy": c["dimension_exact_ok"] / n,
            "dimension_recall_accuracy": c["dimension_recall_ok"] / n,
            "joint_metric_dimension_accuracy": c["joint_ok"] / n,
            "refusal_precision": c["refusal_tp"] / max(1, c["refusal_tp"] + c["refusal_fp"]),
            "refusal_recall": c["refusal_tp"] / max(1, c["refusal_tp"] + c["refusal_fn"]),
        }
    return summary, scored_rows


def write_summary(summary, family, link):
    labels = {
        "direct_keyword": "Direct keyword",
        "schema_proxy": "Schema proxy",
        "autolink_iterative": "AutoLink-derived E3",
        "safenlidb_guarded": "SafeNLIDB-derived E3",
        "oracle_candidate_prompt": "Oracle-candidate",
        "caliber_graph": "CaliberGraph",
        "no_grain_compiler": "No grain compiler",
        "no_policy_compiler": "No policy compiler",
    }
    order = ["direct_keyword", "schema_proxy", "autolink_iterative", "safenlidb_guarded", "oracle_candidate_prompt", "caliber_graph"]
    lines = [
        "# MultiGov-MetricCaliber Results",
        "",
        "Blind protocol: predictors read `blind_cases.jsonl` plus public catalogs; `gold_labels.jsonl` is used only by the scorer. The oracle-candidate row is explicitly a gold-metric upper-bound diagnostic.",
        "",
        "## Main Results",
        "",
        "| Method | Metric | Dim. | Joint | Ref.P | Ref.R |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mode in order:
        s = summary[mode]
        lines.append(
            f"| {labels[mode]} | {s['metric_accuracy']:.3f} | {s['dimension_exact_accuracy']:.3f} | {s['joint_metric_dimension_accuracy']:.3f} | {s['refusal_precision']:.3f} | {s['refusal_recall']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Candidate Recall",
            "",
            f"- Answerable cases: {link['n_answerable']}",
            f"- Metric candidate recall@3: {link['metric_candidate_recall_at_3']:.3f}",
            f"- Dimension candidate recall: {link['dimension_candidate_recall_at_explicit']:.3f}",
            f"- Joint candidate recall: {link['joint_candidate_recall']:.3f}",
            "",
            "## Query-Family Joint Accuracy",
            "",
            "| Family | AutoLink-derived E3 | SafeNLIDB-derived E3 | CaliberGraph |",
            "|---|---:|---:|---:|",
        ]
    )
    for family_name in sorted(family):
        item = family[family_name]
        lines.append(
            f"| {family_name} | {item['autolink_iterative']['joint_metric_dimension_accuracy']:.3f} | {item['safenlidb_guarded']['joint_metric_dimension_accuracy']:.3f} | {item['caliber_graph']['joint_metric_dimension_accuracy']:.3f} |"
        )
    (OUT / "multigov_eval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    metrics = read_jsonl(DATA / "metric_catalog.jsonl")
    raw_cases = read_jsonl(DATA / "test_cases.jsonl")
    edges = read_jsonl(DATA / "governance_edges.jsonl")
    metric_by_id = {metric["metric_id"]: metric for metric in metrics}
    compiler = ContractCompiler(DATA)
    gold_rows = [gold_label(case) for case in raw_cases]
    blind_rows = [blind_case(case) for case in raw_cases]
    for case in blind_rows:
        assert_blind(case)
    gold_by_id = {row["case_id"]: row for row in gold_rows}
    rollup_parent = {edge["src"]: edge["dst"] for edge in edges if edge.get("edge_type") == "rolls_up_to"}

    write_jsonl(DATA / "blind_cases.jsonl", blind_rows)
    write_jsonl(DATA / "gold_labels.jsonl", gold_rows)

    modes = [
        "direct_keyword",
        "schema_proxy",
        "autolink_iterative",
        "safenlidb_guarded",
        "oracle_candidate_prompt",
        "caliber_graph",
        "no_grain_compiler",
        "no_policy_compiler",
    ]
    predictions = []
    for case in blind_rows:
        for mode in modes:
            if mode == "oracle_candidate_prompt":
                pred = predict_oracle_metric(case, gold_by_id[case["case_id"]], metric_by_id, rollup_parent, compiler)
            else:
                pred = predict_public(case, metric_by_id, metrics, rollup_parent, mode, compiler)
            predictions.append({"mode": mode, **case, **pred})

    summary, scored_rows = score_predictions(predictions, gold_by_id)
    family = {}
    for family_name in sorted({case["query_family"] for case in blind_rows}):
        fam_predictions = [row for row in predictions if row["query_family"] == family_name]
        family[family_name], _ = score_predictions(fam_predictions, gold_by_id)

    answerable = [gold for gold in gold_rows if gold["expected_action"] == "answer"]
    candidate_hits = 0
    dim_hits = 0
    joint_hits = 0
    blind_by_id = {case["case_id"]: case for case in blind_rows}
    for gold in answerable:
        case = blind_by_id[gold["case_id"]]
        ranked = rank_metrics(case["nl_query"], metrics)[:3]
        metric_hit = gold["expected_metric_id"] in {item["metric_id"] for item in ranked}
        domain_id = domain_for_metric(gold["expected_metric_id"], metric_by_id)
        dims = compiler.detect_dimensions(case["nl_query"], domain_id=domain_id)
        dim_hit = set(gold["expected_dimensions"]).issubset(set(finest_dims(dims, rollup_parent)))
        candidate_hits += int(metric_hit)
        dim_hits += int(dim_hit)
        joint_hits += int(metric_hit and dim_hit)
    link = {
        "n_answerable": len(answerable),
        "metric_candidate_recall_at_3": candidate_hits / len(answerable),
        "dimension_candidate_recall_at_explicit": dim_hits / len(answerable),
        "joint_candidate_recall": joint_hits / len(answerable),
    }

    write_jsonl(OUT / "multigov_predictions.jsonl", predictions)
    write_jsonl(OUT / "multigov_score_audit.jsonl", scored_rows)
    write_json(
        OUT / "multigov_eval_results.json",
        {
            "summary": summary,
            "family_breakdown": family,
            "linking": link,
            "blind_protocol": {
                "prediction_input": "blind_cases.jsonl",
                "scoring_input": "gold_labels.jsonl",
                "gold_fields_forbidden_in_predictions": sorted(GOLD_KEYS),
                "oracle_candidate_prompt_uses_gold_metric": True,
            },
            "artifact_counts": {
                "metrics": len(metrics),
                "cases": len(blind_rows),
                "domains": len(read_jsonl(DATA / "domain_catalog.jsonl")),
            },
        },
    )
    write_summary(summary, family, link)
    print(json.dumps({"out": str(OUT), "summary": summary, "blind_protocol": True}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
