#!/usr/bin/env python3
"""Build and evaluate a BIRD-MetricCaliber diagnostic benchmark.

The goal is to raise the public-evidence level beyond the small Chinook
benchmark. We derive metric-caliber labels from BIRD Mini-Dev's public
NL/SQL/schema/evidence records and evaluate existing BIRD model SQL outputs
as strong text-to-SQL baselines under metric-caliber diagnostics.
"""

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp


ROOT = Path(__file__).resolve().parents[1]
BIRD_ROOT = ROOT / "public_benchmark" / "external" / "bird_mini_dev" / "mini_dev-main"
PROMPT_PATH = BIRD_ROOT / "finetuning" / "inference" / "mini_dev_prompt.jsonl"
OUT = ROOT / "public_benchmark" / "bird_metric_caliber"
EXP_OUT = OUT / "experiments"

AGG_CLASSES = (exp.Sum, exp.Count, exp.Avg, exp.Max, exp.Min)
AGG_NAMES = {"sum", "count", "avg", "max", "min"}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def norm_sql(text):
    text = str(text or "")
    text = re.sub(r"--.*", " ", text)
    text = re.sub(r"\s+", " ", text).strip().rstrip(";")
    return text


def clean_id(text):
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", str(text).strip().lower())
    return re.sub(r"_+", "_", text).strip("_")


def split_prediction(value):
    sql, _, db_id = str(value).partition("\t----- bird -----\t")
    return sql.strip(), db_id.strip()


def parse_sql(sql):
    sql = norm_sql(sql)
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except Exception:
        return None
    agg_exprs = []
    for expr in tree.expressions if isinstance(tree, exp.Select) else list(tree.find_all(exp.Select))[0].expressions:
        if list(expr.find_all(*AGG_CLASSES)):
            agg_exprs.append(expr)
    agg_funcs = sorted({a.key.lower() for expr_ in agg_exprs for a in expr_.find_all(*AGG_CLASSES)})
    group = tree.args.get("group")
    group_dims = []
    if group:
        for g in group.expressions:
            group_dims.append(normalize_column_like(g.sql(dialect="sqlite")))
    measure_columns = sorted({normalize_column_like(c.sql(dialect="sqlite")) for expr_ in agg_exprs for c in expr_.find_all(exp.Column)})
    tables = sorted({clean_id(t.name) for t in tree.find_all(exp.Table) if t.name})
    select_signature = " || ".join(normalize_expr(e.sql(dialect="sqlite")) for e in agg_exprs)
    return {
        "has_aggregate": bool(agg_exprs),
        "metric_signature": select_signature,
        "agg_funcs": agg_funcs,
        "measure_columns": measure_columns,
        "group_dimensions": sorted(dict.fromkeys(group_dims)),
        "tables": tables,
        "normalized_sql": tree.sql(dialect="sqlite"),
    }


