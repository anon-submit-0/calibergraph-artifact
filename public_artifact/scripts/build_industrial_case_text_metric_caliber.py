#!/usr/bin/env python3
"""Build a public desensitized industrial case-text benchmark.

The source cases are real enterprise NL2Metric-Caliber cases. The release keeps
desensitized natural query text and gold labels, but replaces internal domain,
metric, dimension, caliber, product, and source identifiers with public IDs.
"""

from __future__ import annotations

import hashlib
import json
import re
import argparse
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_PRIVATE = ROOT / "experiments" / "enterprise_metric_cases.jsonl"
SRC_PUBLIC = ROOT / "experiments" / "enterprise_metric_cases_public_desensitized.jsonl"
SRC_PUBLIC_LABELS = ROOT / "experiments" / "enterprise_metric_cases_public_desensitized_labels.jsonl"
OUT = ROOT / "public_benchmark" / "industrial_case_text_metric_caliber"
SRC_PUBLIC_BENCHMARK = OUT / "source_candidates_public_desensitized.jsonl"
SRC_PUBLIC_BENCHMARK_LABELS = OUT / "source_candidate_labels_public_desensitized.jsonl"
RESULTS = OUT / "results"
INTERNAL_TRACE = ROOT.parent / ("internal" + "_author" + "_evidence") / "industrial_case_text_metric_caliber"

METRIC_META = {
    "sale_amount_usd": ("Sales Amount", ["销售额", "sales amount", "revenue"]),
    "sale_qty": ("Sales Quantity", ["销量", "sales quantity", "units sold"]),
    "problem_cnt": ("Issue Count", ["问题次数", "issue count", "problem count"]),
    "rma_order_count": ("After-Sales Case Count", ["售后单数", "客诉数", "after-sales case count"]),
    "category_complaint_rate": ("Category Complaint Rate", ["客诉率", "品类问题率", "品类问题", "complaint rate"]),
    "quality_problem_ratio": ("Quality Defect Rate", ["质量不良率", "质量问题比例", "Quality issue问题占比", "defect rate", "quality issue ratio"]),
    "resend_rate": ("Reshipment Share", ["补发占比", "补发率", "reshipment share", "resend rate"]),
    "sku_complaint_rate": ("Item Complaint Rate", ["SKU客诉率", "商品客诉率", "item complaint rate"]),
    "return_qty": ("Return Quantity", ["退货量", "return quantity"]),
    "return_rate": ("Return Rate", ["退货率", "return rate"]),
    "refund_amount_usd": ("Refund Amount", ["退款金额", "refund amount"]),
    "refund_rate": ("Refund Rate", ["退款率", "refund rate"]),
    "problem_product_qty": ("Defective Item Quantity", ["问题品", "问题品数量", "defective item quantity"]),
    "reship_qty": ("Reshipment Quantity", ["补发量", "reshipment quantity"]),
    "product_reship_loss_usd": ("Reshipment Loss", ["补发损失", "reshipment loss"]),
}

DIM_MAP = {
    "category_l1": ("segment_l1", "Segment Level 1", ["一级品类", "level 1 segment", "segment level 1"]),
    "category_l2": ("segment_l2", "Segment Level 2", ["二级品类", "level 2 segment", "segment level 2"]),
    "category_l3": ("segment_l3", "Segment Level 3", ["三级品类", "level 3 segment", "segment level 3"]),
    "region": ("market_region", "Market Region", ["区域", "region", "market region"]),
}

TIME_MAP = {
    "last_month": "last_month",
    "this_year": "this_year",
    "last_30_days": "last_30_days",
    "last_7_days": "last_7_days",
    "last_year": "last_year",
    "this_month": "this_month",
    "today": "today",
    "yesterday": "yesterday",
    "last_quarter": "last_quarter",
    "quarter_explicit": "explicit_quarter",
    "this_quarter": "this_quarter",
    "": "unspecified",
}

CALIBER_MAP = {
    "rma_created": "case_created_caliber",
    "cross_caliber": "cross_caliber",
    "": "not_applicable",
}

