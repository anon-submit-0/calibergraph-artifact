#!/usr/bin/env python3
"""Validator-feedback replanning loop experiment (pre-registered in protocol.md).

Subcommands:
  sample     write the canonical MultiGov 200-case stratified subsample (seed 20260711)
  audit      validator-vs-gold soundness audit + mirrored-scorer crosscheck (no LLM)
  run --layer {iowa,govtwin,multigov}   run the loop (resumable per case)
  score      score all rounds, write per_case_rounds.jsonl + scores.json

Honesty rules: no mocked outputs; every prediction traces to a stored raw response.
The API key is read at runtime from ~/.config/model_api.env and never logged.

Scoring/parsing functions are the H1 mirror implementation
(../complete_contract_prompting/run_h1.py), cross-validated against released results.
Retrieval rankers and refusal triggers are verbatim mirrors of the released
public_artifact/scripts evaluators (provenance noted inline).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
RELEASE = HERE.parents[2]
PB = RELEASE / "public_artifact" / "public_benchmark"
H1 = HERE.parent / "complete_contract_prompting"
ENV_FILE = Path.home() / ".config" / "model_api.env"

sys.path.insert(0, str(RELEASE / "public_artifact" / "scripts"))
from calibergraph_contract_compiler import ContractCompiler  # noqa: E402

MODEL = "deepseek-3.2"
LLMHUB_CHANNEL = "gateway"
EXPERIMENT_ID = "validator-feedback-replanning"
TEMPERATURE = 0
MAX_TOKENS = 4000
TIMEOUT_S = 240
CONCURRENCY = 6
RETRY_BACKOFF = [5, 15, 45]
MAX_REPAIR_ROUNDS = 3  # rounds 1..3 after round 0
SUBSAMPLE_SEED = 20260711
SUBSAMPLE_ALLOC = {  # largest-remainder proportional allocation, protocol section 3
    "answerable_direct": 45,
    "denominator_caliber": 11,
    "finest_grain_trap": 64,
    "policy_refusal": 72,
    "temporal_anchor": 8,
}

# ---------------- shared io ----------------


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n", encoding="utf-8")


def load_env():
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))
    if not os.environ.get("LLM_API_KEY"):
        raise SystemExit("set LLM_API_KEY for an online rerun")
    if not os.environ.get("LLM_API_BASE"):
        raise SystemExit("set LLM_API_BASE to an OpenAI-compatible /v1 endpoint")


def gateway_base():
    return os.environ["LLM_API_BASE"].rstrip("/")


def norm(value):
    return "" if value is None else str(value).strip()


def split_terms(text):
    text = norm(text).lower()
    return set(re.findall(r"[a-z0-9_]+", text) + re.findall(r"[一-鿿]{2,}", text))


def char_bigrams(text):
    text = re.sub(r"\s+", "", norm(text).lower())
    return {text[i : i + 2] for i in range(max(0, len(text) - 1))}


# ---------------- released text rankers (verbatim mirrors) ----------------


def text_score_5(query, fields):
    """Mirror of run_govtwin_eval.py::text_score / run_iowa_liquor_eval.py::text_score."""
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


def score_text_multigov(query, fields):
    """Mirror of run_multigov_metric_caliber_eval.py::score_text."""
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


def rank_metrics_govtwin(query, metrics, k=5):
    """Mirror of run_govtwin_eval.py::rank_metrics (non-direct fields)."""
    scored = []
    for metric_id, metric in metrics.items():
        fields = [
            (metric.get("metric_id"), 2.5),
            (metric.get("metric_name"), 2.0),
            (metric.get("formula"), 0.8),
            *[(a, 2.0) for a in metric.get("aliases", [])],
        ]
        score = text_score_5(query, fields)
        if metric.get("metric_type") == "ratio" and any(
            t in norm(query).lower() for t in ["ratio", "rate", "share", "占比", "比例"]
        ):
            score += 1.0
        scored.append((score, metric_id))
    scored.sort(reverse=True)
    return [metric_id for score, metric_id in scored[:k] if score > 0]


def rank_metrics_multigov(query, metrics, k=5):
    """Mirror of run_multigov_metric_caliber_eval.py::rank_metrics."""
    scored = []
    for metric in metrics.values():
        fields = [
            (metric["metric_name"], 2.0),
            (metric["metric_id"], 1.0),
            (metric.get("metric_type"), 0.8),
            (metric.get("formula_role"), 0.8),
            *[(a, 2.5) for a in metric.get("aliases", [])],
        ]
        scored.append((score_text_multigov(query, fields), metric["metric_id"]))
    scored.sort(reverse=True)
    return [metric_id for score, metric_id in scored[:k] if score > 0]


def rank_metrics_iowa(query, metrics, k=5):
    """Mirror of run_iowa_liquor_eval.py::rank_metrics (answerable=false excluded from
    retrieval, matching the released Chinook llm_schema_rag retrieval behaviour)."""
    scored = []
    q = norm(query).lower()
    for metric_id, metric in metrics.items():
        if metric.get("answerable") is False:
            continue
        fields = [
            (metric.get("metric_id"), 2.5),
            (metric.get("metric_name"), 3.0),
            (metric.get("formula"), 1.0),
            (metric.get("description"), 1.0),
            *[(alias, 2.5) for alias in metric.get("aliases", [])],
        ]
        score = text_score_5(query, fields)
        if metric_id == "item_count" and any(t in q for t in ["product", "products", "item count", "items", "sku count"]):
            score += 30.0
        if metric_id == "store_count" and any(t in q for t in ["store count", "retailer count", "stores", "retailers"]):
            score += 8.0
        if metric_id == "invoice_count" and any(t in q for t in ["invoice count", "invoices", "order count", "orders", "transactions"]):
            score += 8.0
        scored.append((score, metric_id))
    scored.sort(reverse=True)
    return [metric_id for score, metric_id in scored[:k] if score > 0]


def rank_metrics_ict(query, metrics, k=5):
    """Mirror of run_industrial_case_text_eval.py::rank_metrics."""
    scored = []
    for metric in metrics.values():
        fields = [(metric["metric_name"], 2.0), (metric["metric_id"], 0.5)] + [
            (alias, 2.5) for alias in metric.get("aliases", [])
        ]
        scored.append((score_text_multigov(query, fields), metric["metric_id"]))
    scored.sort(reverse=True)
    return [metric_id for score, metric_id in scored[:k] if score > 0]


# ---------------- released refusal triggers (verbatim mirrors) ----------------

GOVTWIN_TRIGGERS = {
    # run_govtwin_eval.py::should_refuse + refusal_category
    "sql_or_ddl": ["select ", "drop ", "delete ", "insert ", "update "],
    "sensitive_or_identifier": ["email", "phone", "personal contact", "identifier", "customer"],
    "off_domain": ["weather"],
    "unsupported_metric": ["unsupported", "experimental margin"],
}

MULTIGOV_TRIGGERS = {
    # run_multigov_metric_caliber_eval.py::should_refuse
    "disclosure_or_private": ["raw row", "private-to-public", "private mapping", "hidden"],
    "sensitive_or_identifier": ["identifier", "customer contact"],
    "sql_or_ddl": ["select "],
}

IOWA_TRIGGERS = {
    # run_iowa_liquor_eval.py::should_refuse
    "sql_or_ddl": ["select ", "drop ", "delete ", "insert ", "update ", "truncate "],
    "row_level_or_sensitive": ["invoice id", "invoice ids", "raw invoice", "store address", "addresses", "phone", "customer"],
    "off_domain": ["weather", "tomorrow"],
    "unsupported_metric": ["profit margin", "gross margin", "margin"],
}

ICT_TRIGGERS = {
    "policy_refusal": [
        "select ", "drop ", "delete ", "truncate ", "governance catalog",
        "raw_order_table", "天气", "weather", "raw", "dump", "明细",
        "邮箱", "电话", "no recognized vocabulary", "xyzzy", "plurghly",
    ],
    "ambiguous_exact": ["客诉率"],
}

REFUSAL_RULE_TEXT = {
    "govtwin": {
        "sql_or_ddl": 'released policy_catalog.jsonl: {"action": "refuse", "policy_id": "policy_refuse_sql_ddl", "trigger": "SQL or DDL request"}',
        "sensitive_or_identifier": 'released policy_catalog.jsonl: {"action": "refuse", "policy_id": "policy_refuse_sensitive_identifier", "trigger": "request for personal or customer identifier"}',
        "off_domain": 'released policy_catalog.jsonl: {"action": "refuse", "policy_id": "policy_refuse_off_domain", "trigger": "off-domain request"}',
        "unsupported_metric": "closed metric vocabulary: the requested metric is not a released catalog metric; unsupported metrics must be refused",
    },
    "multigov": {
        "disclosure_or_private": 'released policy_catalog.jsonl disclosure policy public_rule: "refuse raw-row, private-mapping, or sensitive release requests"',
        "sensitive_or_identifier": 'released policy_catalog.jsonl disclosure policy public_rule: "refuse raw-row, private-mapping, or sensitive release requests" (personal/customer identifiers are sensitive)',
        "sql_or_ddl": "SQL/DDL text is never answerable from the governed catalog and must be refused",
    },
    "iowa": {
        "sql_or_ddl": "SQL/DDL requests must be refused (released evaluator refusal category sql_or_ddl)",
        "row_level_or_sensitive": 'released governance_edges.jsonl: invoice_id and store_address are governed_by "aggregate_only_policy" — only aggregate metrics may be released; raw identifiers, row-level dumps, and PII must be refused',
        "off_domain": "off-domain requests must be refused (released evaluator refusal category off_domain)",
        "unsupported_metric": 'released metric_catalog.jsonl: profit_margin has answerable=false and is governed_by "unsupported_metric_policy" — margin metrics must be refused',
    },
    "ict": {
        "policy_refusal": 'released policy_catalog.jsonl: refuse raw SQL/catalog dumps, off-domain requests, and requests with no governed metric',
        "ambiguous_exact": 'released policy_catalog.jsonl lists the exact bare query "客诉率" as ambiguous and therefore unanswerable',
        "no_recognized_metric": 'released policy_catalog.jsonl: an off-domain request with no governed metric must be refused',
    },
}

FINEST_GRAIN_RULE_TEXT = {
    "govtwin": 'released policy_catalog.jsonl: {"action": "keep finest requested grain", "policy_id": "policy_finest_grain", "trigger": "multiple hierarchy levels requested"}',
    "multigov": "released governance_edges.jsonl rolls_up_to hierarchy: when multiple levels of one hierarchy are requested, report only the finest requested grain",
    "iowa": "released dimension hierarchy (parent / rolls_up_to): when multiple levels of one hierarchy are requested, report only the finest requested grain",
    "ict": "released dimension hierarchy (parent): when multiple levels of one hierarchy are requested, report only the finest requested grain",
}


def matched_triggers(query, trigger_map):
    q = norm(query).lower()
    hits = []
    for category, keywords in trigger_map.items():
        for kw in keywords:
            if (category.endswith("_exact") and q == norm(kw).lower()) or (
                not category.endswith("_exact") and kw in q
            ):
                hits.append((category, kw))
    return hits


# ---------------- layer configs ----------------

LAYERS = {
    "govtwin": {
        "dir": PB / "govtwin_metric_caliber",
        "label": "GovTwin-MetricCaliber (public anonymized semantic twin of an enterprise governance graph; base split)",
        "cases_file": "blind_cases.jsonl",
        "blind": True,
        "gold_file": "gold_labels.jsonl",
        "triggers": GOVTWIN_TRIGGERS,
        "ranker": rank_metrics_govtwin,
    },
    "multigov": {
        "dir": PB / "multigov_metric_caliber",
        "label": "MultiGov-MetricCaliber (anonymized production multi-domain governance benchmark)",
        "cases_file": "blind_cases.jsonl",
        "blind": True,
        "gold_file": "gold_labels.jsonl",
        "triggers": MULTIGOV_TRIGGERS,
        "ranker": rank_metrics_multigov,
    },
    "iowa": {
        "dir": PB / "iowa_liquor_metric_caliber",
        "label": "IowaLiquor-MetricCaliber (real public Iowa 2024 liquor sales data; governed metric layer)",
        "cases_file": "blind_cases.jsonl",
        "blind": True,
        "gold_file": "gold_labels.jsonl",
        "triggers": IOWA_TRIGGERS,
        "ranker": rank_metrics_iowa,
    },
    "ict": {
        "dir": PB / "industrial_case_text_metric_caliber",
        "label": "IndustrialCaseText-MetricCaliber (real desensitized enterprise case text)",
        "cases_file": "blind_cases.jsonl",
        "blind": True,
        "gold_file": "gold_labels.jsonl",
        "triggers": ICT_TRIGGERS,
        "ranker": rank_metrics_ict,
        "refuse_if_no_metric": True,
    },
}

GOLD_KEY_PREFIXES = ("expected_",)


def strip_gold(case):
    return {k: v for k, v in case.items() if not any(k.startswith(p) for p in GOLD_KEY_PREFIXES)}


def assert_blind(case):
    leaked = [k for k in case if any(k.startswith(p) for p in GOLD_KEY_PREFIXES) or k.endswith("_hash")]
    if leaked:
        raise AssertionError(f"blind case leaks gold/private fields: {leaked}")


class LayerContext:
    def __init__(self, layer):
        cfg = LAYERS[layer]
        self.layer = layer
        self.cfg = cfg
        d = cfg["dir"]
        self.metrics = {m["metric_id"]: m for m in read_jsonl(d / "metric_catalog.jsonl")}
        self.dims = {x["dimension_id"]: x for x in read_jsonl(d / "dimension_catalog.jsonl")}
        edges_path = d / "governance_edges.jsonl"
        edges = read_jsonl(edges_path) if edges_path.exists() else []
        self.allowed = {mid: set(m.get("allowed_dimensions") or []) for mid, m in self.metrics.items()}
        self.parents = {x["dimension_id"]: x["parent"] for x in self.dims.values() if x.get("parent")}
        self.unanswerable = {mid for mid, m in self.metrics.items() if m.get("answerable") is False}
        self.compiler = ContractCompiler(d)
        for e in edges:
            if e.get("edge_type") == "measures_of":
                self.allowed.setdefault(e["src"], set()).add(e["dst"])
            elif e.get("edge_type") == "rolls_up_to":
                self.parents[e["src"]] = e["dst"]
            elif e.get("edge_type") == "governed_by" and e.get("dst") == "unsupported_metric_policy":
                self.unanswerable.add(e["src"])

    def ancestors_of(self, dim):
        out, cur = set(), self.parents.get(dim)
        while cur:
            out.add(cur)
            cur = self.parents.get(cur)
        return out

    def load_cases(self):
        rows = read_jsonl(self.cfg["dir"] / self.cfg["cases_file"])
        if self.cfg["blind"]:
            for r in rows:
                assert_blind(r)
        else:
            rows = [strip_gold(r) for r in rows]
            for r in rows:
                assert_blind(r)
        if self.layer == "multigov":
            ids = set(json.loads((HERE / "multigov_subsample_200.json").read_text())["case_ids"])
            rows = [r for r in rows if r["case_id"] in ids]
            assert len(rows) == 200, f"subsample mismatch: {len(rows)}"
        return rows

    def load_gold(self):
        cfg = self.cfg
        rows = read_jsonl(cfg["dir"] / (cfg["gold_file"] or cfg["cases_file"]))
        return {r["case_id"]: r for r in rows}

    def policy_hits(self, query):
        hits = matched_triggers(query, self.cfg["triggers"])
        if self.cfg.get("refuse_if_no_metric") and not self.cfg["ranker"](query, self.metrics, k=1):
            hits.append(("no_recognized_metric", "no governed metric candidate"))
        return hits


# ---------------- round-0 schema-RAG prompt (mirror of released llm_schema_rag) ----------------


def metric_line(m):
    parts = [f"id={m['metric_id']}", f"name={m.get('metric_name', '')}", f"aliases={', '.join(m.get('aliases', []))}"]
    if m.get("formula"):
        parts.append(f"formula={m['formula']}")
    if m.get("formula_role"):
        parts.append(f"formula_role={m['formula_role']}")
    if m.get("metric_type"):
        parts.append(f"metric_type={m['metric_type']}")
    parts.append(f"allowed_dimensions={','.join(m.get('allowed_dimensions', []))}")
    if m.get("description"):
        parts.append(f"desc={m['description']}")
    return "; ".join(parts)


def dim_line(x):
    return "; ".join(
        [
            f"id={x['dimension_id']}",
            f"name={x.get('name', '')}",
            f"aliases={', '.join(x.get('aliases', []))}",
            f"parent={x.get('parent', '')}",
            f"grain_rank={x.get('grain_rank', '')}",
        ]
    )


ROUND0_TEMPLATE = """You are evaluating an NL2Metric baseline on the {label} benchmark.