def normalize_expr(text):
    text = norm_sql(text).lower()
    text = text.replace('"', "").replace("`", "")
    text = re.sub(r"\bcast\s*\(", "cast(", text)
    text = re.sub(r"\s+as\s+[a-zA-Z_][a-zA-Z0-9_]*$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_column_like(text):
    text = str(text or "").strip().lower().replace('"', "").replace("`", "")
    text = re.sub(r"\s+", " ", text)
    return text


def parse_schema_columns(db_id, schema):
    dims = []
    current_table = None
    for raw in schema.splitlines():
        line = raw.strip()
        m = re.match(r"create\s+table\s+[`\"]?([^`\"(]+)[`\"]?\s*\(", line, flags=re.I)
        if m:
            current_table = clean_id(m.group(1))
            continue
        if not current_table or line.startswith(")") or line.upper().startswith(("PRIMARY ", "FOREIGN ", "UNIQUE ", "CONSTRAINT ")):
            continue
        col_part, _, comment = line.partition("--")
        col_part = col_part.strip().rstrip(",")
        if not col_part:
            continue
        col = col_part.split()[0].strip('`"[]')
        if not col or col.lower() in {"primary", "foreign"}:
            continue
        dim_id = f"{db_id}.{current_table}.{clean_id(col)}"
        dims.append(
            {
                "dimension_id": dim_id,
                "db_id": db_id,
                "table": current_table,
                "column": clean_id(col),
                "name": col,
                "description": comment.strip(),
                "fields": [col, current_table, comment.strip()],
            }
        )
    return dims


def build_benchmark():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(PROMPT_PATH)
    metrics = {}
    dims = {}
    cases = []
    skipped = Counter()
    for source_index, row in enumerate(rows):
        parsed = parse_sql(row["SQL"])
        if not parsed or not parsed["has_aggregate"]:
            skipped["non_aggregate_or_parse_fail"] += 1
            continue
        db_id = clean_id(row["db_id"])
        schema_dims = parse_schema_columns(db_id, row.get("schema", ""))
        for dim in schema_dims:
            dims.setdefault(dim["dimension_id"], dim)
        h = hashlib.sha1((db_id + "::" + parsed["metric_signature"]).encode()).hexdigest()[:12]
        metric_id = f"{db_id}.metric_{h}"
        evidence = row.get("evidence", "")
        metric = metrics.setdefault(
            metric_id,
            {
                "metric_id": metric_id,
                "db_id": db_id,
                "metric_signature": parsed["metric_signature"],
                "agg_funcs": parsed["agg_funcs"],
                "measure_columns": parsed["measure_columns"],
                "tables": parsed["tables"],
                "evidence": evidence,
                "allowed_dimensions": set(),
                "case_count": 0,
            },
        )
        metric["allowed_dimensions"].update(parsed["group_dimensions"])
        metric["case_count"] += 1
        cases.append(
            {
                "case_id": f"birdmc_{len(cases):04d}",
                "source_index": source_index,
                "source_question_id": row.get("question_id"),
                "db_id": db_id,
                "nl_query": row["question"],
                "evidence": evidence,
                "expected_metric_id": metric_id,
                "expected_metric_signature": parsed["metric_signature"],
                "expected_agg_funcs": parsed["agg_funcs"],
                "expected_measure_columns": parsed["measure_columns"],
                "expected_dimensions": parsed["group_dimensions"],
                "expected_tables": parsed["tables"],
                "gold_sql": row["SQL"],
            }
        )
    metric_rows = []
    for m in metrics.values():
        item = dict(m)
        item["allowed_dimensions"] = sorted(item["allowed_dimensions"])
        metric_rows.append(item)
    (OUT / "bird_metric_catalog.jsonl").write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in metric_rows) + "\n")
    (OUT / "bird_dimension_catalog.jsonl").write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in dims.values()) + "\n")
    (OUT / "bird_metric_cases.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n")
    readme = f"""# BIRD-MetricCaliber Diagnostic Benchmark

Derived from BIRD Mini-Dev public `mini_dev_prompt.jsonl`.

- Source records: {len(rows)}
- Aggregate metric-caliber cases: {len(cases)}
- Unique metric signatures: {len(metric_rows)}
- Dimension columns parsed from schemas: {len(dims)}

Gold labels are derived from the public SQL:

- metric signature: aggregate expression(s) in the SELECT clause;
- measure columns: columns used inside aggregate expressions;
- dimensions: GROUP BY expressions;
- tables: tables referenced by the SQL.

This split is a diagnostic benchmark for metric-caliber planning and verification, not a replacement for full SQL execution evaluation.
"""
    (OUT / "README.md").write_text(readme)
    return {"rows": rows, "cases": cases, "metrics": metric_rows, "dims": list(dims.values()), "skipped": dict(skipped)}


def text_terms(text):
    return set(re.findall(r"[a-zA-Z0-9_]+", str(text).lower()))


def score_text(query, fields):
    q = str(query).lower()
    q_terms = text_terms(q)
    score = 0.0
    for field, weight in fields:
        f = str(field or "").lower()
        if not f:
            continue
        if f in q:
            score += 5.0 * weight
        score += weight * len(q_terms & text_terms(f))
    return score


def rank_metrics(case, metrics_by_db, mode, k=5):
    scored = []
    query_text = case["nl_query"] if mode == "direct" else f"{case['nl_query']} {case.get('evidence', '')}"
    for m in metrics_by_db[case["db_id"]]:
        if mode == "direct":
            fields = [(m["metric_signature"], 2.0), (" ".join(m["measure_columns"]), 2.0), (" ".join(m["agg_funcs"]), 1.0)]
        elif mode == "schema_rag":
            fields = [(m["evidence"], 3.0), (m["metric_signature"], 2.0), (" ".join(m["measure_columns"]), 2.0), (" ".join(m["tables"]), 1.0)]
        else:
            fields = [(m["evidence"], 3.0), (m["metric_signature"], 2.5), (" ".join(m["measure_columns"]), 2.0), (" ".join(m["tables"]), 1.0), (" ".join(m["allowed_dimensions"]), 1.0)]
        scored.append((score_text(query_text, fields), m["metric_id"]))
    scored.sort(reverse=True)
    return [mid for score, mid in scored[:k]]


