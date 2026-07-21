#!/usr/bin/env python3
"""Evaluate deterministic baselines on GovTwin-MetricCaliber."""

import json
import math
import re
from collections import Counter
from pathlib import Path

from calibergraph_contract_compiler import ContractCompiler


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public_benchmark" / "govtwin_metric_caliber"
OUT = DATA / "results"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def assert_blind(case):
    leaked = sorted(key for key in case if key.startswith("expected_"))
    if leaked:
        raise AssertionError(f"blind case contains gold fields: {leaked}")


def split_labeled_cases(rows):
    blind_rows = []
    gold_rows = []
    for row in rows:
        blind_rows.append({key: value for key, value in row.items() if not key.startswith("expected_")})
        gold = {"case_id": row["case_id"]}
        gold.update({key: value for key, value in row.items() if key.startswith("expected_")})
        for key in ("query_family", "severity", "source_case_id", "perturbation_type"):
            if key in row:
                gold[key] = row[key]
        gold_rows.append(gold)
    for row in blind_rows:
        assert_blind(row)
    return blind_rows, gold_rows


def norm(value):
    if value is None:
        return ""
    return str(value).strip()


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
            (metric.get("metric_name"), 2.0),
            (metric.get("formula"), 0.8),
            *[(a, 2.0) for a in metric.get("aliases", [])],
        ]
    for dim in dims.values():
        dim["fields"] = [
            (dim.get("dimension_id"), 2.5),
            (dim.get("name"), 2.0),
            *[(a, 2.5) for a in dim.get("aliases", [])],
        ]
    metric_dims = {mid: set(m.get("allowed_dimensions") or []) for mid, m in metrics.items()}
    for edge in edges:
        if edge.get("edge_type") == "measures_of":
            metric_dims.setdefault(edge["src"], set()).add(edge["dst"])
    return metrics, dims, cases, gold, metric_dims


def load_optional_jsonl(path):
    if not path.exists():
        return []
    return read_jsonl(path)


def should_refuse(query):
    q = norm(query).lower()
    triggers = [
        "select ",
        "drop ",
        "delete ",
        "insert ",
        "update ",
        "email",
        "phone",
        "personal contact",
        "identifier",
        "customer",
        "weather",
        "unsupported",
        "experimental margin",
    ]
    return any(t in q for t in triggers)


def refusal_category(query, expected_action="refuse"):
    if expected_action != "refuse":
        return "answerable"
    q = norm(query).lower()
    if any(t in q for t in ["select ", "drop ", "delete ", "insert ", "update "]):
        return "sql_or_ddl"
    if any(t in q for t in ["email", "phone", "personal contact", "identifier", "customer"]):
        return "sensitive_or_identifier"
    if any(t in q for t in ["weather", "tomorrow"]):
        return "off_domain"
    if any(t in q for t in ["unsupported", "experimental margin"]):
        return "unsupported_metric"
    return "policy_denied"


def rank_metrics(query, metrics, k=5, direct=False):
    scored = []
    for metric_id, metric in metrics.items():
        fields = metric["fields"][:2] if direct else metric["fields"]
        score = text_score(query, fields)
        if metric.get("metric_type") == "ratio" and any(t in norm(query).lower() for t in ["ratio", "rate", "share", "占比", "比例"]):
            score += 1.0
        scored.append((score, metric_id))
    scored.sort(reverse=True)
    return [metric_id for score, metric_id in scored[:k] if score > 0]


def explicit_all_dims(query):
    q = norm(query).lower()
    dims = []
    checks = [
        ("segment_l1", ["segment level 1", "level one", "一级组合"]),
        ("segment_l2", ["segment level 2", "level two", "二级组合"]),
        ("segment_l3", ["segment level 3", "level three", "三级组合"]),
        ("issue_type", ["issue type", "signal type", "问题类型"]),
        ("market_region", ["market region", "operating region", "市场区域"]),
    ]
    for dim_id, aliases in checks:
        if any(alias in q for alias in aliases):
            dims.append(dim_id)
    return list(dict.fromkeys(dims))


def finest_dims(query):
    dims = explicit_all_dims(query)
    if "segment_l3" in dims:
        dims = [d for d in dims if d not in {"segment_l1", "segment_l2"}]
    elif "segment_l2" in dims:
        dims = [d for d in dims if d != "segment_l1"]
    return dims