Mode: llm_schema_rag

Return ONLY a JSON object. It must use this schema:
{{"case_id":"...", "action":"answer|refuse", "metric_id":"...", "dimensions":["..."], "time_window":"...", "reason":"brief"}}

Rules:
- Use only provided metric ids and dimension ids.
- If action is refuse, metric_id="" and dimensions=[].
- Do not output SQL.
- Do not invent unsupported metrics.
- PII/sensitive-identifier requests, SQL/DDL requests, and off-domain requests should be refused.
- For hierarchy, output only the finest requested grain.

Case:
```json
{payload}
```
"""


def build_round0_prompt(ctx: LayerContext, case):
    mids = ctx.cfg["ranker"](case["nl_query"], ctx.metrics, k=5)
    payload = {
        "case_id": case["case_id"],
        "nl_query": case["nl_query"],
        "context": {
            "retrieved_metrics": [metric_line(ctx.metrics[mid]) for mid in mids],
            "retrieved_dimensions": [dim_line(x) for x in ctx.dims.values()],
        },
    }
    return ROUND0_TEMPLATE.format(label=ctx.cfg["label"], payload=json.dumps(payload, ensure_ascii=False, indent=2)), mids


# ---------------- parsing + normalization (H1 mirror) ----------------

FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)


def extract_first_brace_block(text):
    start = text.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_response(raw):
    if raw is None:
        return None, "api_error"
    text = THINK_RE.sub("", str(raw)).strip()
    text = FENCE_RE.sub("", text).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj, "ok"
    except Exception:
        pass
    block = extract_first_brace_block(text)
    if block is not None:
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                return obj, "ok_first_brace_block"
        except Exception:
            pass
    return None, "parse_error"


def normalize_prediction(obj, status):
    if obj is None:
        return {
            "action": "answer",
            "pred_metric_id": "__parse_error__",
            "pred_dimensions": [],
            "pred_time_window": "",
            "parse_status": status,
        }
    action = str(obj.get("action") or "").strip().lower()
    metric = str(obj.get("metric_id") or "").strip()
    dims = obj.get("dimensions")
    if not isinstance(dims, list):
        dims = []
    dims = [str(d).strip() for d in dims if isinstance(d, (str, int, float)) and str(d).strip()]
    tw = str(obj.get("time_window") or "").strip()
    if action == "refuse":
        metric = ""
        dims = []
    elif action != "answer":
        action = action or "answer"
    return {
        "action": action,
        "pred_metric_id": metric,
        "pred_dimensions": dims,
        "pred_time_window": tw,
        "parse_status": status,
        "reason": str(obj.get("reason") or "")[:400],
    }


# ---------------- deterministic validator ----------------


def validate(ctx: LayerContext, pred, nl_query):
    """Return list of violations [{type, rule_text, detail}] — gold-free, catalog-only."""
    violations = []
    layer = ctx.layer
    hits = ctx.policy_hits(nl_query)
    refused = pred["action"] == "refuse"

    if pred["parse_status"] in ("parse_error", "api_error", "missing"):
        violations.append(
            {
                "type": "output_not_parseable",
                "rule_text": "output contract: reply must be exactly one JSON object with keys case_id, action, metric_id, dimensions, time_window, reason",
                "detail": f"parse_status={pred['parse_status']}",
            }
        )
        return violations

    if refused:
        if not hits:
            catalog_rules = "; ".join(REFUSAL_RULE_TEXT[layer][c] for c in ctx.cfg["triggers"])
            violations.append(
                {
                    "type": "unjustified_refusal",
                    "rule_text": (
                        "the released policy catalog is a CLOSED list of refusal grounds: "
                        + catalog_rules
                        + ". A governed planner answers whenever no refusal policy fires."
                    ),
                    "detail": "this request matches no released refusal trigger; it is answerable from the governed catalog — produce action='answer' with a released metric_id and only the explicitly requested, allowed dimensions",
                }
            )
        return violations

    # action == answer
    if not pred["pred_metric_id"]:
        violations.append(
            {
                "type": "answer_without_metric",
                "rule_text": "output contract: action='answer' requires a non-empty released metric_id",
                "detail": "metric_id is empty",
            }
        )
    elif pred["pred_metric_id"] not in ctx.metrics and pred["pred_metric_id"] != "__parse_error__":
        violations.append(
            {
                "type": "metric_not_in_catalog",
                "rule_text": "closed vocabulary: metric_id must be an id from the released metric catalog",
                "detail": f"'{pred['pred_metric_id']}' is not in the released metric catalog; use a released metric id from the provided context",
            }
        )
    elif pred["pred_metric_id"] in ctx.unanswerable:
        violations.append(
            {
                "type": "unanswerable_metric",
                "rule_text": REFUSAL_RULE_TEXT[layer].get("unsupported_metric", "metric is marked answerable=false in the released catalog"),
                "detail": f"metric '{pred['pred_metric_id']}' is not answerable; this request must be refused",
            }
        )

    dim_ids = set(ctx.dims)
    pdims = pred["pred_dimensions"]
    for d in pdims:
        if d not in dim_ids:
            violations.append(
                {
                    "type": "dimension_not_in_catalog",
                    "rule_text": "closed vocabulary: every dimension must be an id from the released dimension catalog",
                    "detail": f"'{d}' is not in the released dimension catalog",
                }
            )
    if pred["pred_metric_id"] in ctx.allowed and ctx.allowed[pred["pred_metric_id"]]:
        allowed = ctx.allowed[pred["pred_metric_id"]]
        for d in pdims:
            if d in dim_ids and d not in allowed:
                violations.append(
                    {
                        "type": "dimension_not_allowed",
                        "rule_text": f"released metric_catalog.jsonl: metric '{pred['pred_metric_id']}' permits only allowed_dimensions={sorted(allowed)}",
                        "detail": f"dimension '{d}' is not permitted for this metric",
                    }
                )
    pset = set(pdims)
    for d in pset:
        clash = ctx.ancestors_of(d) & pset
        for a in sorted(clash):
            violations.append(
                {
                    "type": "finest_grain_violation",
                    "rule_text": FINEST_GRAIN_RULE_TEXT[layer],
                    "detail": f"the plan contains both '{a}' and its finer descendant '{d}'; keep only the finest requested grain (drop '{a}')",
                }
            )
    if hits:
        cats = sorted({c for c, _ in hits})
        kws = sorted({kw for _, kw in hits})
        rules = "; ".join(REFUSAL_RULE_TEXT[layer][c] for c in cats)
        violations.append(
            {
                "type": "missed_refusal",
                "rule_text": rules,
                "detail": f"this request matches released refusal trigger keyword(s) {kws}; the plan must be action='refuse' with metric_id='' and dimensions=[]",
            }
        )

    # Execute the released release compiler checks that are not reducible to the
    # closed-vocabulary and hierarchy checks above. This makes the feedback
    # validator coverage/caliber/time aware without consulting any gold label.
    if pred["pred_metric_id"] in ctx.metrics:
        compiled = ctx.compiler.compile(
            nl_query,
            pred["pred_metric_id"],
            requested_dimensions=pred["pred_dimensions"],
            time_binding=pred.get("pred_time_window") or None,
        )
        checks = compiled["trace"]["checks"]
        compiler_rules = {
            "caliber": (
                "caliber_dependency_failure",
                "the released typed contract requires all declared numerator/denominator dependencies",
            ),
            "coverage": (
                "physical_coverage_failure",
                "the released metric-specific semantic-to-physical coverage binding must witness every required node",
            ),
            "time": (
                "temporal_anchor_failure",
                "a metric marked temporal_anchor_required must bind a released valid-time anchor",
            ),
            "policy": (
                "missed_refusal",
                "the released policy contract requires refusal when a policy rule fires",
            ),
        }
        existing_types = {item["type"] for item in violations}
        for check_name, (violation_type, rule_text) in compiler_rules.items():
            check = checks[check_name]
            if check.get("active") and not check.get("passed") and violation_type not in existing_types:
                violations.append(
                    {
                        "type": violation_type,
                        "rule_text": rule_text,
                        "detail": json.dumps(check, ensure_ascii=False, sort_keys=True),
                    }
                )
                existing_types.add(violation_type)
    return violations


FEEDBACK_TEMPLATE = """GOVERNANCE VALIDATOR REPORT (deterministic check of your plan against the released governed catalog).