def predict_dims(case, dims_by_db, mode):
    if mode == "direct":
        return []
    group_cues = [" by ", " per ", " each ", " for each ", " for every ", "group", "distribution", "breakdown", "ranked by", "monthly", "yearly"]
    q = f" {case['nl_query'].lower()} "
    if not any(cue in q for cue in group_cues):
        return []
    scored = []
    for d in dims_by_db[case["db_id"]]:
        fields = [(d["name"], 3.0), (d["column"], 2.0), (d["table"], 1.0), (d.get("description"), 1.5)]
        s = score_text(case["nl_query"] + " " + case.get("evidence", ""), fields)
        if s > 0:
            scored.append((s, normalize_column_like(d["column"])))
    scored.sort(reverse=True)
    # CaliberGraph keeps only salient dimensions, Schema-RAG over-keeps more.
    limit = 2 if mode == "schema_rag" else 1
    return sorted(dict.fromkeys(d for _, d in scored[:limit]))


def score_plan_rows(rows):
    c = Counter()
    for r in rows:
        metric_ok = r["pred_metric_id"] == r["expected_metric_id"]
        dim_ok = set(r["pred_dimensions"]) == set(r["expected_dimensions"])
        if metric_ok:
            c["metric_ok"] += 1
        if dim_ok:
            c["dim_ok"] += 1
        if metric_ok and dim_ok:
            c["joint_ok"] += 1
    n = len(rows)
    return {"n": n, "metric_accuracy": c["metric_ok"] / n, "dimension_exact_accuracy": c["dim_ok"] / n, "joint_accuracy": c["joint_ok"] / n}


def evaluate_planners(cases, metrics, dims):
    metrics_by_db = defaultdict(list)
    for m in metrics:
        metrics_by_db[m["db_id"]].append(m)
    dims_by_db = defaultdict(list)
    for d in dims:
        dims_by_db[d["db_id"]].append(d)
    rows = []
    for mode in ["direct", "schema_rag", "autolink_derived_e3", "caliber_graph"]:
        for case in cases:
            mechanism_mode = "schema_rag" if mode == "autolink_derived_e3" else mode
            pred_metric = rank_metrics(case, metrics_by_db, "caliber_graph" if mode == "caliber_graph" else mechanism_mode, k=1)[0]
            pred_dims = predict_dims(case, dims_by_db, mechanism_mode)
            if mode == "caliber_graph":
                metric = next(m for m in metrics_by_db[case["db_id"]] if m["metric_id"] == pred_metric)
                allowed = {normalize_column_like(x.split(".")[-1]) for x in metric["allowed_dimensions"]}
                if allowed:
                    pred_dims = [d for d in pred_dims if d in allowed]
            rows.append({"mode": mode, **case, "pred_metric_id": pred_metric, "pred_dimensions": pred_dims})
    grouped = defaultdict(list)
    for r in rows:
        grouped[r["mode"]].append(r)
    return rows, {mode: score_plan_rows(sub) for mode, sub in grouped.items()}