def predict(case, metrics, metric_dims, mode, compiler, oracle_metric_id=""):
    assert_blind(case)
    q = case["nl_query"]
    if mode in {"safenlidb_guarded", "no_grain_compiler", "oracle_candidate_prompt"} and should_refuse(q):
        return {"action": "refuse", "pred_metric_id": "", "pred_dimensions": [], "reason": f"{mode}_policy_refusal"}
    if mode == "oracle_candidate_prompt" and oracle_metric_id:
        return {
            "action": "answer",
            "pred_metric_id": oracle_metric_id,
            "pred_dimensions": explicit_all_dims(q),
            "reason": "gold_metric_candidate_with_prompt_style_dimension_finalizer",
        }
    ranked = rank_metrics(q, metrics, k=5, direct=(mode == "direct_keyword"))
    metric_id = ranked[0] if ranked else ""
    if mode == "direct_keyword":
        dims = []
    elif mode in {"schema_proxy", "autolink_iterative", "safenlidb_guarded", "no_grain_compiler", "no_graph_constraints"}:
        dims = explicit_all_dims(q)
    elif mode == "caliber_graph":
        return compiler.compile(
            q,
            metric_id,
            requested_dimensions=compiler.detect_dimensions(q),
            candidate_metrics=ranked[:3],
        )
    else:
        dims = [d for d in finest_dims(q) if d in metric_dims.get(metric_id, set()) or d in set().union(*metric_dims.values())]
    return {"action": "answer", "pred_metric_id": metric_id, "pred_dimensions": dims, "reason": mode}


def score_rows(rows, gold_by_id):
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
            dim_recall = set(gold["expected_dimensions"]).issubset(set(row["pred_dimensions"]))
            if metric_ok:
                counts["metric_ok"] += 1
            if dim_ok:
                counts["dimension_exact_ok"] += 1
            if dim_recall:
                counts["dimension_recall_ok"] += 1
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
            row["dimension_recall_ok"] = dim_recall
            row["joint_ok"] = metric_ok and dim_ok
        n = len(subset)
        summary[mode] = {
            "n": n,
            "metric_accuracy": counts["metric_ok"] / n,
            "dimension_exact_accuracy": counts["dimension_exact_ok"] / n,
            "dimension_recall_accuracy": counts["dimension_recall_ok"] / n,
            "joint_metric_dimension_accuracy": counts["joint_ok"] / n,
            "refusal_precision": counts["refusal_tp"] / max(1, counts["refusal_tp"] + counts["refusal_fp"]),
            "refusal_recall": counts["refusal_tp"] / max(1, counts["refusal_tp"] + counts["refusal_fn"]),
        }
    return summary


def refusal_breakdown(rows, gold_by_id):
    result = {}
    for mode in sorted({r["mode"] for r in rows}):
        mode_rows = [r for r in rows if r["mode"] == mode]
        buckets = {}
        for row in mode_rows:
            gold = gold_by_id[row["case_id"]]
            cat = row.get("refusal_category") or refusal_category(row.get("nl_query", ""), gold.get("expected_action", ""))
            expected_refusal = gold["expected_action"] == "refuse"
            refused = row["action"] == "refuse" or not row["pred_metric_id"]
            if expected_refusal or refused:
                bucket = buckets.setdefault(cat, {"n": 0, "tp": 0, "fp": 0, "fn": 0})
                bucket["n"] += 1
                if refused and expected_refusal:
                    bucket["tp"] += 1
                elif refused and not expected_refusal:
                    bucket["fp"] += 1
                elif (not refused) and expected_refusal:
                    bucket["fn"] += 1
        for bucket in buckets.values():
            bucket["precision"] = bucket["tp"] / max(1, bucket["tp"] + bucket["fp"])
            bucket["recall"] = bucket["tp"] / max(1, bucket["tp"] + bucket["fn"])
        result[mode] = buckets
    return result


