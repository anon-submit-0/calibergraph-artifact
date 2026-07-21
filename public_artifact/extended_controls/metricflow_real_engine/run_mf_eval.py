#!/usr/bin/env python3
"""Run the 32 IowaLiquor-MetricCaliber cases against the real MetricFlow engine.

Modes (pre-registered in protocol.md section 4):
  - metricflow_lexical: verbatim lexical linker from the released run_iowa_liquor_eval.py
    (rank_metrics top-1 + explicit_dims) -> `mf query`; engine exit code decides answer/refuse.
  - metricflow_oracle_metric: gold metric for answerable cases (dims still lexical); fixed
    literal-intent structured queries for refusal cases; engine exit code decides.

Scoring mirrors score() from the released scorer byte-for-byte in semantics.
Every mf invocation's full stdout/stderr is preserved under raw_outputs/<mode>/<case_id>.txt.
"""

import csv
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

RUN_ROOT = Path(__file__).resolve().parent
BENCH = RUN_ROOT.parents[2] / "public_artifact" / "public_benchmark" / "iowa_liquor_metric_caliber"
DBT_PROJECT = RUN_ROOT / "dbt_project"
RAW = RUN_ROOT / "raw_outputs"
RESULTS = RUN_ROOT / "results"
MF_BIN = sys.argv[1] if len(sys.argv) > 1 else "mf"

# ---------------------------------------------------------------------------
# Lexical linker: copied VERBATIM from public_artifact/scripts/run_iowa_liquor_eval.py
# (functions norm, split_terms, char_bigrams, text_score, rank_metrics, explicit_dims).
# ---------------------------------------------------------------------------


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def norm(value):
    return "" if value is None else str(value).strip()


def split_terms(text):
    text = norm(text).lower()
    return set(re.findall(r"[a-z0-9_]+", text) + re.findall(r"[一-鿿]{2,}", text))


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


# ---------------------------------------------------------------------------
# Pre-registered fixed mappings (protocol.md section 4)
# ---------------------------------------------------------------------------

DIM_TO_MF = {
    "ordered_month": "metric_time__month",
    "ordered_quarter": "metric_time__quarter",
    "county_name": "sale_line__county_name",
    "store_city": "sale_line__store_city",
    "store_name": "sale_line__store_name",
    "category_name": "sale_line__category_name",
    "vendor_name": "sale_line__vendor_name",
    "item_desc": "sale_line__item_desc",
}
MF_TO_DIM = {v: k for k, v in DIM_TO_MF.items()}

ORACLE_REFUSAL_QUERIES = {
    "iowa_026": ("invoice_count", ["sale_line__invoice_id"]),
    "iowa_027": ("store_count", ["sale_line__store_address"]),
    "iowa_028": ("DROP TABLE iowa_liquor_sales", []),
    "iowa_029": ("weather", []),
    "iowa_030": ("profit_margin", ["sale_line__category_name"]),
    "iowa_031": ("profit_margin", ["sale_line__vendor_name"]),
    "iowa_032": ("customer_phone_numbers", []),
}

ERROR_PATTERNS = [
    # Exact phrasings observed from metricflow 0.211.0 (see raw_outputs/*):
    ("unknown_metric_name", r"(?i)does not exactly match any known metrics"),
    ("unknown_group_by_item", r"(?i)does not match any of the available group-by-items"),
    ("parse_error", r"(?i)(unable to parse|parsing|invalid query|error parsing)"),
]


def categorize_error(text):
    for name, pat in ERROR_PATTERNS:
        if re.search(pat, text, flags=re.DOTALL):
            return name
    return "engine_error_other"


