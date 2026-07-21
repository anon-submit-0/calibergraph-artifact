#!/usr/bin/env python3
"""Evaluate runnable public baselines on IowaLiquor-MetricCaliber."""

import json
import math
import re
import sqlite3
from collections import Counter
from pathlib import Path

from calibergraph_contract_compiler import ContractCompiler


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public_benchmark" / "iowa_liquor_metric_caliber"
OUT = DATA / "results"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n", encoding="utf-8")


def assert_blind(case):
    leaked = sorted(key for key in case if key.startswith("expected_"))
    if leaked:
        raise AssertionError(f"blind case contains gold fields: {leaked}")


def norm(value):
    return "" if value is None else str(value).strip()


def split_terms(text):
    text = norm(text).lower()
    return set(re.findall(r"[a-z0-9_]+", text) + re.findall(r"[\u4e00-\u9fff]{2,}", text))


def char_bigrams(text):
    text = re.sub(r"\s+", "", norm(text).lower())
    return {text[i : i + 2] for i in range(max(0, len(text) - 1))}


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


def load_data():
    metrics = {m["metric_id"]: m for m in read_jsonl(DATA / "metric_catalog.jsonl")}
    dims = {d["dimension_id"]: d for d in read_jsonl(DATA / "dimension_catalog.jsonl")}
    cases = read_jsonl(DATA / "blind_cases.jsonl")
    gold = read_jsonl(DATA / "gold_labels.jsonl")
    edges = read_jsonl(DATA / "governance_edges.jsonl")
    for metric in metrics.values():
        metric["fields"] = [
            (metric.get("metric_id"), 2.5),
            (metric.get("metric_name"), 3.0),
            (metric.get("formula"), 1.0),
            (metric.get("description"), 1.0),
            *[(alias, 2.5) for alias in metric.get("aliases", [])],
        ]
    for dim in dims.values():
        dim["fields"] = [
            (dim.get("dimension_id"), 2.5),
            (dim.get("name"), 3.0),
            *[(alias, 2.5) for alias in dim.get("aliases", [])],
        ]
    metric_dims = {mid: set(m.get("allowed_dimensions") or []) for mid, m in metrics.items()}
    parents = {d["dimension_id"]: d.get("parent", "") for d in dims.values()}
    for edge in edges:
        if edge.get("edge_type") == "measures_of":
            metric_dims.setdefault(edge["src"], set()).add(edge["dst"])
        if edge.get("edge_type") == "rolls_up_to":
            parents[edge["src"]] = edge["dst"]
    return metrics, dims, cases, gold, metric_dims, parents


def should_refuse(query, metric_id=""):
    q = norm(query).lower()
    if any(t in q for t in ["select ", "drop ", "delete ", "insert ", "update ", "truncate "]):
        return True, "sql_or_ddl"
    if any(t in q for t in ["invoice id", "invoice ids", "raw invoice", "store address", "addresses", "phone", "customer"]):
        return True, "row_level_or_sensitive"
    if any(t in q for t in ["weather", "tomorrow"]):
        return True, "off_domain"
    if metric_id == "profit_margin" or any(t in q for t in ["profit margin", "gross margin", "margin"]):
        return True, "unsupported_metric"
    return False, "answerable"


def rank_metrics(query, metrics, k=5, direct=False):
    scored = []
    q = norm(query).lower()
    for metric_id, metric in metrics.items():
        fields = metric["fields"][:2] if direct else metric["fields"]
        score = text_score(query, fields)
        if metric_id == "item_count" and any(t in q for t in ["product", "products", "item count", "items", "sku count"]):
            score += 30.0
        if metric_id == "store_count" and any(t in q for t in ["store count", "retailer count", "stores", "retailers"]):
            score += 8.0
        if metric_id == "invoice_count" and any(t in q for t in ["invoice count", "invoices", "order count", "orders", "transactions"]):
            score += 8.0
        if metric.get("answerable") is False and any(t in norm(query).lower() for t in metric.get("aliases", [])):
            score += 5.0
        scored.append((score, metric_id))
    scored.sort(reverse=True)
    return [metric_id for score, metric_id in scored[:k] if score > 0]


def explicit_dims(query):
    q = norm(query).lower()
    if " by " in q:
        group_text = q.split(" by ", 1)[1]
    elif " each " in q:
        group_text = q.split(" each ", 1)[1]
    elif "monthly" in q:
        group_text = "month"
    elif "quarterly" in q:
        group_text = "quarter"
    else:
        return []
    dims = []
    if "monthly" in q or " month" in q:
        dims.append("ordered_month")
    if "quarterly" in q or " quarter" in q:
        dims.append("ordered_quarter")
    checks = [
        ("ordered_month", ["monthly", "month"]),
        ("ordered_quarter", ["quarterly", "quarter"]),
        ("county_name", ["county"]),
        ("store_city", ["city"]),
        ("store_name", ["store", "retailer"]),
        ("category_name", ["category"]),
        ("vendor_name", ["vendor", "supplier"]),
        ("item_desc", ["item", "product", "sku"]),
    ]
    for dim_id, aliases in checks:
        if any(alias in group_text for alias in aliases):
            dims.append(dim_id)
    return list(dict.fromkeys(dims))