PRODUCT_REPLACEMENTS = {
    "TV Cabinets": "Product Family A",
    "Office Chair": "Product Family B",
    "Mattresses": "Product Family C",
    "Heat Gun": "Product Family D",
    "Pallet Trucks": "Product Family E",
    "Gaming Chair": "Product Family F",
    "Standing Desks": "Product Family G",
}

SENSITIVE_PATTERNS = [
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"\b\d{6,}\b"),
]

PRIVATE_TERMS = [
    "private_company_token",
    "private_domain_token",
    "private_metric_token",
    "private_table_token",
    "private_column_token",
]


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(payload) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def metric_public_ids(rows):
    metrics = sorted({r.get("expected_metric_id", "") for r in rows if r.get("expected_metric_id")})
    return {metric: f"ict_metric_{i:03d}" for i, metric in enumerate(metrics, 1)}


def desensitize_query(text: str) -> str:
    out = str(text or "")
    out = out.replace("RMA订单数", "售后单数")
    out = out.replace("RMA", "售后")
    out = out.replace("SKU", "商品")
    out = out.replace("gov_metric_definition", "governance catalog")
    out = out.replace("ods_erp_orders", "raw_order_table")
    for private, public in PRODUCT_REPLACEMENTS.items():
        out = out.replace(private, public)
    for pattern in SENSITIVE_PATTERNS:
        out = pattern.sub("[REDACTED_ID]", out)
    return out


def expected_action(row):
    return "answer" if row.get("expected_metric_id") else "refuse"


def query_family(row, public_dims):
    q = str(row.get("nl_query") or "").lower()
    if expected_action(row) == "refuse":
        return "policy_refusal"
    if "top10" in q or "top 10" in q:
        return "ranking_topk"
    if len(public_dims) >= 2:
        return "multi_dimension"
    if public_dims:
        return "single_dimension"
    return "flat_metric"


def label_signature(case):
    return json.dumps(
        {
            "a": case["expected_action"],
            "m": case["expected_metric_id"],
            "d": sorted(case["expected_dimensions"]),
            "t": case["expected_time_window"],
            "c": case["expected_caliber"],
        },
        sort_keys=True,
    )


def normalized_query(text):
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def conflict_audit(cases):
    normalized = defaultdict(list)
    for case in cases:
        normalized[normalized_query(case["nl_query"])].append(case)
    conflicts = []
    for key, group in normalized.items():
        labels = {label_signature(g) for g in group}
        if len(labels) > 1:
            conflicts.append(
                {
                    "normalized_query": key,
                    "case_ids": [g["case_id"] for g in group],
                    "label_count": len(labels),
                    "reason": "duplicate public query has incompatible action/metric/dimension/time/caliber labels",
                }
            )
    return normalized, conflicts


def public_source_row(public_case, metric_name="", metric_aliases=None):
    row = {k: public_case[k] for k in [
        "case_id",
        "nl_query",
        "query_family",
        "severity",
        "domain_id",
        "split",
    ]}
    row["source_format"] = "public_desensitized_case_text_v2_label_free"
    return row


def public_label_row(public_case, metric_name="", metric_aliases=None):
    row = {k: public_case[k] for k in [
        "case_id",
        "expected_action",
        "expected_metric_id",
        "expected_dimensions",
        "expected_time_window",
        "expected_caliber",
        "expected_policy_id",
        "query_family",
        "severity",
        "domain_id",
        "split",
    ]}
    row["metric_name"] = metric_name
    row["metric_aliases"] = metric_aliases or []
    row["label_format"] = "public_desensitized_case_labels_v1"
    return row