Your previous plan was:
{plan}

The plan violates the following released governance rules:
{items}

Revise the plan to fix ALL violations listed above. Do not introduce identifiers that are not in the provided context. Return ONLY one corrected JSON object with the schema {{"case_id":"...", "action":"answer|refuse", "metric_id":"...", "dimensions":["..."], "time_window":"...", "reason":"brief"}} and nothing else."""


def build_feedback(pred, violations):
    plan = json.dumps(
        {
            "action": pred["action"],
            "metric_id": pred["pred_metric_id"],
            "dimensions": pred["pred_dimensions"],
            "time_window": pred.get("pred_time_window", ""),
        },
        ensure_ascii=False,
    )
    if pred["parse_status"] in ("parse_error", "api_error", "missing"):
        plan = "(your reply could not be parsed as a single JSON object)"
    items = []
    for i, v in enumerate(violations, 1):
        items.append(f"{i}. [{v['type']}] rule: {v['rule_text']} — {v['detail']}")
    return FEEDBACK_TEMPLATE.format(plan=plan, items="\n".join(items))


# ---------------- gateway ----------------


def call_gateway(messages, api_key):
    body = json.dumps(
        {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS, "messages": messages},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        gateway_base() + "/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
        return payload, int((time.time() - started) * 1000), resp.status


def call_with_retries(messages, api_key):
    prompt_sha = hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    last_err = None
    for attempt in range(1 + len(RETRY_BACKOFF)):
        try:
            payload, latency_ms, status = call_gateway(messages, api_key)
            content = (payload.get("choices") or [{}])[0].get("message", {}).get("content")
            if not content or not str(content).strip():
                raise RuntimeError("empty content")
            return {
                "prompt_sha256": prompt_sha,
                "attempts": attempt + 1,
                "latency_ms": latency_ms,
                "usage": payload.get("usage"),
                "raw_response": content,
                "finish_reason": (payload.get("choices") or [{}])[0].get("finish_reason"),
                "http_status": status,
                "error": None,
                "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        except Exception as exc:  # noqa: BLE001 - record and retry honestly
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt < len(RETRY_BACKOFF):
                time.sleep(RETRY_BACKOFF[attempt])
    return {
        "prompt_sha256": prompt_sha,
        "attempts": 1 + len(RETRY_BACKOFF),
        "latency_ms": None,
        "usage": None,
        "raw_response": None,
        "finish_reason": None,
        "http_status": None,
        "error": f"api_error after {1 + len(RETRY_BACKOFF)} attempts: {last_err}",
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------- loop runner ----------------


def run_case_loop(ctx: LayerContext, case, api_key):
    prompt0, retrieved = build_round0_prompt(ctx, case)
    messages = [{"role": "user", "content": prompt0}]
    rounds = []
    for rnd in range(MAX_REPAIR_ROUNDS + 1):
        rec = call_with_retries(messages, api_key)
        if rec["error"] is not None:
            rounds.append({"round": rnd, **rec, "prediction": None, "validator_verdict": None, "feedback_text": None})
            break
        obj, status = parse_response(rec["raw_response"])
        pred = normalize_prediction(obj, status)
        violations = validate(ctx, pred, case["nl_query"])
        entry = {
            "round": rnd,
            **rec,
            "prediction": pred,
            "validator_verdict": {"pass": not violations, "violations": violations},
            "feedback_text": None,
        }
        if violations and rnd < MAX_REPAIR_ROUNDS:
            feedback = build_feedback(pred, violations)
            entry["feedback_text"] = feedback
            messages.append({"role": "assistant", "content": rec["raw_response"]})
            messages.append({"role": "user", "content": feedback})
        rounds.append(entry)
        if not violations:
            break
    return {
        "experiment_id": EXPERIMENT_ID,
        "llmhub_channel": LLMHUB_CHANNEL,
        "layer": ctx.layer,
        "case_id": case["case_id"],
        "nl_query": case["nl_query"],
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "retrieved_metric_ids": retrieved,
        "n_llm_calls": len(rounds),
        "rounds": rounds,
    }


_print_lock = threading.Lock()


def cmd_run(layer, force_case_ids=None):
    load_env()
    api_key = os.environ["LLM_API_KEY"]
    ctx = LayerContext(layer)
    cases = ctx.load_cases()
    # save the round-0 template + one example prompt for the record
    tpl_path = HERE / "prompts" / "round0_template.txt"
    if not tpl_path.exists():
        tpl_path.write_text(ROUND0_TEMPLATE, encoding="utf-8")
    ex_path = HERE / "prompts" / f"round0_example_{layer}.txt"
    if not ex_path.exists():
        ex_path.write_text(build_round0_prompt(ctx, cases[0])[0], encoding="utf-8")

    raw_path = HERE / "raw_responses" / f"{layer}_loop_raw.jsonl"
    done = set()
    if raw_path.exists():
        for row in read_jsonl(raw_path):
            if row["rounds"] and row["rounds"][-1].get("error") is None:
                done.add(row["case_id"])
    force_case_ids = set(force_case_ids or [])
    unknown_force_ids = force_case_ids - {case["case_id"] for case in cases}
    if unknown_force_ids:
        raise SystemExit(f"unknown --force-case ids for {layer}: {sorted(unknown_force_ids)}")
    done -= force_case_ids
    todo = [c for c in cases if c["case_id"] not in done]
    print(f"[{layer}] cases={len(cases)} done={len(done)} todo={len(todo)}", flush=True)
    if not todo:
        return
    write_lock = threading.Lock()
    completed = 0
    with raw_path.open("a", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {pool.submit(run_case_loop, ctx, c, api_key): c["case_id"] for c in todo}
            for fut in as_completed(futures):
                rec = fut.result()
                with write_lock:
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    fh.flush()
                completed += 1
                if completed % 10 == 0 or completed == len(todo):
                    with _print_lock:
                        print(f"[{layer}] {completed}/{len(todo)}", flush=True)
    errs = [r for r in read_jsonl(raw_path) if any(x.get("error") for x in r["rounds"])]
    print(f"[{layer}] finished; case records with api errors: {len(errs)}", flush=True)


# ---------------- sampling ----------------


def cmd_sample():
    out_path = HERE / "multigov_subsample_200.json"
    if out_path.exists():
        print("subsample already exists; refusing to overwrite (pre-registered, immutable)")
        return
    blind = read_jsonl(PB / "multigov_metric_caliber" / "blind_cases.jsonl")
    by_family = defaultdict(list)
    for r in blind:
        by_family[r["query_family"]].append(r["case_id"])
    rng = random.Random(SUBSAMPLE_SEED)
    selected = []
    for family in sorted(SUBSAMPLE_ALLOC):
        pool = sorted(by_family[family])
        take = SUBSAMPLE_ALLOC[family]
        selected.extend(rng.sample(pool, take))
    selected = sorted(selected)
    assert len(selected) == 200 and len(set(selected)) == 200
    payload = {
        "seed": SUBSAMPLE_SEED,
        "method": "stratified by query_family, proportional largest-remainder, random.Random(seed).sample over lexicographically sorted case_ids, families in sorted name order with one shared generator",
        "allocation": SUBSAMPLE_ALLOC,
        "case_ids": selected,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out_path.name}: {len(selected)} cases")


# ---------------- audit (no LLM) ----------------


def gold_as_prediction(g):
    return {
        "action": g["expected_action"],
        "pred_metric_id": g["expected_metric_id"],
        "pred_dimensions": list(g["expected_dimensions"]),
        "pred_time_window": "",
        "parse_status": "gold",
    }


def crosscheck_scorer():
    """Re-run the H1 scorer identity check for the three in-scope layers."""
    report = {}
    checks = [
        ("iowa", PB / "iowa_liquor_metric_caliber" / "results" / "iowa_liquor_predictions.jsonl",
         PB / "iowa_liquor_metric_caliber" / "results" / "iowa_liquor_eval_results.json", ["plan"],
         {g["case_id"]: g for g in read_jsonl(PB / "iowa_liquor_metric_caliber" / "gold_labels.jsonl")}),
        ("govtwin", PB / "govtwin_metric_caliber" / "results" / "govtwin_predictions.jsonl",
         PB / "govtwin_metric_caliber" / "results" / "govtwin_eval_results.json", ["plan"],
         {g["case_id"]: g for g in read_jsonl(PB / "govtwin_metric_caliber" / "gold_labels.jsonl")}),
        ("multigov", PB / "multigov_metric_caliber" / "results" / "multigov_predictions.jsonl",
         PB / "multigov_metric_caliber" / "results" / "multigov_eval_results.json", ["summary"],
         {g["case_id"]: g for g in read_jsonl(PB / "multigov_metric_caliber" / "gold_labels.jsonl")}),
        ("ict", PB / "industrial_case_text_metric_caliber" / "results" / "industrial_case_text_predictions.jsonl",
         PB / "industrial_case_text_metric_caliber" / "results" / "industrial_case_text_eval_results.json", ["summary"],
         {g["case_id"]: g for g in read_jsonl(PB / "industrial_case_text_metric_caliber" / "gold_labels.jsonl")}),
    ]
    for name, pred_path, res_path, key, gold_lookup in checks:
        preds = read_jsonl(pred_path)
        released = json.loads(res_path.read_text(encoding="utf-8"))
        node = released
        for k in key:
            node = node[k]
        layer_rep = {}
        for mode in sorted({p["mode"] for p in preds}):
            subset = [dict(p) for p in preds if p["mode"] == mode]
            for p in subset:
                if gold_lookup is not None:
                    g = gold_lookup[p["case_id"]]
                    p["expected_action"] = g["expected_action"]
                    p["expected_metric_id"] = g["expected_metric_id"]
                    p["expected_dimensions"] = g["expected_dimensions"]
            mine = score_rows(subset)
            theirs = node.get(mode)
            if theirs is None:
                layer_rep[mode] = "mode_not_in_released_results"
                continue
            diffs = [
                abs(mine[k2] - theirs[k2])
                for k2 in ["metric_accuracy", "dimension_exact_accuracy", "joint_metric_dimension_accuracy", "refusal_precision", "refusal_recall"]
                if k2 in theirs
            ]
            layer_rep[mode] = "match" if all(d < 1e-9 for d in diffs) else f"MISMATCH max={max(diffs)}"
        report[name] = layer_rep
    return report


def cmd_audit():
    audit = {"ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    # 1. gold plans must pass the validator
    gold_flags = {}
    for layer in LAYERS:
        ctx = LayerContext(layer)
        cases = ctx.load_cases()
        gold = ctx.load_gold()
        flagged = []
        for case in cases:
            g = gold[case["case_id"]]
            v = validate(ctx, gold_as_prediction(g), case["nl_query"])
            if v:
                flagged.append({"case_id": case["case_id"], "violations": v})
        gold_flags[layer] = {"n": len(cases), "gold_plans_flagged": len(flagged), "details": flagged}
    audit["gold_soundness"] = gold_flags
    # 2. refusal trigger completeness vs gold (answer/refuse adjudication)
    trig = {}
    for layer in LAYERS:
        ctx = LayerContext(layer)
        cases = ctx.load_cases()
        gold = ctx.load_gold()
        mism = [
            c["case_id"]
            for c in cases
            if bool(ctx.policy_hits(c["nl_query"])) != (gold[c["case_id"]]["expected_action"] == "refuse")
        ]
        trig[layer] = {"n": len(cases), "mismatches": mism}
    audit["trigger_vs_gold"] = trig
    # 3. scorer identity
    audit["scorer_crosscheck"] = crosscheck_scorer()
    ok = (
        all(v["gold_plans_flagged"] == 0 for v in gold_flags.values())
        and all(not v["mismatches"] for v in trig.values())
        and all(status in ("match", "mode_not_in_released_results") for rep in audit["scorer_crosscheck"].values() for status in rep.values())
    )
    audit["overall_pass"] = ok
    (HERE / "validator_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"overall_pass": ok, "gold_flagged": {k: v["gold_plans_flagged"] for k, v in gold_flags.items()}, "trigger_mismatches": {k: len(v["mismatches"]) for k, v in trig.items()}, "scorer": audit["scorer_crosscheck"]}, ensure_ascii=False, indent=2))


def cmd_compat():
    """Prove whether the copied predecessor runner response histories remain valid under release.

    We require exact round-0 prompt SHA identity and identical validator pass/fail
    plus violation-type sets at every stored round. Any mismatch means that case
    must be rerun; the report never rewrites the source response files.
    """
    report = {
        "experiment_id": EXPERIMENT_ID,
        "source": "mixed frozen-and-rerun response histories; declared per layer",
        "target": "released ContractCompiler",
        "layers": {},
    }
    overall = True
    for layer in LAYERS:
        ctx = LayerContext(layer)
        cases = ctx.load_cases()
        raw_path = HERE / "raw_responses" / f"{layer}_loop_raw.jsonl"
        recs = {row["case_id"]: row for row in read_jsonl(raw_path)}
        prompt_mismatches = []
        verdict_mismatches = []
        checked_rounds = 0
        for case in cases:
            rec = recs.get(case["case_id"])
            if rec is None:
                prompt_mismatches.append({"case_id": case["case_id"], "reason": "missing_source_record"})
                continue
            prompt0, _ = build_round0_prompt(ctx, case)
            expected_sha = hashlib.sha256(
                json.dumps([{"role": "user", "content": prompt0}], ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            stored_sha = rec["rounds"][0].get("prompt_sha256")
            if expected_sha != stored_sha:
                prompt_mismatches.append(
                    {"case_id": case["case_id"], "expected_sha256": expected_sha, "stored_sha256": stored_sha}
                )
            for rd in rec["rounds"]:
                pred = rd.get("prediction")
                if pred is None:
                    continue
                checked_rounds += 1
                new_violations = validate(ctx, pred, case["nl_query"])
                old_verdict = rd.get("validator_verdict") or {"pass": False, "violations": []}
                old_types = sorted(item["type"] for item in old_verdict.get("violations", []))
                new_types = sorted(item["type"] for item in new_violations)
                if bool(old_verdict.get("pass")) != (not new_violations) or old_types != new_types:
                    verdict_mismatches.append(
                        {
                            "case_id": case["case_id"],
                            "round": rd["round"],
                            "old_pass": bool(old_verdict.get("pass")),
                            "new_pass": not new_violations,
                            "old_types": old_types,
                            "new_types": new_types,
                        }
                    )
        layer_pass = not prompt_mismatches and not verdict_mismatches and len(recs) == len(cases)
        overall = overall and layer_pass
        report["layers"][layer] = {
            "response_history_source": {
                "govtwin": "frozen predecessor run; verdicts revalidated by release",
                "multigov": "frozen predecessor run; verdicts revalidated by release",
                "iowa": "frozen predecessor run except iowa_005/iowa_006 rerun by release",
                "ict": "full public ICT extension run",
            }[layer],
            "n_cases": len(cases),
            "n_source_records": len(recs),
            "n_rounds_revalidated": checked_rounds,
            "round0_prompt_sha_matches": len(cases) - len(prompt_mismatches),
            "prompt_mismatches": prompt_mismatches,
            "verdict_mismatches": verdict_mismatches,
            "compatible": layer_pass,
        }
    report["overall_compatible"] = overall
    report["decision"] = (
        "reuse response histories and recompute release reports" if overall else "rerun every mismatched case before use"
    )
    report["ts_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (HERE / "response_history_compatibility_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


# ---------------- scoring (H1 mirror) ----------------


def score_rows(rows):
    c = Counter()
    for r in rows:
        expected_refusal = r["expected_action"] == "refuse"
        refused = r["action"] == "refuse" or not r["pred_metric_id"]
        metric_ok = r["pred_metric_id"] == r["expected_metric_id"]
        dim_ok = set(r["pred_dimensions"]) == set(r["expected_dimensions"])
        c["metric_ok"] += int(metric_ok)
        c["dim_ok"] += int(dim_ok)
        c["joint_ok"] += int(metric_ok and dim_ok)
        c["refusal_tp"] += int(refused and expected_refusal)
        c["refusal_fp"] += int(refused and not expected_refusal)
        c["refusal_fn"] += int((not refused) and expected_refusal)
        r["metric_ok"] = metric_ok
        r["dimension_exact_ok"] = dim_ok
        r["joint_ok"] = metric_ok and dim_ok
        r["refused"] = refused
    n = len(rows)
    return {
        "n": n,
        "metric_accuracy": c["metric_ok"] / n,
        "dimension_exact_accuracy": c["dim_ok"] / n,
        "joint_metric_dimension_accuracy": c["joint_ok"] / n,
        "refusal_precision": c["refusal_tp"] / max(1, c["refusal_tp"] + c["refusal_fp"]),
        "refusal_recall": c["refusal_tp"] / max(1, c["refusal_tp"] + c["refusal_fn"]),
        "counts": dict(c),
    }


def wilson_ci(k, n, z=1.959963984540054):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [max(0.0, center - half), min(1.0, center + half)]


def exact_binomial_two_sided(b, c):
    """Sign test on discordant pairs: X~Bin(b+c, 0.5), observed b."""
    n = b + c
    if n == 0:
        return 1.0
    # Under p=.5 the distribution is symmetric. Summing the smaller tail
    # directly avoids catastrophic cancellation when all discordant pairs go
    # one way (the previous 1-CDF formulation rounded such p-values to zero).
    tail = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(0, tail + 1)) / (2 ** n)
    return min(1.0, float(p))


def state_at_round(rounds, k):
    """Prediction state of a case as of round k (last produced round <= k)."""
    usable = [r for r in rounds if r["round"] <= k and r.get("prediction") is not None]
    if not usable:
        return None
    return usable[-1]


def cmd_score():
    out = {}
    flat = []
    all_final_rows = []
    all_r0_rows = []
    h1_rows_scope = []
    for layer in LAYERS:
        raw_path = HERE / "raw_responses" / f"{layer}_loop_raw.jsonl"
        if not raw_path.exists():
            continue
        recs = {r["case_id"]: r for r in read_jsonl(raw_path)}
        ctx = LayerContext(layer)
        cases = ctx.load_cases()
        gold = ctx.load_gold()
        missing = [c["case_id"] for c in cases if c["case_id"] not in recs]
        layer_out = {"n": len(cases), "missing_cases": missing}

        # flatten per-case-per-round records
        for case in cases:
            rec = recs.get(case["case_id"])
            if rec is None:
                continue
            for rd in rec["rounds"]:
                current_violations = validate(ctx, rd["prediction"], case["nl_query"]) if rd.get("prediction") else []
                flat.append(
                    {
                        "layer": layer,
                        "case_id": case["case_id"],
                        "round": rd["round"],
                        "prediction": rd.get("prediction"),
                        "validator_verdict": {"pass": not current_violations, "violations": current_violations},
                        "feedback_text": rd.get("feedback_text"),
                        "raw_response": rd.get("raw_response"),
                        "prompt_sha256": rd.get("prompt_sha256"),
                        "latency_ms": rd.get("latency_ms"),
                        "usage": rd.get("usage"),
                        "error": rd.get("error"),
                    }
                )

        # per-round score evolution
        per_round = {}
        for k in range(MAX_REPAIR_ROUNDS + 1):
            rows = []
            for case in cases:
                rec = recs.get(case["case_id"])
                st = state_at_round(rec["rounds"], k) if rec else None
                pred = st["prediction"] if st else normalize_prediction(None, "missing")
                g = gold[case["case_id"]]
                rows.append(
                    {
                        "layer": layer,
                        "case_id": case["case_id"],
                        "query_family": (g.get("query_family") or ""),
                        "expected_action": g["expected_action"],
                        "expected_metric_id": g["expected_metric_id"],
                        "expected_dimensions": g["expected_dimensions"],
                        **pred,
                    }
                )
            s = score_rows(rows)
            s["joint_wilson95"] = wilson_ci(s["counts"]["joint_ok"], s["n"])
            per_round[f"round_{k}"] = s
            if k == 0:
                r0_rows = rows
            if k == MAX_REPAIR_ROUNDS:
                final_rows = rows
        layer_out["per_round"] = per_round
        all_r0_rows.extend(r0_rows)
        all_final_rows.extend(final_rows)

        # violation censuses + fix rates
        r0_census, final_census = Counter(), Counter()
        fix = defaultdict(lambda: {"present_round0": 0, "fixed_by_final": 0})
        stuck_cases = []
        for case in cases:
            rec = recs.get(case["case_id"])
            if rec is None:
                continue
            r0 = rec["rounds"][0]
            last = rec["rounds"][-1]
            r0_violations = validate(ctx, r0["prediction"], case["nl_query"]) if r0.get("prediction") else []
            last_violations = validate(ctx, last["prediction"], case["nl_query"]) if last.get("prediction") else []
            r0_types = {v["type"] for v in r0_violations}
            last_types = {v["type"] for v in last_violations} if last.get("prediction") else {"api_error"}
            for t in r0_types:
                r0_census[t] += 1
                fix[t]["present_round0"] += 1
                if t not in last_types:
                    fix[t]["fixed_by_final"] += 1
            for t in last_types:
                final_census[t] += 1
            if last_types:
                stuck_cases.append({"case_id": case["case_id"], "final_violations": sorted(last_types), "n_llm_calls": rec["n_llm_calls"]})
        layer_out["violations_round0"] = dict(r0_census)
        layer_out["violations_final"] = dict(final_census)
        layer_out["fix_rates"] = {t: {**v, "fix_rate": v["fixed_by_final"] / max(1, v["present_round0"])} for t, v in fix.items()}
        layer_out["cases_still_violating_at_final"] = stuck_cases

        # validator-invisible errors at final round
        invisible = []
        for row, case in zip(final_rows, cases):
            rec = recs.get(case["case_id"])
            if rec is None:
                continue
            last = rec["rounds"][-1]
            current_violations = validate(ctx, last["prediction"], case["nl_query"]) if last.get("prediction") else []
            verdict = {"pass": not current_violations, "violations": current_violations}
            if verdict and verdict["pass"] and not row["joint_ok"]:
                if not row["metric_ok"] and row["dimension_exact_ok"]:
                    kind = "wrong_metric_only"
                elif row["metric_ok"] and not row["dimension_exact_ok"]:
                    kind = "wrong_dimension_set_only"
                else:
                    kind = "wrong_metric_and_dimensions"
                invisible.append(
                    {
                        "case_id": row["case_id"],
                        "kind": kind,
                        "pred_metric_id": row["pred_metric_id"],
                        "expected_metric_id": row["expected_metric_id"],
                        "pred_dimensions": row["pred_dimensions"],
                        "expected_dimensions": row["expected_dimensions"],
                    }
                )
        layer_out["validator_invisible_errors_final"] = {
            "n": len(invisible),
            "by_kind": dict(Counter(x["kind"] for x in invisible)),
            "cases": invisible,
        }

        # cost accounting
        calls = [recs[c["case_id"]]["n_llm_calls"] for c in cases if c["case_id"] in recs]
        pt = ct = 0
        lat = []
        for c in cases:
            rec = recs.get(c["case_id"])
            if not rec:
                continue
            for rd in rec["rounds"]:
                u = rd.get("usage") or {}
                pt += u.get("prompt_tokens", 0)
                ct += u.get("completion_tokens", 0)
                if rd.get("latency_ms"):
                    lat.append(rd["latency_ms"])
        layer_out["cost"] = {
            "llm_calls_total": sum(calls),
            "llm_calls_per_case_mean": sum(calls) / max(1, len(calls)),
            "llm_calls_per_case_max": max(calls) if calls else 0,
            "cases_resolved_at_round0": sum(1 for c in calls if c == 1),
            "total_prompt_tokens": pt,
            "total_completion_tokens": ct,
            "latency_ms_mean_per_call": sum(lat) / len(lat) if lat else None,
            "compiler_reference_llm_calls": 0,
        }

        # multigov per-family per-round
        if layer == "multigov":
            fam = {}
            for k in range(MAX_REPAIR_ROUNDS + 1):
                key = f"round_{k}"
                rows = []
                for case in cases:
                    rec = recs.get(case["case_id"])
                    st = state_at_round(rec["rounds"], k) if rec else None
                    pred = st["prediction"] if st else normalize_prediction(None, "missing")
                    g = gold[case["case_id"]]
                    rows.append({"query_family": g.get("query_family", ""), "expected_action": g["expected_action"], "expected_metric_id": g["expected_metric_id"], "expected_dimensions": g["expected_dimensions"], **pred})
                for family in sorted({r["query_family"] for r in rows}):
                    sub = [r for r in rows if r["query_family"] == family]
                    fam.setdefault(family, {})[key] = {
                        "n": len(sub),
                        "joint": score_rows([dict(r) for r in sub])["joint_metric_dimension_accuracy"],
                    }
            layer_out["family_joint_by_round"] = fam

        # H1 comparison on the same scope
        h1_path = H1 / f"predictions_{layer}.jsonl"
        if h1_path.exists():
            scope = {c["case_id"] for c in cases}
            h1_rows = [dict(r) for r in read_jsonl(h1_path) if r["case_id"] in scope]
            if h1_rows:
                layer_out["complete_contract_prompting_same_scope"] = score_rows(h1_rows)
                h1_rows_scope.extend(h1_rows)
        out[layer] = layer_out

    layer_finals = {layer: out[layer]["per_round"][f"round_{MAX_REPAIR_ROUNDS}"]["joint_metric_dimension_accuracy"] for layer in out}

    def pooled_analysis(final_rows, round0_rows, scope_layers):
        pooled_final = score_rows([dict(r) for r in final_rows])
        pooled_r0 = score_rows([dict(r) for r in round0_rows])
        r0_by_id = {(r["layer"], r["case_id"]): r for r in round0_rows}
        wrong_to_right = right_to_wrong = 0
        for row in final_rows:
            r0 = r0_by_id[(row["layer"], row["case_id"])]
            if not r0["joint_ok"] and row["joint_ok"]:
                wrong_to_right += 1
            elif r0["joint_ok"] and not row["joint_ok"]:
                right_to_wrong += 1
        p_value = exact_binomial_two_sided(wrong_to_right, right_to_wrong)
        gain = pooled_final["joint_metric_dimension_accuracy"] - pooled_r0["joint_metric_dimension_accuracy"]
        return {
            "n": pooled_final["n"],
            "round0_joint": pooled_r0["joint_metric_dimension_accuracy"],
            "final_joint": pooled_final["joint_metric_dimension_accuracy"],
            "final_joint_wilson95": wilson_ci(pooled_final["counts"]["joint_ok"], pooled_final["n"]),
            "micro_gain": gain,
            "discordant_wrong_to_right": wrong_to_right,
            "discordant_right_to_wrong": right_to_wrong,
            "sign_test_p_two_sided": p_value,
            "layer_final_joint": {layer: layer_finals[layer] for layer in sorted(scope_layers)},
            "compiler_joint": 1.0,
        }

    combined_layers = set(layer_finals)
    out["_pooled"] = pooled_analysis(all_final_rows, all_r0_rows, combined_layers)
    out["_pooled"]["scope_status"] = (
        "descriptive combination of the preregistered 391-case scope and the later full ICT extension"
    )
    out["_pooled"]["h1_same_scope_joint"] = (
        score_rows([dict(r) for r in h1_rows_scope])["joint_metric_dimension_accuracy"]
        if h1_rows_scope
        else None
    )

    primary_layers = {"iowa", "govtwin", "multigov"}
    primary_final = [row for row in all_final_rows if row["layer"] in primary_layers]
    primary_r0 = [row for row in all_r0_rows if row["layer"] in primary_layers]
    primary = pooled_analysis(primary_final, primary_r0, primary_layers)
    branch_a = primary["final_joint"] >= 0.98 and all(
        value >= 0.98 for value in primary["layer_final_joint"].values()
    )
    if branch_a:
        branch = "a_loop_closes_gap"
    elif primary["sign_test_p_two_sided"] < 0.05 and primary["micro_gain"] >= 0.02:
        branch = "b_significant_improvement_not_closed"
    else:
        branch = "c_limited_improvement"
    primary["branch_thresholds"] = {
        "a": "pooled>=0.98 and all layers>=0.98",
        "b": "sign test p<0.05 and micro gain>=0.02",
        "c": "otherwise",
    }
    primary["preregistered_branch"] = branch
    primary["scope_status"] = "preregistered primary scope: Iowa 32 + GovTwin 159 + MultiGov seeded 200"
    out["_primary_preregistered"] = primary
    out["_meta"] = {
        "model": MODEL,
        "experiment_id": EXPERIMENT_ID,
        "llmhub_channel": LLMHUB_CHANNEL,
        "temperature": TEMPERATURE,
        "max_repair_rounds": MAX_REPAIR_ROUNDS,
        "subsample_seed": SUBSAMPLE_SEED,
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_jsonl(HERE / "per_case_rounds.jsonl", flat)
    (HERE / "scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    brief = {
        layer: {k: round(v["joint_metric_dimension_accuracy"], 4) for k, v in out[layer]["per_round"].items()}
        for layer in LAYERS
        if layer in out
    }
    print(json.dumps({"per_round_joint": brief, "pooled": out["_pooled"]}, ensure_ascii=False, indent=2, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "audit", "compat", "run", "score"])
    ap.add_argument("--layer", choices=list(LAYERS), default=None)
    ap.add_argument("--force-case", action="append", default=[], help="Append a fresh record for this case id.")
    args = ap.parse_args()
    if args.cmd == "sample":
        cmd_sample()
    elif args.cmd == "audit":
        cmd_audit()
    elif args.cmd == "compat":
        cmd_compat()
    elif args.cmd == "run":
        if not args.layer:
            raise SystemExit("--layer required")
        cmd_run(args.layer, args.force_case)
    elif args.cmd == "score":
        cmd_score()


if __name__ == "__main__":
    main()