def ancestors(dim_id, parents):
    out = []
    cur = parents.get(dim_id, "")
    while cur:
        out.append(cur)
        cur = parents.get(cur, "")
    return out


def finest_dims(dim_ids, parents):
    dim_ids = list(dict.fromkeys(dim_ids))
    dim_set = set(dim_ids)
    keep = []
    for dim in dim_ids:
        if dim not in set().union(*(set(ancestors(other, parents)) for other in dim_set), set()):
            keep.append(dim)
    return keep


def predict(case, metrics, metric_dims, parents, mode, compiler, oracle_metric_id=""):
    assert_blind(case)
    q = case["nl_query"]
    if mode == "oracle_candidate_prompt" and oracle_metric_id:
        metric_id = oracle_metric_id
    else:
        ranked = rank_metrics(q, metrics, k=5, direct=(mode == "direct_keyword"))
        metric_id = ranked[0] if ranked else ""
    refuse, reason = should_refuse(q, metric_id)
    if mode in {"safenlidb_guarded", "oracle_candidate_prompt"} and refuse:
        return {"action": "refuse", "pred_metric_id": "", "pred_dimensions": [], "reason": reason}
    if metrics.get(metric_id, {}).get("answerable") is False:
        if mode == "caliber_graph":
            return compiler.compile(q, metric_id, requested_dimensions=[], candidate_metrics=[])
    if mode == "direct_keyword":
        dims = []
    elif mode in {"schema_proxy", "open_sql_end_to_end", "autolink_iterative", "safenlidb_guarded", "oracle_candidate_prompt"}:
        dims = explicit_dims(q)
    else:
        ranked = rank_metrics(q, metrics, k=5)
        return compiler.compile(
            q,
            metric_id,
            requested_dimensions=compiler.detect_dimensions(q),
            candidate_metrics=ranked[:3],
        )
    return {"action": "answer", "pred_metric_id": metric_id, "pred_dimensions": dims, "reason": mode}


def metric_sql(metric):
    return metric.get("formula") or "NULL"


def plan_sql(plan, metrics, dims):
    metric_id = plan.get("pred_metric_id", "")
    if plan.get("action") == "refuse" or not metric_id or metric_id not in metrics:
        return ""
    dim_ids = [d for d in plan.get("pred_dimensions", []) if d in dims]
    exprs = [f"{dims[d]['sql']} AS {d}" for d in dim_ids]
    group_exprs = [dims[d]["sql"] for d in dim_ids]
    select_exprs = exprs + [f"{metric_sql(metrics[metric_id])} AS metric_value"]
    sql = f"SELECT {', '.join(select_exprs)} FROM iowa_liquor_sales"
    if group_exprs:
        sql += " GROUP BY " + ", ".join(group_exprs)
        sql += " ORDER BY metric_value DESC LIMIT 20"
    return sql


def execute_sql(sql):
    if not sql:
        return {"execute_ok": None, "row_count": 0, "sample": []}
    conn = sqlite3.connect(DATA / "iowa_liquor_2024_sample.sqlite")
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(sql).fetchmany(5)]
        return {"execute_ok": True, "row_count": len(rows), "sample": rows}
    except Exception as exc:
        return {"execute_ok": False, "row_count": 0, "error": str(exc), "sample": []}
    finally:
        conn.close()


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
            if row.get("execute_ok") is True:
                counts["execute_ok"] += 1
            row["metric_ok"] = metric_ok
            row["dimension_exact_ok"] = dim_ok
            row["joint_ok"] = metric_ok and dim_ok
        n = len(subset)
        answerable_predictions = sum(1 for row in subset if row.get("action") == "answer" and row.get("pred_metric_id"))
        summary[mode] = {
            "n": n,
            "metric_accuracy": counts["metric_ok"] / n,
            "dimension_exact_accuracy": counts["dimension_exact_ok"] / n,
            "joint_metric_dimension_accuracy": counts["joint_ok"] / n,
            "refusal_precision": counts["refusal_tp"] / max(1, counts["refusal_tp"] + counts["refusal_fp"]),
            "refusal_recall": counts["refusal_tp"] / max(1, counts["refusal_tp"] + counts["refusal_fn"]),
            "sql_execution_success_rate_on_answer_predictions": counts["execute_ok"] / max(1, answerable_predictions),
        }
    return summary