def split_legacy_labeled_source(rows):
    """Allow one migration run from the older labeled source-candidate file."""
    if not rows or "expected_action" not in rows[0]:
        return rows, None
    source_rows = []
    label_rows = []
    for row in rows:
        source_rows.append(
            {
                "case_id": row["case_id"],
                "nl_query": row["nl_query"],
                "query_family": row.get("query_family", "flat_metric"),
                "severity": row.get("severity", "P1"),
                "domain_id": row.get("domain_id", "ict_domain_01"),
                "split": row.get("split", "public_industrial_case_text"),
                "source_format": "public_desensitized_case_text_v2_label_free",
            }
        )
        label_rows.append(
            {
                "case_id": row["case_id"],
                "expected_action": row["expected_action"],
                "expected_metric_id": row.get("expected_metric_id", ""),
                "expected_dimensions": row.get("expected_dimensions", []),
                "expected_time_window": row.get("expected_time_window", "unspecified"),
                "expected_caliber": row.get("expected_caliber", "not_applicable"),
                "expected_policy_id": row.get("expected_policy_id", ""),
                "query_family": row.get("query_family", "flat_metric"),
                "severity": row.get("severity", "P1"),
                "domain_id": row.get("domain_id", "ict_domain_01"),
                "split": row.get("split", "public_industrial_case_text"),
                "metric_name": row.get("metric_name", ""),
                "metric_aliases": row.get("metric_aliases", []),
                "label_format": "public_desensitized_case_labels_v1",
            }
        )
    return source_rows, label_rows


def sanitize_public_source_rows(source_rows, label_rows):
    source_allowed = {
        "case_id",
        "nl_query",
        "query_family",
        "severity",
        "domain_id",
        "split",
        "source_format",
    }
    label_allowed = {
        "case_id",
        "expected_action",
        "expected_metric_id",
        "expected_dimensions",
        "expected_time_window",
        "expected_caliber",
        "expected_policy_id",
        "query_family",
        "severity",
        "domain_id",
        "split",
        "metric_name",
        "metric_aliases",
        "label_format",
    }
    label_by_id = {}
    for row in label_rows:
        if set(row) - label_allowed:
            raise ValueError(f"public label row {row.get('case_id')} contains unsupported fields: {sorted(set(row) - label_allowed)}")
        if row.get("label_format") != "public_desensitized_case_labels_v1":
            raise ValueError(f"public label row {row.get('case_id')} has unsupported label_format")
        label_by_id[row["case_id"]] = row
    cases = []
    metric_meta = {}
    for row in source_rows:
        if set(row) - source_allowed:
            raise ValueError(f"public source row {row.get('case_id')} contains unsupported fields: {sorted(set(row) - source_allowed)}")
        if row.get("source_format") != "public_desensitized_case_text_v2_label_free":
            raise ValueError(f"public source row {row.get('case_id')} has unsupported source_format")
        label = label_by_id.get(row["case_id"])
        if not label:
            raise ValueError(f"missing label row for public source case {row['case_id']}")
        case = {
            "case_id": row["case_id"],
            "nl_query": row["nl_query"],
            "expected_action": label["expected_action"],
            "expected_metric_id": label.get("expected_metric_id", ""),
            "expected_dimensions": label.get("expected_dimensions", []),
            "expected_time_window": label.get("expected_time_window", "unspecified"),
            "expected_caliber": label.get("expected_caliber", "not_applicable"),
            "expected_policy_id": label.get("expected_policy_id", ""),
            "query_family": row.get("query_family", "flat_metric"),
            "severity": row.get("severity", "P1"),
            "domain_id": row.get("domain_id", "ict_domain_01"),
            "split": row.get("split", "public_industrial_case_text"),
        }
        cases.append(case)
        metric_id = case["expected_metric_id"]
        if metric_id:
            metric_meta.setdefault(
                metric_id,
                {
                    "metric_id": metric_id,
                    "metric_name": label.get("metric_name") or metric_id.replace("_", " ").title(),
                    "aliases": label.get("metric_aliases") or [],
                    "domain_id": "ict_domain_01",
                    "release_note": "Public anonymized metric id; private metric id withheld.",
                },
            )
    return cases, sorted(metric_meta.values(), key=lambda x: x["metric_id"])