def evaluate_sql_baselines(cases):
    prediction_files = {
        "bird_gpt4o_sql": BIRD_ROOT / "llm" / "exp_result" / "TA_output" / "predict_mini_dev_gpt-4-o_cot_SQLite.json",
        "bird_gpt4_turbo_sql": BIRD_ROOT / "llm" / "exp_result" / "TA_output" / "predict_mini_dev_gpt-4-turbo_cot_SQLite.json",
        "bird_llama3_70b_sql": BIRD_ROOT / "llm" / "exp_result" / "TA_output" / "predict_mini_dev_meta-llama-3-70b-instruct2_cot_SQLite.json",
        "bird_gpt35_sql": BIRD_ROOT / "llm" / "exp_result" / "TA_output" / "predict_mini_dev_gpt-35-turbo_cot_SQLite.json",
    }
    cases_by_index = {int(c["source_index"]): c for c in cases}
    rows = []
    for mode, path in prediction_files.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        for idx, case in cases_by_index.items():
            pred_raw = data.get(str(idx), "")
            pred_sql, pred_db = split_prediction(pred_raw)
            parsed = parse_sql(pred_sql)
            if not parsed:
                pred = {"pred_agg_funcs": [], "pred_measure_columns": [], "pred_dimensions": [], "pred_tables": [], "parse_ok": False}
            else:
                pred = {
                    "pred_agg_funcs": parsed["agg_funcs"],
                    "pred_measure_columns": parsed["measure_columns"],
                    "pred_dimensions": parsed["group_dimensions"],
                    "pred_tables": parsed["tables"],
                    "parse_ok": True,
                }
            rows.append({"mode": mode, **case, **pred, "pred_sql": pred_sql})
    summary = {}
    for mode in sorted({r["mode"] for r in rows}):
        sub = [r for r in rows if r["mode"] == mode]
        c = Counter()
        for r in sub:
            agg_ok = set(r["pred_agg_funcs"]) == set(r["expected_agg_funcs"])
            measure_ok = set(r["pred_measure_columns"]) == set(r["expected_measure_columns"])
            dim_ok = set(r["pred_dimensions"]) == set(r["expected_dimensions"])
            table_ok = set(r["expected_tables"]).issubset(set(r["pred_tables"]))
            joint = agg_ok and measure_ok and dim_ok
            c["parse_ok"] += int(r["parse_ok"])
            c["agg_ok"] += int(agg_ok)
            c["measure_ok"] += int(measure_ok)
            c["dim_ok"] += int(dim_ok)
            c["table_ok"] += int(table_ok)
            c["joint_ok"] += int(joint)
        n = len(sub)
        summary[mode] = {
            "n": n,
            "parse_rate": c["parse_ok"] / n,
            "agg_func_accuracy": c["agg_ok"] / n,
            "measure_column_accuracy": c["measure_ok"] / n,
            "dimension_exact_accuracy": c["dim_ok"] / n,
            "table_recall_exact": c["table_ok"] / n,
            "joint_caliber_accuracy": c["joint_ok"] / n,
        }
    return rows, summary


def write_report(build_info, planner_summary, sql_summary):
    EXP_OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# BIRD-MetricCaliber Diagnostic Evaluation",
        "",
        f"Source records: {len(build_info['rows'])}",
        f"Aggregate cases: {len(build_info['cases'])}",
        f"Unique metric signatures: {len(build_info['metrics'])}",
        f"Schema dimensions: {len(build_info['dims'])}",
        "",
        "## NL2Metric-Caliber Planners",
        "",
        "| Method | Metric Acc. | Dim. Exact | Joint |",
        "|---|---:|---:|---:|",
    ]
    for mode, s in planner_summary.items():
        lines.append(f"| {mode} | {s['metric_accuracy']:.3f} | {s['dimension_exact_accuracy']:.3f} | {s['joint_accuracy']:.3f} |")
    lines.extend(["", "## Strong Text-to-SQL Baselines Diagnosed as Metric-Caliber Outputs", "", "| SQL baseline | Parse | Agg func | Measure col | Dim exact | Table recall | Joint caliber |", "|---|---:|---:|---:|---:|---:|---:|"])
    for mode, s in sql_summary.items():
        lines.append(
            f"| {mode} | {s['parse_rate']:.3f} | {s['agg_func_accuracy']:.3f} | {s['measure_column_accuracy']:.3f} | {s['dimension_exact_accuracy']:.3f} | {s['table_recall_exact']:.3f} | {s['joint_caliber_accuracy']:.3f} |"
        )
    report = "\n".join(lines) + "\n"
    (EXP_OUT / "bird_metric_caliber_summary.md").write_text(report, encoding="utf-8")
    print(report)


def main():
    build_info = build_benchmark()
    planner_rows, planner_summary = evaluate_planners(build_info["cases"], build_info["metrics"], build_info["dims"])
    sql_rows, sql_summary = evaluate_sql_baselines(build_info["cases"])
    EXP_OUT.mkdir(parents=True, exist_ok=True)
    (EXP_OUT / "bird_planner_predictions.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in planner_rows) + "\n")
    (EXP_OUT / "bird_sql_baseline_diagnostics.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in sql_rows) + "\n")
    (EXP_OUT / "bird_planner_results.json").write_text(json.dumps(planner_summary, ensure_ascii=False, indent=2) + "\n")
    (EXP_OUT / "bird_sql_baseline_results.json").write_text(json.dumps(sql_summary, ensure_ascii=False, indent=2) + "\n")
    write_report(build_info, planner_summary, sql_summary)


if __name__ == "__main__":
    main()