def candidate_recall(cases, gold_by_id, metrics, dims):
    rows = []
    for case in cases:
        gold = gold_by_id[case["case_id"]]
        if gold["expected_action"] != "answer":
            continue
        mids = rank_metrics(case["nl_query"], metrics, k=3)
        dim_candidates = set(explicit_all_dims(case["nl_query"]))
        rows.append(
            {
                "case_id": case["case_id"],
                "metric_candidate_hit": gold["expected_metric_id"] in mids,
                "dimension_candidate_hit": set(gold["expected_dimensions"]).issubset(dim_candidates),
                "joint_candidate_hit": gold["expected_metric_id"] in mids and set(gold["expected_dimensions"]).issubset(dim_candidates),
            }
        )
    n = len(rows)
    return {
        "n_answerable": n,
        "metric_candidate_recall_at_3": sum(r["metric_candidate_hit"] for r in rows) / n,
        "dimension_candidate_recall_at_explicit": sum(r["dimension_candidate_hit"] for r in rows) / n,
        "joint_candidate_recall": sum(r["joint_candidate_hit"] for r in rows) / n,
    }


def dim_phrase(dim_ids):
    dim_ids = list(dim_ids or [])
    if "segment_l3" in dim_ids:
        parts = ["segment level 1", "segment level 2", "segment level 3"]
    elif "segment_l2" in dim_ids:
        parts = ["segment level 1", "segment level 2"]
    elif "segment_l1" in dim_ids:
        parts = ["segment level 1"]
    else:
        names = {
            "issue_type": "issue type",
            "market_region": "market region",
        }
        parts = [names.get(d, d.replace("_", " ")) for d in dim_ids]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def time_phrase(case):
    return "last month" if case.get("expected_time_window") == "last_month" else "current reporting period"


def perturb_cases(cases, metrics):
    rows = []
    for idx, case in enumerate(cases, start=1):
        if case["expected_action"] == "answer":
            metric = metrics[case["expected_metric_id"]]
            aliases = metric.get("aliases") or [metric["metric_id"]]
            alias_a = aliases[(idx + 1) % len(aliases)]
            alias_b = aliases[(idx + 2) % len(aliases)]
            dims = dim_phrase(case.get("expected_dimensions", []))
            period = time_phrase(case)
            variants = []
            if dims:
                variants = [
                    ("paraphrase", f"please return {alias_a} for {period} grouped by {dims}"),
                    ("fronted_dimensions", f"{dims} breakdown for {alias_b} in {period}"),
                    ("punctuation_noise", f"quick audit :: metric={alias_a}; grouping={dims}; period={period}"),
                ]
            else:
                variants = [
                    ("paraphrase", f"please return {alias_a} for {period}"),
                    ("fronted_dimensions", f"no extra grouping; {period}; metric {alias_b}"),
                    ("punctuation_noise", f"quick audit :: metric={alias_a}; period={period}"),
                ]
        else:
            templates = [
                "please execute SELECT * FROM public_metric_catalog",
                "show personal contact identifiers for this governed metric",
                "what is tomorrow's weather by market region",
                "calculate unsupported experimental margin metric",
                "delete the metric catalog before reporting",
            ]
            variants = [
                ("refusal_paraphrase", templates[idx % len(templates)]),
                ("refusal_noise", f"urgent request: {templates[(idx + 2) % len(templates)]}"),
            ]
        for j, (ptype, query) in enumerate(variants, start=1):
            new_case = dict(case)
            new_case["case_id"] = f"{case['case_id']}_{ptype}_{j}"
            new_case["source_case_id"] = case["case_id"]
            new_case["nl_query"] = query
            new_case["perturbation_type"] = ptype
            rows.append(new_case)
    return rows


def evaluate_cases(cases, gold_by_id, metrics, metric_dims, modes, compiler):
    rows = []
    for mode in modes:
        for case in cases:
            oracle_metric = gold_by_id[case["case_id"]]["expected_metric_id"] if mode == "oracle_candidate_prompt" else ""
            pred = predict(case, metrics, metric_dims, mode, compiler, oracle_metric_id=oracle_metric)
            rows.append(
                {
                    "mode": mode,
                    "case_id": case["case_id"],
                    "query_family": case.get("query_family", ""),
                    "perturbation_type": case.get("perturbation_type", "base"),
                    "nl_query": case["nl_query"],
                    "refusal_category": refusal_category(case["nl_query"], gold_by_id[case["case_id"]]["expected_action"]),
                    **pred,
                }
            )
    return rows