def build_from_private_rows(rows):
    metric_map = metric_public_ids(rows)
    cases = []
    public_source = []
    public_labels = []
    private_trace_digests = []
    for idx, row in enumerate(rows, 1):
        action = expected_action(row)
        metric_id = metric_map.get(row.get("expected_metric_id", ""), "")
        metric_name = ""
        metric_aliases = []
        if row.get("expected_metric_id"):
            metric_name, metric_aliases = METRIC_META.get(
                row.get("expected_metric_id", ""),
                (row.get("expected_metric_id", "").replace("_", " ").title(), [row.get("expected_metric_id", "").replace("_", " ")]),
            )
        public_dims = [DIM_MAP[d][0] for d in row.get("expected_dimensions", []) if d in DIM_MAP]
        time_window = TIME_MAP.get(row.get("expected_time_window", ""), "unspecified")
        caliber = CALIBER_MAP.get(row.get("expected_caliber", ""), "not_applicable")
        public = {
            "case_id": f"ict_case_{idx:04d}",
            "nl_query": desensitize_query(row.get("nl_query", "")),
            "expected_action": action,
            "expected_metric_id": metric_id,
            "expected_dimensions": public_dims,
            "expected_time_window": time_window,
            "expected_caliber": caliber,
            "expected_policy_id": "ict_policy_refusal" if action == "refuse" else "",
            "query_family": query_family(row, public_dims),
            "severity": row.get("severity", "P1"),
            "domain_id": "ict_domain_01",
            "split": "public_industrial_case_text",
        }
        cases.append(public)
        public_source.append(public_source_row(public))
        public_labels.append(public_label_row(public, metric_name=metric_name, metric_aliases=metric_aliases))
        private_trace_digests.append({"case_id": public["case_id"], "private_trace_digest": stable_hash(row)})
    metric_catalog = []
    for private_id, public_id in metric_map.items():
        name, aliases = METRIC_META.get(private_id, (private_id.replace("_", " ").title(), [private_id.replace("_", " ")]))
        metric_catalog.append(
            {
                "metric_id": public_id,
                "metric_name": name,
                "aliases": aliases,
                "domain_id": "ict_domain_01",
                "release_note": "Public anonymized metric id; private metric id withheld.",
            }
        )
    metric_catalog.sort(key=lambda x: x["metric_id"])
    return cases, metric_catalog, public_source, public_labels, private_trace_digests


def build_from_public_source(source_rows, label_rows):
    cases, metric_catalog = sanitize_public_source_rows(source_rows, label_rows)
    return cases, metric_catalog, source_rows, label_rows, []


def public_source_path() -> Path:
    if SRC_PUBLIC.exists():
        return SRC_PUBLIC
    if SRC_PUBLIC_BENCHMARK.exists():
        return SRC_PUBLIC_BENCHMARK
    raise FileNotFoundError(
        "Missing public desensitized source candidate file. Expected "
        f"{SRC_PUBLIC} or {SRC_PUBLIC_BENCHMARK}."
    )


def public_label_path() -> Path:
    if SRC_PUBLIC_LABELS.exists():
        return SRC_PUBLIC_LABELS
    if SRC_PUBLIC_BENCHMARK_LABELS.exists():
        return SRC_PUBLIC_BENCHMARK_LABELS
    return None