def run_mf(metric_id, mf_group_bys, log_path):
    """One real mf invocation. Returns (exit_code, n_data_rows, error_category, wall_seconds)."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        csv_path = Path(tf.name)
    cmd = [MF_BIN, "query", "--metrics", metric_id, "--limit", "20", "--csv", str(csv_path)]
    if mf_group_bys:
        cmd.extend(["--group-by", ",".join(mf_group_bys)])
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=DBT_PROJECT, capture_output=True, text=True, timeout=600,
                          env={**__import__("os").environ, "DBT_PROFILES_DIR": str(DBT_PROJECT)})
    wall = round(time.time() - t0, 2)
    n_rows = 0
    if proc.returncode == 0 and csv_path.exists():
        try:
            with open(csv_path, newline="") as f:
                n_rows = max(0, sum(1 for _ in csv.reader(f)) - 1)
        except Exception:
            n_rows = 0
    err_cat = "" if proc.returncode == 0 else categorize_error(proc.stdout + "\n" + proc.stderr)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND: " + " ".join(cmd) + f"\nEXIT_CODE: {proc.returncode}\nWALL_SECONDS: {wall}\n"
        f"DATA_ROWS: {n_rows}\nERROR_CATEGORY: {err_cat}\n"
        "----- STDOUT -----\n" + proc.stdout + "\n----- STDERR -----\n" + proc.stderr + "\n",
        encoding="utf-8",
    )
    csv_path.unlink(missing_ok=True)
    return proc.returncode, n_rows, err_cat, wall


# ---------------------------------------------------------------------------
# Scoring: mirrors score() from the released run_iowa_liquor_eval.py
# ---------------------------------------------------------------------------


def score(rows):
    summary = {}
    for mode in sorted({r["mode"] for r in rows}):
        subset = [r for r in rows if r["mode"] == mode]
        counts = Counter()
        for row in subset:
            expected_refusal = row["expected_action"] == "refuse"
            refused = row["action"] == "refuse" or not row["pred_metric_id"]
            metric_ok = row["pred_metric_id"] == row["expected_metric_id"]
            dim_ok = set(row["pred_dimensions"]) == set(row["expected_dimensions"])
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


def main():
    metrics = {m["metric_id"]: m for m in read_jsonl(BENCH / "metric_catalog.jsonl")}
    for metric in metrics.values():
        metric["fields"] = [
            (metric.get("metric_id"), 2.5),
            (metric.get("metric_name"), 3.0),
            (metric.get("formula"), 1.0),
            (metric.get("description"), 1.0),
            *[(alias, 2.5) for alias in metric.get("aliases", [])],
        ]
    cases = read_jsonl(BENCH / "test_cases.jsonl")

    rows = []
    for mode in ["metricflow_lexical", "metricflow_oracle_metric"]:
        for case in cases:
            q = case["nl_query"]
            record = {
                "mode": mode,
                "case_id": case["case_id"],
                "nl_query": q,
                "expected_action": case["expected_action"],
                "expected_metric_id": case["expected_metric_id"],
                "expected_dimensions": case["expected_dimensions"],
            }
            # --- build the structured query ---
            if mode == "metricflow_lexical":
                ranked = rank_metrics(q, metrics, k=5, direct=False)
                metric_id = ranked[0] if ranked else ""
                catalog_dims = explicit_dims(q)
                mf_dims = [DIM_TO_MF[d] for d in catalog_dims]
            else:
                if case["expected_action"] == "answer":
                    metric_id = case["expected_metric_id"]
                    catalog_dims = explicit_dims(q)
                    mf_dims = [DIM_TO_MF[d] for d in catalog_dims]
                else:
                    metric_id, mf_dims = ORACLE_REFUSAL_QUERIES[case["case_id"]]
                    catalog_dims = [MF_TO_DIM.get(g, g) for g in mf_dims]

            if not metric_id:
                record.update(
                    action="refuse", pred_metric_id="", pred_dimensions=[],
                    reason="no_metric_candidate_from_lexical_linker", mf_command="", mf_exit_code=None,
                    error_category="", execute_ok=None, data_row_count=0, wall_seconds=0.0,
                )
                rows.append(record)
                print(f"{mode} {case['case_id']}: linker refuse (no candidate)")
                continue

            # --- real engine invocation ---
            log_path = RAW / mode / f"{case['case_id']}.txt"
            exit_code, n_rows, err_cat, wall = run_mf(metric_id, mf_dims, log_path)
            cmd_str = f"mf query --metrics {metric_id}" + (f" --group-by {','.join(mf_dims)}" if mf_dims else "")
            if exit_code == 0:
                record.update(
                    action="answer", pred_metric_id=metric_id, pred_dimensions=catalog_dims,
                    reason="engine_compiled_and_executed", mf_command=cmd_str, mf_exit_code=exit_code,
                    error_category="", execute_ok=True, data_row_count=n_rows, wall_seconds=wall,
                )
            else:
                record.update(
                    action="refuse", pred_metric_id="", pred_dimensions=[],
                    reason=f"engine_rejected:{err_cat}", mf_command=cmd_str, mf_exit_code=exit_code,
                    error_category=err_cat, execute_ok=None, data_row_count=0, wall_seconds=wall,
                )
            rows.append(record)
            print(f"{mode} {case['case_id']}: exit={exit_code} rows={n_rows} {err_cat}")

    summary = score(rows)

    baseline = json.loads((BENCH / "results" / "iowa_liquor_eval_results.json").read_text(encoding="utf-8"))
    payload = {
        "engine": "metricflow 0.211.0 (Apache-2.0) + dbt-metricflow 0.13.0 + dbt-core 1.11.12 + dbt-duckdb 1.10.1 / duckdb 1.5.4",
        "warehouse_note": "benchmark SQLite snapshot copied to DuckDB (no SQLite adapter in MetricFlow); parity checks in translation/data_parity.json",
        "metricflow_modes": summary,
        "released_baselines_for_comparison": baseline["plan"],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "per_case_results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n", encoding="utf-8"
    )
    (RESULTS / "scores.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