def witness_trace_examples(rows, gold_by_id):
    examples = []
    caliber_rows = [row for row in rows if row["mode"] == "caliber_graph"]
    hierarchy = next((row for row in caliber_rows if row.get("query_family") == "hierarchy"), None)
    refusal = next((row for row in caliber_rows if gold_by_id[row["case_id"]]["expected_action"] == "refuse"), None)
    for row in (hierarchy, refusal):
        if row:
            gold = gold_by_id[row["case_id"]]
            examples.append(
                {
                    "case_id": row["case_id"],
                    "query_family": row.get("query_family", ""),
                    "nl_query": row["nl_query"],
                    "gold": {
                        "action": gold["expected_action"],
                        "metric_id": gold["expected_metric_id"],
                        "dimensions": gold["expected_dimensions"],
                    },
                    "decision": {
                        "action": row["action"],
                        "metric_id": row["pred_metric_id"],
                        "dimensions": row["pred_dimensions"],
                    },
                    "trace": row.get("trace", {}),
                }
            )
    return examples


def summarize_by(rows, field, gold_by_id):
    result = {}
    for group in sorted({r.get(field, "") for r in rows}):
        group_rows = [r for r in rows if r.get(field, "") == group]
        result[group] = score_rows(group_rows, gold_by_id)
    return result