def build(source: str = "public"):
    if source == "public":
        source_path = public_source_path()
        rows = read_jsonl(source_path)
        rows, legacy_labels = split_legacy_labeled_source(rows)
        labels_path = public_label_path()
        if legacy_labels is None and labels_path is None:
            raise FileNotFoundError(
                "Missing public desensitized label file. Expected "
                f"{SRC_PUBLIC_LABELS} or {SRC_PUBLIC_BENCHMARK_LABELS}."
            )
        label_rows = legacy_labels if legacy_labels is not None else read_jsonl(labels_path)
        source_mode = "public_desensitized_candidate_source"
        cases, metric_catalog, public_source, public_labels, private_trace_digests = build_from_public_source(rows, label_rows)
    elif source == "private":
        if not SRC_PRIVATE.exists():
            raise FileNotFoundError(f"Private author source requested but missing: {SRC_PRIVATE}")
        rows = read_jsonl(SRC_PRIVATE)
        source_mode = "private_author_source"
        cases, metric_catalog, public_source, public_labels, private_trace_digests = build_from_private_rows(rows)
    else:
        raise ValueError(f"Unsupported source mode: {source}")

    candidate_normalized, candidate_conflicts = conflict_audit(cases)
    withheld_ids = {case_id for conflict in candidate_conflicts for case_id in conflict["case_ids"]}
    clean_cases = [case for case in cases if case["case_id"] not in withheld_ids]
    normalized, conflicts = conflict_audit(clean_cases)
    blind = [{k: v for k, v in case.items() if not k.startswith("expected_")} for case in clean_cases]
    gold = [
        {
            "case_id": case["case_id"],
            "expected_action": case["expected_action"],
            "expected_metric_id": case["expected_metric_id"],
            "expected_dimensions": case["expected_dimensions"],
            "expected_time_window": case["expected_time_window"],
            "expected_caliber": case["expected_caliber"],
            "expected_policy_id": case["expected_policy_id"],
            "query_family": case["query_family"],
        }
        for case in clean_cases
    ]
    withheld_label_conflicts = [
        {
            "normalized_query": conflict["normalized_query"],
            "case_ids": conflict["case_ids"],
            "reason": conflict["reason"],
        }
        for conflict in candidate_conflicts
    ]
    trace_rows = [
        {
            **trace,
            "release_status": "withheld_label_conflict" if trace["case_id"] in withheld_ids else "released",
        }
        for trace in private_trace_digests
    ]
    dimension_catalog = [
        {
            "dimension_id": public_id,
            "name": name,
            "aliases": aliases,
            "domain_id": "ict_domain_01",
            "parent": {"segment_l2": "segment_l1", "segment_l3": "segment_l2"}.get(public_id, ""),
            "grain_rank": {"segment_l1": 1, "segment_l2": 2, "segment_l3": 3, "market_region": 1}.get(public_id, 1),
        }
        for _, (public_id, name, aliases) in DIM_MAP.items()
    ]
    policies = [
        {
            "policy_id": "ict_policy_refusal",
            "policy_type": "disclosure_and_offdomain_refusal",
            "public_rule": "Refuse raw SQL/catalog dumps, off-domain requests, and requests with no governed metric.",
            "refusal_triggers": [
                "select ",
                "drop ",
                "delete ",
                "truncate ",
                "governance catalog",
                "raw_order_table",
                "天气",
                "weather",
                "raw",
                "dump",
                "明细",
                "邮箱",
                "电话",
                "no recognized vocabulary",
                "xyzzy",
                "plurghly",
            ],
            "ambiguous_queries": ["客诉率"],
        }
    ]
    audit_text = "\n".join(json.dumps(obj, ensure_ascii=False, sort_keys=True) for obj in clean_cases + metric_catalog + dimension_catalog)
    private_hits = [term for term in PRIVATE_TERMS if re.search(rf"\b{re.escape(term)}\b", audit_text, flags=re.I)]
    audit = {
        "counts": {
            "source_cases": len(rows),
            "candidate_cases": len(cases),
            "released_cases": len(clean_cases),
            "withheld_label_conflict_cases": len(withheld_ids),
            "metrics": len(metric_catalog),
            "dimensions": len(dimension_catalog),
            "refusal_cases": sum(1 for c in clean_cases if c["expected_action"] == "refuse"),
        },
        "source_mode": source_mode,
        "label_conflict_audit": {
            "normalized_query_groups": len(normalized),
            "duplicate_query_groups": sum(1 for group in normalized.values() if len(group) > 1),
            "conflicting_duplicate_groups": len(conflicts),
            "conflict_examples": conflicts[:5],
            "candidate_conflicting_duplicate_groups_before_withholding": len(candidate_conflicts),
            "withheld_conflict_groups": withheld_label_conflicts,
        },
        "privacy_audit": {
            "private_term_hits": private_hits,
            "passed": not private_hits,
            "withheld": [
                "raw rows",
                "private table names",
                "private column names",
                "private metric ids",
                "private domain ids",
                "private-to-public mappings",
                "case source ids",
                "private provenance digests, stored only in internal author trace",
            ],
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    stale_public_trace = OUT / "private_trace_digests_internal.jsonl"
    if stale_public_trace.exists():
        stale_public_trace.unlink()
    write_jsonl(OUT / "cases.jsonl", clean_cases)
    write_jsonl(OUT / "blind_cases.jsonl", blind)
    write_jsonl(OUT / "gold_labels.jsonl", gold)
    write_jsonl(OUT / "metric_catalog.jsonl", metric_catalog)
    write_jsonl(OUT / "dimension_catalog.jsonl", dimension_catalog)
    write_jsonl(OUT / "policy_catalog.jsonl", policies)
    write_jsonl(OUT / "withheld_label_conflicts.jsonl", withheld_label_conflicts)
    write_jsonl(OUT / "source_candidates_public_desensitized.jsonl", public_source)
    write_jsonl(OUT / "source_candidate_labels_public_desensitized.jsonl", public_labels)
    write_jsonl(ROOT / "experiments" / "enterprise_metric_cases_public_desensitized.jsonl", public_source)
    write_jsonl(ROOT / "experiments" / "enterprise_metric_cases_public_desensitized_labels.jsonl", public_labels)
    if trace_rows:
        INTERNAL_TRACE.mkdir(parents=True, exist_ok=True)
        write_jsonl(INTERNAL_TRACE / "private_trace_digests_internal.jsonl", trace_rows)
    write_json(OUT / "release_audit.json", audit)
    (OUT / "README.md").write_text(
        "\n".join(
            [
                "# IndustrialCaseText-MetricCaliber",
                "",
                "A public desensitized release of real industrial NL2Metric-Caliber case text and labels.",
                "It releases natural query text, anonymized labels, blind prediction input, scorer-only labels, catalogs, and privacy/label audits.",
                "",
                "It does not release raw enterprise rows, private table/column names, private metric ids, private domain ids, source case ids, or private-to-public mappings.",
                "`source_candidates_public_desensitized.jsonl` and `experiments/enterprise_metric_cases_public_desensitized.jsonl` are label-free source-candidate files for rebuild and inspection.",
                "`source_candidate_labels_public_desensitized.jsonl`, `gold_labels.jsonl`, and `experiments/enterprise_metric_cases_public_desensitized_labels.jsonl` contain labels for rebuild/scoring only and are not legal prediction inputs.",
                "`cases.jsonl` is a labeled inspection/rebuild convenience file, not a legal prediction input.",
                "",
                "Run:",
                "",
                "```bash",
                "python3 scripts/build_industrial_case_text_metric_caliber.py",
                "python3 scripts/run_industrial_case_text_eval.py",
                "```",
                "",
                "Legal prediction input is `blind_cases.jsonl` plus public catalogs/policies. The evaluator uses `gold_labels.jsonl` only for scoring.",
                "",
                "See `LABEL_POLICY.md` for the public action, metric, dimension, time, caliber, and duplicate-conflict labeling rules.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "label_quality_audit.md").write_text(
        "\n".join(
            [
                "# Label Quality Audit",
                "",
                f"- Candidate cases before conflict withholding: {len(cases)}",
                f"- Released scored cases: {len(clean_cases)}",
                f"- Withheld label-conflict cases: {len(withheld_ids)}",
                f"- Metrics: {len(metric_catalog)}",
                f"- Dimensions: {len(dimension_catalog)}",
                f"- Refusal cases: {audit['counts']['refusal_cases']}",
                f"- Duplicate normalized query groups: {audit['label_conflict_audit']['duplicate_query_groups']}",
                f"- Conflicting duplicate groups: {audit['label_conflict_audit']['conflicting_duplicate_groups']}",
                f"- Privacy scan passed: {audit['privacy_audit']['passed']}",
                "",
                "Conflict policy: any duplicate public query with incompatible gold action/metric/dimension/time/caliber labels is withheld from the scored public split.",
                "Prediction protocol: `source_candidates_public_desensitized.jsonl` is label-free; labels are separated into `source_candidate_labels_public_desensitized.jsonl` and scorer-only `gold_labels.jsonl`; `blind_cases.jsonl` removes labels and private trace digests.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build IndustrialCaseText-MetricCaliber from public or private source.")
    parser.add_argument(
        "--source",
        choices=["public", "private"],
        default="public",
        help="Use the released public desensitized candidate-source file by default. Private author source is opt-in.",
    )
    args = parser.parse_args()
    build(source=args.source)