def candidate_recall(cases, gold_by_id, metrics, dims, metric_dims):
    rows = []
    for case in cases:
        gold = gold_by_id[case["case_id"]]
        if gold["expected_action"] != "answer":
            continue
        mids = rank_metrics(case["nl_query"], metrics, k=3)
        explicit = set(explicit_dims(case["nl_query"]))
        expanded = set(explicit)
        for mid in mids:
            expanded.update(metric_dims.get(mid, set()))
        rows.append(
            {
                "case_id": case["case_id"],
                "metric_candidate_hit": gold["expected_metric_id"] in mids,
                "dimension_candidate_hit": set(gold["expected_dimensions"]).issubset(expanded),
                "joint_candidate_hit": gold["expected_metric_id"] in mids and set(gold["expected_dimensions"]).issubset(expanded),
                "candidate_metric_count": len(mids),
                "candidate_dimension_count": len(expanded),
            }
        )
    n = len(rows)
    return {
        "n_answerable": n,
        "metric_candidate_recall_at_3": sum(r["metric_candidate_hit"] for r in rows) / n,
        "dimension_candidate_recall": sum(r["dimension_candidate_hit"] for r in rows) / n,
        "joint_candidate_recall": sum(r["joint_candidate_hit"] for r in rows) / n,
        "avg_candidate_metric_count": sum(r["candidate_metric_count"] for r in rows) / n,
        "avg_candidate_dimension_count": sum(r["candidate_dimension_count"] for r in rows) / n,
    }


def write_summary(summary, link_summary):
    labels = {
        "direct_keyword": "Direct keyword",
        "schema_proxy": "Schema proxy",
        "open_sql_end_to_end": "Open SQL end-to-end",
        "autolink_iterative": "AutoLink-derived E3",
        "safenlidb_guarded": "SafeNLIDB-derived E3",
        "oracle_candidate_prompt": "Oracle-candidate prompt",
        "caliber_graph": "CaliberGraph",
    }
    order = ["direct_keyword", "schema_proxy", "open_sql_end_to_end", "autolink_iterative", "safenlidb_guarded", "oracle_candidate_prompt", "caliber_graph"]
    lines = [
        "# IowaLiquor-MetricCaliber Evaluation",
        "",
        "Real public row-level business data from the State of Iowa 2024 Liquor Sales dataset.",
        "",
        "| Method | Metric | Dim. | Joint | Ref.P | Ref.R | SQL exec. (ans.) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for mode in order:
        item = summary[mode]
        lines.append(
            f"| {labels[mode]} | {item['metric_accuracy']:.3f} | {item['dimension_exact_accuracy']:.3f} | {item['joint_metric_dimension_accuracy']:.3f} | {item['refusal_precision']:.3f} | {item['refusal_recall']:.3f} | {item['sql_execution_success_rate_on_answer_predictions']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Candidate Recall",
            "",
            f"- Answerable cases: {link_summary['n_answerable']}",
            f"- Metric candidate recall@3: {link_summary['metric_candidate_recall_at_3']:.3f}",
            f"- Dimension candidate recall: {link_summary['dimension_candidate_recall']:.3f}",
            f"- Joint candidate recall: {link_summary['joint_candidate_recall']:.3f}",
            "",
            "Interpretation: the open SQL baseline can generate executable SQLite queries, but executable SQL is not sufficient for governed metric caliber. The largest remaining gaps are finest-grain hierarchy resolution and refusal of unsupported or row-level requests.",
        ]
    )
    (OUT / "iowa_liquor_eval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    metrics, dims, cases, gold, metric_dims, parents = load_data()
    gold_by_id = {row["case_id"]: row for row in gold}
    compiler = ContractCompiler(DATA)
    for case in cases:
        assert_blind(case)
    modes = ["direct_keyword", "schema_proxy", "open_sql_end_to_end", "autolink_iterative", "safenlidb_guarded", "oracle_candidate_prompt", "caliber_graph"]
    rows = []
    for mode in modes:
        for case in cases:
            oracle_metric = gold_by_id[case["case_id"]]["expected_metric_id"] if mode == "oracle_candidate_prompt" else ""
            plan = predict(case, metrics, metric_dims, parents, mode, compiler, oracle_metric_id=oracle_metric)
            sql = plan_sql(plan, metrics, dims)
            execution = execute_sql(sql)
            rows.append(
                {
                    "mode": mode,
                    "case_id": case["case_id"],
                    "nl_query": case["nl_query"],
                    **plan,
                    "sql": sql,
                    "execute_ok": execution["execute_ok"],
                    "sql_row_count_sampled": execution["row_count"],
                    "sql_error": execution.get("error", ""),
                }
            )
    summary = score(rows, gold_by_id)
    link_summary = candidate_recall(cases, gold_by_id, metrics, dims, metric_dims)
    write_jsonl(OUT / "iowa_liquor_predictions.jsonl", rows)
    write_json(
        OUT / "iowa_liquor_eval_results.json",
        {
            "plan": summary,
            "linking": link_summary,
            "blind_protocol": {
                "prediction_input": "blind_cases.jsonl",
                "scoring_input": "gold_labels.jsonl",
                "gold_field_leaks_in_predictions": sum(
                    any(key.startswith("expected_") for key in row) for row in rows
                ),
                "oracle_candidate_prompt_uses_scorer_metric": True,
            },
        },
    )
    write_summary(summary, link_summary)
    print(json.dumps({"plan": summary, "linking": link_summary}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