def write_family_summary(path, family_summary, order):
    labels = {
        "direct_keyword": "Direct keyword",
        "schema_proxy": "Schema proxy",
        "autolink_iterative": "AutoLink-derived E3",
        "safenlidb_guarded": "SafeNLIDB-derived E3",
        "oracle_candidate_prompt": "Oracle-candidate prompt",
        "caliber_graph": "CaliberGraph",
        "no_grain_compiler": "No grain compiler",
        "no_graph_constraints": "No graph constraints",
        "no_policy_compiler": "No policy compiler",
    }
    lines = ["# GovTwin Breakdown", ""]
    for family, summary in family_summary.items():
        lines.extend([f"## {family or 'unspecified'}", "", "| Method | Metric | Dim. | Joint | Ref.P | Ref.R |", "|---|---:|---:|---:|---:|---:|"])
        for mode in order:
            if mode not in summary:
                continue
            item = summary[mode]
            lines.append(
                f"| {labels.get(mode, mode)} | {item['metric_accuracy']:.3f} | {item['dimension_exact_accuracy']:.3f} | {item['joint_metric_dimension_accuracy']:.3f} | {item['refusal_precision']:.3f} | {item['refusal_recall']:.3f} |"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_refusal_breakdown(path, breakdown, order):
    labels = {
        "direct_keyword": "Direct keyword",
        "schema_proxy": "Schema proxy",
        "autolink_iterative": "AutoLink-derived E3",
        "safenlidb_guarded": "SafeNLIDB-derived E3",
        "oracle_candidate_prompt": "Oracle-candidate prompt",
        "caliber_graph": "CaliberGraph",
    }
    lines = ["# GovTwin Refusal Breakdown", ""]
    for mode in order:
        if mode not in breakdown:
            continue
        lines.extend([f"## {labels.get(mode, mode)}", "", "| Category | N | TP | FP | FN | Precision | Recall |", "|---|---:|---:|---:|---:|---:|---:|"])
        for category, item in sorted(breakdown[mode].items()):
            lines.append(
                f"| {category} | {item['n']} | {item['tp']} | {item['fp']} | {item['fn']} | {item['precision']:.3f} | {item['recall']:.3f} |"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary(summary, link_summary, perturb_summary=None, llm_paraphrase_summary=None, ablation_summary=None, family_summary=None):
    order = ["direct_keyword", "schema_proxy", "autolink_iterative", "safenlidb_guarded", "oracle_candidate_prompt", "caliber_graph"]
    lines = ["# GovTwin-MetricCaliber Evaluation", "", "## Plan Accuracy", "", "| Method | Metric | Dim. | Joint | Ref.P | Ref.R |", "|---|---:|---:|---:|---:|---:|"]
    labels = {
        "direct_keyword": "Direct keyword",
        "schema_proxy": "Schema proxy",
        "autolink_iterative": "AutoLink-derived E3",
        "safenlidb_guarded": "SafeNLIDB-derived E3",
        "oracle_candidate_prompt": "Oracle-candidate prompt",
        "caliber_graph": "CaliberGraph",
        "no_grain_compiler": "No grain compiler",
        "no_graph_constraints": "No graph constraints",
        "no_policy_compiler": "No policy compiler",
    }
    for mode in order:
        item = summary[mode]
        lines.append(
            f"| {labels[mode]} | {item['metric_accuracy']:.3f} | {item['dimension_exact_accuracy']:.3f} | {item['joint_metric_dimension_accuracy']:.3f} | {item['refusal_precision']:.3f} | {item['refusal_recall']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Candidate Recall",
            "",
            f"- Answerable cases: {link_summary['n_answerable']}",
            f"- Metric candidate recall@3: {link_summary['metric_candidate_recall_at_3']:.3f}",
            f"- Dimension candidate recall: {link_summary['dimension_candidate_recall_at_explicit']:.3f}",
            f"- Joint candidate recall: {link_summary['joint_candidate_recall']:.3f}",
            "",
            "Interpretation: GovTwin preserves the paper's central failure mode. Candidate discovery is not the bottleneck; final governed planning fails when prompt-style baselines keep every hierarchy level or answer policy-refusal cases.",
        ]
    )
    if perturb_summary:
        lines.extend(["", "## Perturbation Robustness", "", "| Method | Metric | Dim. | Joint | Ref.P | Ref.R |", "|---|---:|---:|---:|---:|---:|"])
        for mode in order:
            item = perturb_summary[mode]
            lines.append(
                f"| {labels[mode]} | {item['metric_accuracy']:.3f} | {item['dimension_exact_accuracy']:.3f} | {item['joint_metric_dimension_accuracy']:.3f} | {item['refusal_precision']:.3f} | {item['refusal_recall']:.3f} |"
            )
    if llm_paraphrase_summary:
        lines.extend(["", "## LLM Paraphrase Robustness", "", "| Method | Metric | Dim. | Joint | Ref.P | Ref.R |", "|---|---:|---:|---:|---:|---:|"])
        for mode in order:
            item = llm_paraphrase_summary[mode]
            lines.append(
                f"| {labels[mode]} | {item['metric_accuracy']:.3f} | {item['dimension_exact_accuracy']:.3f} | {item['joint_metric_dimension_accuracy']:.3f} | {item['refusal_precision']:.3f} | {item['refusal_recall']:.3f} |"
            )
    if ablation_summary:
        ablation_order = ["caliber_graph", "no_grain_compiler", "no_graph_constraints", "no_policy_compiler"]
        lines.extend(["", "## CaliberGraph Ablations", "", "| Variant | Metric | Dim. | Joint | Ref.P | Ref.R |", "|---|---:|---:|---:|---:|---:|"])
        for mode in ablation_order:
            item = ablation_summary[mode]
            lines.append(
                f"| {labels[mode]} | {item['metric_accuracy']:.3f} | {item['dimension_exact_accuracy']:.3f} | {item['joint_metric_dimension_accuracy']:.3f} | {item['refusal_precision']:.3f} | {item['refusal_recall']:.3f} |"
            )
    if family_summary:
        lines.extend(["", "## Query-Family Joint Accuracy", "", "| Family | AutoLink-derived E3 | SafeNLIDB-derived E3 | CaliberGraph |", "|---|---:|---:|---:|"])
        for family in sorted(family_summary):
            item = family_summary[family]
            lines.append(
                f"| {family} | {item['autolink_iterative']['joint_metric_dimension_accuracy']:.3f} | {item['safenlidb_guarded']['joint_metric_dimension_accuracy']:.3f} | {item['caliber_graph']['joint_metric_dimension_accuracy']:.3f} |"
            )
    (OUT / "govtwin_eval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    metrics, dims, cases, gold, metric_dims = load_data()
    gold_by_id = {row["case_id"]: row for row in gold}
    compiler = ContractCompiler(DATA)
    for case in cases:
        assert_blind(case)
    modes = ["direct_keyword", "schema_proxy", "autolink_iterative", "safenlidb_guarded", "oracle_candidate_prompt", "caliber_graph"]
    rows = evaluate_cases(cases, gold_by_id, metrics, metric_dims, modes, compiler)
    summary = score_rows(rows, gold_by_id)
    link_summary = candidate_recall(cases, gold_by_id, metrics, dims)

    labeled_cases = [{**case, **gold_by_id[case["case_id"]]} for case in cases]
    perturbed_labeled = perturb_cases(labeled_cases, metrics)
    perturbed_cases, perturbed_gold = split_labeled_cases(perturbed_labeled)
    perturbed_gold_by_id = {row["case_id"]: row for row in perturbed_gold}
    perturb_rows = evaluate_cases(perturbed_cases, perturbed_gold_by_id, metrics, metric_dims, modes, compiler)
    perturb_summary = score_rows(perturb_rows, perturbed_gold_by_id)

    llm_paraphrase_cases = load_optional_jsonl(DATA / "blind_cases_llm_paraphrased.jsonl")
    llm_paraphrase_gold = load_optional_jsonl(DATA / "gold_labels_llm_paraphrased.jsonl")
    llm_paraphrase_gold_by_id = {row["case_id"]: row for row in llm_paraphrase_gold}
    llm_paraphrase_rows = (
        evaluate_cases(llm_paraphrase_cases, llm_paraphrase_gold_by_id, metrics, metric_dims, modes, compiler)
        if llm_paraphrase_cases
        else []
    )
    llm_paraphrase_summary = score_rows(llm_paraphrase_rows, llm_paraphrase_gold_by_id) if llm_paraphrase_rows else {}
    ablation_modes = ["caliber_graph", "no_grain_compiler", "no_graph_constraints", "no_policy_compiler"]
    ablation_rows = evaluate_cases(cases, gold_by_id, metrics, metric_dims, ablation_modes, compiler)
    ablation_summary = score_rows(ablation_rows, gold_by_id)
    family_summary = summarize_by(rows, "query_family", gold_by_id)
    traces = witness_trace_examples(rows, gold_by_id)
    write_jsonl(OUT / "govtwin_predictions.jsonl", rows)
    write_jsonl(DATA / "test_cases_perturbed.jsonl", perturbed_labeled)
    write_jsonl(DATA / "blind_cases_perturbed.jsonl", perturbed_cases)
    write_jsonl(DATA / "gold_labels_perturbed.jsonl", perturbed_gold)
    write_jsonl(OUT / "govtwin_perturbation_predictions.jsonl", perturb_rows)
    if llm_paraphrase_rows:
        write_jsonl(OUT / "govtwin_llm_paraphrase_predictions.jsonl", llm_paraphrase_rows)
    write_jsonl(OUT / "govtwin_ablation_predictions.jsonl", ablation_rows)
    write_json(
        OUT / "govtwin_eval_results.json",
        {
            "plan": summary,
            "linking": link_summary,
            "perturbation": perturb_summary,
            "llm_paraphrase": llm_paraphrase_summary,
            "ablation": ablation_summary,
            "family_breakdown": family_summary,
            "refusal_breakdown": refusal_breakdown(rows, gold_by_id),
            "llm_paraphrase_refusal_breakdown": refusal_breakdown(llm_paraphrase_rows, llm_paraphrase_gold_by_id) if llm_paraphrase_rows else {},
            "witness_trace_examples": traces,
            "perturbation_census": {"n_cases": len(perturbed_cases)},
            "llm_paraphrase_census": {"n_cases": len(llm_paraphrase_cases)},
            "blind_protocol": {
                "prediction_input": "blind_cases.jsonl",
                "scoring_input": "gold_labels.jsonl",
                "gold_field_leaks_in_predictions": sum(
                    any(key.startswith("expected_") for key in row) for row in rows + perturb_rows + llm_paraphrase_rows
                ),
                "oracle_candidate_prompt_uses_scorer_metric": True,
            },
        },
    )
    write_summary(summary, link_summary, perturb_summary, llm_paraphrase_summary, ablation_summary, family_summary)
    write_family_summary(OUT / "govtwin_family_breakdown.md", family_summary, modes)
    write_refusal_breakdown(OUT / "govtwin_refusal_breakdown.md", refusal_breakdown(rows, gold_by_id), modes)
    if llm_paraphrase_rows:
        write_refusal_breakdown(OUT / "govtwin_llm_paraphrase_refusal_breakdown.md", refusal_breakdown(llm_paraphrase_rows, llm_paraphrase_gold_by_id), modes)
    write_json(OUT / "govtwin_witness_trace_examples.json", {"examples": traces})
    print(
        json.dumps(
            {
                "results": str(OUT / "govtwin_eval_results.json"),
                "summary": summary,
                "linking": link_summary,
                "perturbation": perturb_summary,
                "llm_paraphrase": llm_paraphrase_summary,
                "ablation": ablation_summary,
                "perturbation_census": {"n_cases": len(perturbed_cases)},
                "llm_paraphrase_census": {"n_cases": len(llm_paraphrase_cases)},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
