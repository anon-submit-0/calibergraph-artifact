#!/usr/bin/env python3
"""P1a entropy-based confidence abstention baseline (pre-registered in protocol.md, frozen
sha256 01e35be46b462314b2ac68336b2ceb6eee5e2545e6974486611af1997c991f27).

Reimplementation target: Somov & Tutubalina, AAAI-25 (DOI 10.1609/aaai.v39i23.34699),
adapted to the governed NL2Metric interface; black-box sampling-consistency entropy
(gateway returns logprobs=null even when requested; see protocol.md section 0).

Subcommands:
  prompts             build per-case Schema-RAG round-0 prompts, save examples (no LLM)
  run --layer L       sample k=5 per case at temperature 0.7 (resumable per (case,sample))
  score               aggregate, apply the three frozen abstention arms, write scores.json

Honesty rules: no mocked outputs; every prediction traces to a stored raw response.
The API key is read at runtime from ~/.config/llm_keys.env and never logged.

Prompt construction (rank_metrics_*, text scorers, metric_line/dim_line, ROUND0_TEMPLATE)
is a verbatim vendored mirror of the frozen validator-feedback runner:
  _20260712/anon_repo_calibergraph/public_artifact/extended_controls/
  validator_feedback_replanning/run_loop.py
which itself mirrors the released public_artifact/scripts evaluators.
Parsing/normalization is the H1 mirror ( h1_instructed_execution/run_h1.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import threading
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
RELEASES = Path("<REPO_ROOT>/releases")
PB = RELEASES / "v24_group-B_evidence_fusion_submission_20260712" / "public_artifact" / "public_benchmark"
SUBSAMPLE_JSON = (
    RELEASES
    / "_20260712"
    / "anon_repo_calibergraph"
    / "public_artifact"
    / "extended_controls"
    / "validator_feedback_replanning"
    / "multigov_subsample_200.json"
)
SUBSAMPLE_SHA256 = "3b01f8e6668943b63a5df942a94b0741c518a8bcc6837b65d505de2494a2f5cc"
ENV_FILE = Path.home() / ".config" / "llm_keys.env"

MODEL = "deepseek-3.2"
TEMPERATURE = 0.7
K_SAMPLES = 5
MAX_TOKENS = 4000
# transport amendment 2026-07-14 (protocol.md AMENDMENT 1, transport-only):
# socket-level timeout 110 s + hard 120 s wall-clock deadline per attempt.
# urllib's timeout bounds individual socket ops only; a trickling/half-open gateway
# connection can hold a worker forever (observed: multigov stall, 82 min zero progress).
TIMEOUT_S = 110
HARD_DEADLINE_S = 120
CONCURRENCY = 6
RETRY_BACKOFF = [5, 15, 45]

GOLD_KEY_PREFIXES = ("expected_",)

# frozen error-family mapping (protocol.md section 7.2)
FAMILY_MAP = {
    "govtwin": {
        "single_or_flat_dimension": "1_metric_identity",
        "hierarchy": "3_grain",
        "synthetic_refusal": "5_refusal",
    },
    "multigov": {
        "answerable_direct": "1_metric_identity",
        "denominator_caliber": "2_caliber",
        "finest_grain_trap": "3_grain",
        "temporal_anchor": "4_temporal_coverage",
        "policy_refusal": "5_refusal",
    },
}

ARMS = ("unanimous", "majority", "any")  # c1==5 / c1>=3 / never abstain

# ---------------- shared io ----------------


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n", encoding="utf-8")


def load_env():
    if not ENV_FILE.exists():
        raise SystemExit(f"env file missing: {ENV_FILE}")
    for raw in ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))
    if not os.environ.get("<anon>_GW_KEY"):
        raise SystemExit("<anon>_GW_KEY not found in env file")


def gateway_base():
    return os.environ.get("<anon>_GW_BASE", "<GATEWAY_BASE>").rstrip("/")


def norm(value):
    return "" if value is None else str(value).strip()


def split_terms(text):
    text = norm(text).lower()
    return set(re.findall(r"[a-z0-9_]+", text) + re.findall(r"[一-鿿]{2,}", text))


def char_bigrams(text):
    text = re.sub(r"\s+", "", norm(text).lower())
    return {text[i : i + 2] for i in range(max(0, len(text) - 1))}


# ---------------- released text rankers (verbatim mirrors of run_loop.py) ----------------


def text_score_5(query, fields):
    """Mirror of run_govtwin_eval.py::text_score."""
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
    """Mirror of run_govtwin_eval.py::rank_metrics."""
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


# ---------------- layer configs ----------------

LAYERS = {
    "govtwin": {
        "dir": PB / "govtwin_metric_caliber",
        "label": "GovTwin-MetricCaliber (public anonymized semantic twin of an enterprise governance graph; base split)",
        "ranker": rank_metrics_govtwin,
    },
    "multigov": {
        "dir": PB / "multigov_metric_caliber",
        "label": "MultiGov-MetricCaliber (anonymized production multi-domain governance benchmark)",
        "ranker": rank_metrics_multigov,
    },
}


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

    def load_cases(self):
        rows = read_jsonl(self.cfg["dir"] / "blind_cases.jsonl")
        for r in rows:
            assert_blind(r)
        if self.layer == "multigov":
            raw = SUBSAMPLE_JSON.read_bytes()
            got = hashlib.sha256(raw).hexdigest()
            if got != SUBSAMPLE_SHA256:
                raise SystemExit(f"canonical subsample hash mismatch: {got}")
            ids = set(json.loads(raw.decode("utf-8"))["case_ids"])
            rows = [r for r in rows if r["case_id"] in ids]
            assert len(rows) == 200, f"subsample mismatch: {len(rows)}"
        return rows

    def load_gold(self):
        return {r["case_id"]: r for r in read_jsonl(self.cfg["dir"] / "gold_labels.jsonl")}


# ---------------- round-0 schema-RAG prompt (verbatim mirror of run_loop.py) ----------------


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


# ---------------- transport (H1 mirror; temperature 0.7 per protocol) ----------------


def _call_gateway_inner(messages, api_key):
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


class HardTimeout(RuntimeError):
    pass


def call_gateway(messages, api_key):
    """Transport amendment 1: enforce a hard wall-clock deadline per attempt.

    urllib's timeout bounds each socket operation, not the whole request; a gateway
    connection that trickles bytes (or wedges mid-body) can block a worker forever.
    The attempt runs in a daemon thread joined with HARD_DEADLINE_S; on expiry the
    attempt is abandoned and counted as a retryable failure (recorded honestly).
    The abandoned thread dies on its own socket timeout (TIMEOUT_S)."""
    result, error = [], []

    def target():
        try:
            result.append(_call_gateway_inner(messages, api_key))
        except Exception as exc:  # noqa: BLE001 - surfaced to retry loop
            error.append(exc)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(HARD_DEADLINE_S)
    if t.is_alive():
        raise HardTimeout(f"attempt exceeded hard wall-clock deadline {HARD_DEADLINE_S}s")
    if error:
        raise error[0]
    return result[0]


_print_lock = threading.Lock()


def run_sample(layer, case, sample_idx, prompt, api_key):
    messages = [{"role": "user", "content": prompt}]
    prompt_sha = hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    record = {
        "layer": layer,
        "case_id": case["case_id"],
        "sample_idx": sample_idx,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "prompt_sha256": prompt_sha,
        "attempts": 0,
        "latency_ms": None,
        "usage": None,
        "raw_response": None,
        "finish_reason": None,
        "http_status": None,
        "error": None,
        "ts_utc": None,
    }
    last_err = None
    for attempt in range(1 + len(RETRY_BACKOFF)):
        record["attempts"] = attempt + 1
        try:
            payload, latency_ms, status = call_gateway(messages, api_key)
            content = (payload.get("choices") or [{}])[0].get("message", {}).get("content")
            if not content or not str(content).strip():
                raise RuntimeError("empty content")
            record.update(
                {
                    "latency_ms": latency_ms,
                    "usage": payload.get("usage"),
                    "raw_response": content,
                    "finish_reason": (payload.get("choices") or [{}])[0].get("finish_reason"),
                    "http_status": status,
                    "error": None,
                    "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            )
            return record
        except Exception as exc:  # noqa: BLE001 - record and retry honestly
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt < len(RETRY_BACKOFF):
                time.sleep(RETRY_BACKOFF[attempt])
    record["error"] = f"api_error after {record['attempts']} attempts: {last_err}"
    record["ts_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return record


def cmd_run(layer: str):
    load_env()
    api_key = os.environ["<anon>_GW_KEY"]
    ctx = LayerContext(layer)
    cases = ctx.load_cases()
    prompts = {}
    for case in cases:
        prompt, _mids = build_round0_prompt(ctx, case)
        prompts[case["case_id"]] = prompt
    # save one example prompt for audit
    ex_path = HERE / "prompts" / f"{layer}_example_prompt.txt"
    ex_path.parent.mkdir(parents=True, exist_ok=True)
    if not ex_path.exists():
        ex_path.write_text(prompts[cases[0]["case_id"]], encoding="utf-8")

    raw_path = HERE / "raw" / f"{layer}_raw.jsonl"
    done = set()
    if raw_path.exists():
        for row in read_jsonl(raw_path):
            if row.get("error") is None:
                done.add((row["case_id"], row["sample_idx"]))
    todo = [
        (case, s)
        for case in cases
        for s in range(K_SAMPLES)
        if (case["case_id"], s) not in done
    ]
    print(f"[{layer}] cases={len(cases)} samples_needed={len(cases)*K_SAMPLES} done={len(done)} todo={len(todo)}", flush=True)
    if not todo:
        return
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    write_lock = threading.Lock()
    completed = 0
    with raw_path.open("a", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {
                pool.submit(run_sample, layer, case, s, prompts[case["case_id"]], api_key): (case["case_id"], s)
                for case, s in todo
            }
            for fut in as_completed(futures):
                rec = fut.result()
                with write_lock:
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    fh.flush()
                completed += 1
                if completed % 25 == 0 or completed == len(todo):
                    with _print_lock:
                        print(f"[{layer}] {completed}/{len(todo)}", flush=True)
    errs = [r for r in read_jsonl(raw_path) if r.get("error")]
    print(f"[{layer}] finished; error records: {len(errs)}", flush=True)


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


def normalize_tuple(obj, status):
    """Protocol section 5: A = (action, metric_id, sorted(set(dimensions)))."""
    if obj is None:
        return ("__invalid__", "", ()), status, ""
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
    else:
        action = "answer"
    return (action, metric, tuple(sorted(set(dims)))), status, tw


# ---------------- statistics ----------------


def wilson_ci(k, n, z=1.959963984540054):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [max(0.0, center - half), min(1.0, center + half)]


def _log_comb(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact_two_sided(a, b, c, d):
    """2x2 table [[a,b],[c,d]] two-sided Fisher exact p (sum of tables with prob <= observed)."""
    n = a + b + c + d
    if n == 0:
        return None
    row1, col1 = a + b, a + c
    lo, hi = max(0, row1 + col1 - n), min(row1, col1)
    log_denom = _log_comb(n, col1)

    def log_p(x):
        return _log_comb(row1, x) + _log_comb(n - row1, col1 - x) - log_denom

    obs = log_p(a)
    total = 0.0
    for x in range(lo, hi + 1):
        lp = log_p(x)
        if lp <= obs + 1e-9:
            total += math.exp(lp)
    return min(1.0, total)


def shannon_entropy_bits(counts, k=K_SAMPLES):
    h = 0.0
    for c in counts:
        p = c / k
        if p > 0:
            h -= p * math.log2(p)
    return h


# ---------------- scoring ----------------


def released_mirror_predicates(pred_tuple, gold):
    action, metric, dims = pred_tuple
    refused = action == "refuse" or not metric
    metric_ok = metric == gold["expected_metric_id"]
    dim_ok = set(dims) == set(gold["expected_dimensions"])
    joint_ok = metric_ok and dim_ok
    expected_refusal = gold["expected_action"] == "refuse"
    if expected_refusal:
        full_ok = refused
    else:
        full_ok = (not refused) and joint_ok
    return refused, metric_ok, dim_ok, joint_ok, full_ok


def aggregate_case(layer, case, samples, gold):
    """samples: list of K raw records (may include error records)."""
    by_idx = {}
    for rec in sorted(samples, key=lambda r: (r["sample_idx"], r.get("error") is not None)):
        prev = by_idx.get(rec["sample_idx"])
        if prev is None or (prev.get("error") and not rec.get("error")):
            by_idx[rec["sample_idx"]] = rec
    tuples, parse_statuses, tws = [], [], []
    for s in range(K_SAMPLES):
        rec = by_idx.get(s)
        if rec is None:
            tuples.append(("__invalid__", "", ()))
            parse_statuses.append("missing")
            tws.append("")
            continue
        obj, status = parse_response(rec.get("raw_response") if not rec.get("error") else None)
        t, st, tw = normalize_tuple(obj, status if not rec.get("error") else "api_error")
        tuples.append(t)
        parse_statuses.append(st)
        tws.append(tw)
    counts = Counter(tuples)
    c1 = counts.most_common(1)[0][1]
    modal = {t for t, c in counts.items() if c == c1}
    plurality = next(t for t in tuples if t in modal)  # earliest-sample tie-break (frozen)
    entropy = shannon_entropy_bits(counts.values())
    fam = FAMILY_MAP[layer][gold["query_family"]]
    refused, metric_ok, dim_ok, joint_ok, full_ok = released_mirror_predicates(plurality, gold)
    return {
        "layer": layer,
        "case_id": case["case_id"],
        "query_family": gold["query_family"],
        "error_family": fam,
        "expected_action": gold["expected_action"],
        "expected_metric_id": gold["expected_metric_id"],
        "expected_dimensions": gold["expected_dimensions"],
        "sample_tuples": [list(map(str, (t[0], t[1]))) + [list(t[2])] for t in tuples],
        "parse_statuses": parse_statuses,
        "agreement_c1": c1,
        "n_distinct_answers": len(counts),
        "entropy_bits": round(entropy, 6),
        "plurality_action": plurality[0],
        "plurality_metric_id": plurality[1],
        "plurality_dimensions": list(plurality[2]),
        "plurality_time_window": next((tw for t, tw in zip(tuples, tws) if t == plurality), ""),
        "plurality_refused": refused,
        "plurality_metric_ok": metric_ok,
        "plurality_dim_ok": dim_ok,
        "plurality_joint_ok": joint_ok,
        "plurality_full_ok": full_ok,
        "would_be_error": not full_ok,
        "abstain_unanimous": c1 < 5,
        "abstain_majority": c1 < 3,
        "abstain_any": False,
    }


def arm_summary(rows, arm):
    key = f"abstain_{arm}"
    answered = [r for r in rows if not r[key]]
    abstained = [r for r in rows if r[key]]
    n = len(rows)
    out = {
        "n": n,
        "n_answered": len(answered),
        "n_abstained": len(abstained),
        "abstention_rate": len(abstained) / n if n else None,
    }
    if answered:
        out["answered_joint_accuracy"] = sum(r["plurality_joint_ok"] for r in answered) / len(answered)
        out["answered_full_case_accuracy"] = sum(r["plurality_full_ok"] for r in answered) / len(answered)
        out["answered_full_case_wilson95"] = wilson_ci(sum(r["plurality_full_ok"] for r in answered), len(answered))
        # refusal P/R on answered subset, released convention
        tp = sum(1 for r in answered if r["plurality_refused"] and r["expected_action"] == "refuse")
        fp = sum(1 for r in answered if r["plurality_refused"] and r["expected_action"] != "refuse")
        fn = sum(1 for r in answered if (not r["plurality_refused"]) and r["expected_action"] == "refuse")
        out["answered_refusal_precision"] = tp / max(1, tp + fp)
        out["answered_refusal_recall"] = tp / max(1, tp + fn)
    # abstention-as-refusal reading (protocol 7.4b): abstained OR refused counts as refusal
    tp = sum(1 for r in rows if (r[key] or r["plurality_refused"]) and r["expected_action"] == "refuse")
    fp = sum(1 for r in rows if (r[key] or r["plurality_refused"]) and r["expected_action"] != "refuse")
    fn = sum(1 for r in rows if not (r[key] or r["plurality_refused"]) and r["expected_action"] == "refuse")
    out["abstention_as_refusal_precision"] = tp / max(1, tp + fp)
    out["abstention_as_refusal_recall"] = tp / max(1, tp + fn)
    # false abstention on would-be-correct cases
    correct = [r for r in rows if r["plurality_full_ok"]]
    out["false_abstention_rate_on_correct"] = (
        sum(1 for r in correct if r[key]) / len(correct) if correct else None
    )
    # error-family coverage
    errors = [r for r in rows if r["would_be_error"]]
    out["n_would_be_errors"] = len(errors)
    out["abstention_coverage_of_errors_overall"] = (
        sum(1 for r in errors if r[key]) / len(errors) if errors else None
    )
    overall_abst_rate = out["abstention_rate"]
    fam_block = {}
    for fam in sorted({r["error_family"] for r in rows}):
        fam_rows = [r for r in rows if r["error_family"] == fam]
        fam_err = [r for r in fam_rows if r["would_be_error"]]
        covered = sum(1 for r in fam_err if r[key])
        a = covered
        b = len(fam_err) - covered
        c = sum(1 for r in fam_rows if r[key] and not r["would_be_error"])
        d = sum(1 for r in fam_rows if not r[key] and not r["would_be_error"])
        cov = covered / len(fam_err) if fam_err else None
        fam_block[fam] = {
            "n_cases": len(fam_rows),
            "n_would_be_errors": len(fam_err),
            "n_errors_abstained": covered,
            "coverage": cov,
            "lift_vs_overall_abstention_rate": (
                cov / overall_abst_rate if (cov is not None and overall_abst_rate) else None
            ),
            "fisher_two_sided_p_abstained_x_error_within_family": fisher_exact_two_sided(a, b, c, d),
            "n_errors_unanimous_confident_c1_eq_5": sum(1 for r in fam_err if r["agreement_c1"] == 5),
        }
    out["per_error_family"] = fam_block
    # pooled fisher: abstained x would_be_error over all cases
    a = sum(1 for r in rows if r[key] and r["would_be_error"])
    b = sum(1 for r in rows if not r[key] and r["would_be_error"])
    c = sum(1 for r in rows if r[key] and not r["would_be_error"])
    d = sum(1 for r in rows if not r[key] and not r["would_be_error"])
    out["pooled_fisher_two_sided_p_abstained_x_error"] = fisher_exact_two_sided(a, b, c, d)
    return out


def cmd_score():
    all_rows = []
    cost = {"total_calls": 0, "total_prompt_tokens": 0, "total_completion_tokens": 0, "latencies": []}
    parse_counter = Counter()
    error_records = 0
    for layer in LAYERS:
        raw_path = HERE / "raw" / f"{layer}_raw.jsonl"
        if not raw_path.exists():
            print(f"[{layer}] raw missing, skipping")
            continue
        raws = read_jsonl(raw_path)
        ctx = LayerContext(layer)
        cases = ctx.load_cases()
        gold = ctx.load_gold()
        by_case = defaultdict(list)
        for r in raws:
            by_case[r["case_id"]].append(r)
            cost["total_calls"] += 1
            if r.get("error"):
                error_records += 1
            if r.get("usage"):
                cost["total_prompt_tokens"] += r["usage"].get("prompt_tokens", 0)
                cost["total_completion_tokens"] += r["usage"].get("completion_tokens", 0)
            if r.get("latency_ms"):
                cost["latencies"].append(r["latency_ms"])
        rows = []
        for case in cases:
            agg = aggregate_case(layer, case, by_case.get(case["case_id"], []), gold[case["case_id"]])
            for st in agg["parse_statuses"]:
                parse_counter[st] += 1
            rows.append(agg)
        write_jsonl(HERE / f"predictions_{layer}.jsonl", rows)
        all_rows.extend(rows)

    out = {
        "protocol_sha256": "01e35be46b462314b2ac68336b2ceb6eee5e2545e6974486611af1997c991f27",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "k_samples": K_SAMPLES,
        "confidence_signal": "sampling_consistency_entropy_over_normalized_answer_tuples (gateway logprobs unavailable; canary-verified)",
        "parse_status_counts": dict(parse_counter),
        "n_raw_error_records": error_records,
        "cost": {
            "total_calls": cost["total_calls"],
            "total_prompt_tokens": cost["total_prompt_tokens"],
            "total_completion_tokens": cost["total_completion_tokens"],
            "latency_ms_mean": (sum(cost["latencies"]) / len(cost["latencies"])) if cost["latencies"] else None,
            "sampling_cost_multiplier_vs_single_call": K_SAMPLES,
        },
        "arms": {},
    }
    scopes = {"pooled_359": all_rows}
    for layer in LAYERS:
        scopes[layer] = [r for r in all_rows if r["layer"] == layer]
    for arm in ARMS:
        out["arms"][arm] = {scope: arm_summary(rows, arm) for scope, rows in scopes.items() if rows}
    # entropy distribution among would-be errors, by family (mechanism view, arm-independent)
    mech = {}
    for fam in sorted({r["error_family"] for r in all_rows}):
        errs = [r for r in all_rows if r["error_family"] == fam and r["would_be_error"]]
        mech[fam] = {
            "n_would_be_errors": len(errs),
            "mean_entropy_bits": (sum(r["entropy_bits"] for r in errs) / len(errs)) if errs else None,
            "share_unanimous_confident_c1_eq_5": (
                sum(1 for r in errs if r["agreement_c1"] == 5) / len(errs) if errs else None
            ),
        }
    corr = [r for r in all_rows if r["plurality_full_ok"]]
    mech["_correct_cases_reference"] = {
        "n": len(corr),
        "mean_entropy_bits": (sum(r["entropy_bits"] for r in corr) / len(corr)) if corr else None,
        "share_unanimous_c1_eq_5": (sum(1 for r in corr if r["agreement_c1"] == 5) / len(corr)) if corr else None,
    }
    out["mechanism_entropy_by_family"] = mech
    (HERE / "scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    brief = {
        arm: {
            scope: {
                k: v
                for k, v in s.items()
                if k in ("n", "n_abstained", "abstention_rate", "answered_full_case_accuracy", "abstention_coverage_of_errors_overall")
            }
            for scope, s in out["arms"][arm].items()
        }
        for arm in ARMS
    }
    print(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_prompts():
    for layer in LAYERS:
        ctx = LayerContext(layer)
        cases = ctx.load_cases()
        prompt, mids = build_round0_prompt(ctx, cases[0])
        path = HERE / "prompts" / f"{layer}_example_prompt.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prompt, encoding="utf-8")
        print(f"{layer}: cases={len(cases)} example prompt {len(prompt)} chars, retrieved={mids}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prompts", "run", "score"])
    ap.add_argument("--layer", choices=list(LAYERS), default=None)
    args = ap.parse_args()
    if args.cmd == "prompts":
        cmd_prompts()
    elif args.cmd == "run":
        if not args.layer:
            raise SystemExit("--layer required for run")
        cmd_run(args.layer)
    elif args.cmd == "score":
        cmd_score()


if __name__ == "__main__":
    main()
