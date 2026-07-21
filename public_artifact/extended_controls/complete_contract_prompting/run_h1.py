#!/usr/bin/env python3
"""H1 instructed-execution experiment runner (pre-registered in protocol.md).

Subcommands:
  crosscheck          re-score released prediction files, compare to released results
  prompts             build and save per-layer system prompts (no LLM)
  run --layer L       run the LLM condition for one layer (resumable; skips cases already done)
  score               parse raw responses, score all layers, write scores.json

Honesty rules: no mocked outputs; every prediction traces to a stored raw response.
The API key is read at runtime from ~/.config/model_api.env and never logged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
import urllib.request
import urllib.error
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
RELEASE = HERE.parents[2]
PB = RELEASE / "public_artifact" / "public_benchmark"
ENV_FILE = Path.home() / ".config" / "model_api.env"

MODEL = "deepseek-3.2"
LLMHUB_CHANNEL = "gateway"
EXPERIMENT_ID = "complete-contract-instructed-execution"
TEMPERATURE = 0
MAX_TOKENS = 4000
TIMEOUT_S = 240
CONCURRENCY = 6
RETRY_BACKOFF = [5, 15, 45]

GOLD_KEY_PREFIXES = ("expected_",)

EXEC_DIRECTIVE = (
    "You must EXECUTE these policies, not merely consult them: apply the finest-grain "
    "rule to hierarchy paths; REFUSE unsupported metrics, raw identifiers, SQL/DDL, "
    "sensitive requests, and no-scope-ambiguous requests; bind default time when unspecified."
)

POLICY_OBLIGATIONS = """EXPLICIT GOVERNANCE POLICY OBLIGATIONS (execute every one of them on every request):
P1. Finest-grain rule: when a request mentions multiple levels of the same dimension hierarchy (via `parent` fields in the dimension catalog or `rolls_up_to` edges), output ONLY the finest requested grain; never output an ancestor together with its descendant.
P2. Refusal rules: REFUSE (action="refuse", metric_id="", dimensions=[]) any request that (a) asks for SQL/DDL or issues SQL/DDL text, (b) asks for raw rows, raw identifiers, row-level dumps, or private mappings, (c) asks for sensitive or personal data (emails, phones, addresses, customer identifiers), (d) is off-domain for this governed catalog, (e) targets a metric marked answerable=false in the metric catalog or any metric not present in the catalog, (f) matches a refusal trigger or ambiguous-query entry in the policy catalog, or (g) contains no recognizable governed metric or scope from this contract.
P3. Time binding: when the request names no time window, bind the governed default time window (the metric's default_time if released, otherwise the current/default reporting window of this layer); report it in the "time_window" field.
P4. Allowed dimensions: when answering, only output dimensions permitted for the chosen metric (its `allowed_dimensions` list and/or `measures_of` edges, where released).
P5. Closed vocabulary: `metric_id` and every entry of `dimensions` MUST be identifiers that literally appear in the contract above. Never invent identifiers.
"""

OUTPUT_FORMAT = """OUTPUT FORMAT (strict): reply with exactly ONE JSON object and nothing else — no markdown fences, no commentary, no SQL:
{"action":"answer|refuse","metric_id":"<metric_id or empty string>","dimensions":["<dimension_id>", "..."],"time_window":"<bound time window or empty string>","reason":"<short justification>"}
If action is "refuse", metric_id MUST be "" and dimensions MUST be [].
"""

# Released policy statement for the Chinook layer, quoted verbatim from
# public_artifact/scripts/run_public_chinook_eval.py (graph_policy + prompt Rules).
CHINOOK_RELEASED_POLICY = """Released layer policy (quoted verbatim from the released evaluator public_artifact/scripts/run_public_chinook_eval.py):
graph_policy: "If multiple hierarchy levels are requested, return only the finest requested grain: country+city -> city, year+month -> month, artist+album -> album, artist+album+track -> track. Refuse PII requests, SQL/DDL requests, off-domain requests, and unsupported refund metrics."
Released prompt rules: "Use only provided metric ids and dimension ids." / "If action is refuse, metric_id=\\"\\" and dimensions=[]." / "Do not output SQL." / "Do not invent unsupported refund metrics." / "PII requests, SQL/DDL requests, and off-domain weather/lunch/random requests should be refused." / "For hierarchy, output only the finest requested grain."
"""

LAYERS = {
    "iowa": {
        "dir": PB / "iowa_liquor_metric_caliber",
        "contract_files": [
            "contract_profile.json",
            "metric_catalog.jsonl",
            "dimension_catalog.jsonl",
            "governance_edges.jsonl",
            "schema_columns.json",
        ],
        "extra_policy_text": "",
        "cases_file": "blind_cases.jsonl",
        "cases_are_blind": True,
        "gold_file": "gold_labels.jsonl",
        "layer_label": "IowaLiquor-MetricCaliber (real public Iowa 2024 liquor sales data; governed metric layer)",
    },
    "chinook": {
        "dir": PB / "data",
        "contract_files": ["chinook_metric_catalog.jsonl", "chinook_dimension_catalog.jsonl"],
        "extra_policy_text": CHINOOK_RELEASED_POLICY,
        "cases_file": "chinook_metric_cases.jsonl",
        "cases_are_blind": False,
        "gold_file": None,
        "layer_label": "Chinook-MetricCaliber (public SQLite stress benchmark)",
    },
    "govtwin": {
        "dir": PB / "govtwin_metric_caliber",
        "contract_files": [
            "contract_profile.json",
            "metric_catalog.jsonl",
            "dimension_catalog.jsonl",
            "governance_edges.jsonl",
            "policy_catalog.jsonl",
        ],
        "extra_policy_text": "",
        "cases_file": "blind_cases.jsonl",
        "cases_are_blind": True,
        "gold_file": "gold_labels.jsonl",
        "layer_label": "GovTwin-MetricCaliber (public anonymized semantic twin of an enterprise governance graph; base split)",
    },
    "multigov": {
        "dir": PB / "multigov_metric_caliber",
        "contract_files": [
            "contract_profile.json",
            "domain_catalog.jsonl",
            "metric_catalog.jsonl",
            "dimension_catalog.jsonl",
            "governance_edges.jsonl",
            "policy_catalog.jsonl",
            "metric_coverage_bindings.jsonl",
            "physical_coverage.jsonl",
        ],
        "extra_policy_text": "",
        "cases_file": "blind_cases.jsonl",
        "cases_are_blind": True,
        "gold_file": "gold_labels.jsonl",
        "layer_label": "MultiGov-MetricCaliber (anonymized production multi-domain governance benchmark)",
    },
    "ict": {
        "dir": PB / "industrial_case_text_metric_caliber",
        "contract_files": ["metric_catalog.jsonl", "dimension_catalog.jsonl", "policy_catalog.jsonl", "LABEL_POLICY.md"],
        "extra_policy_text": "",
        "cases_file": "blind_cases.jsonl",
        "cases_are_blind": True,
        "gold_file": "gold_labels.jsonl",
        "layer_label": "IndustrialCaseText-MetricCaliber (real desensitized enterprise case text)",
    },
}


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


def strip_gold(case: dict) -> dict:
    return {k: v for k, v in case.items() if not any(k.startswith(p) for p in GOLD_KEY_PREFIXES)}


def assert_blind(case: dict):
    leaked = [k for k in case if any(k.startswith(p) for p in GOLD_KEY_PREFIXES) or k.endswith("_hash")]
    if leaked:
        raise AssertionError(f"blind case leaks gold/private fields: {leaked}")


def build_system_prompt(layer: str) -> str:
    cfg = LAYERS[layer]
    parts = [
        "You are a governed NL2Metric planner. A governance contract has been compiled for the data layer "
        f"'{cfg['layer_label']}'. The COMPLETE governance contract is reproduced VERBATIM below. "
        "Treat it as binding executable policy, not as advisory context.",
        "",
        "===== BEGIN GOVERNANCE CONTRACT (VERBATIM FILE CONTENTS) =====",
    ]
    for fname in cfg["contract_files"]:
        fpath = cfg["dir"] / fname
        parts.append(f"----- file: {fname} -----")
        parts.append(fpath.read_text(encoding="utf-8").rstrip("\n"))
    parts.append("===== END GOVERNANCE CONTRACT =====")
    parts.append("")
    if cfg["extra_policy_text"]:
        parts.append(cfg["extra_policy_text"].rstrip("\n"))
        parts.append("")
    parts.append(POLICY_OBLIGATIONS.rstrip("\n"))
    parts.append("")
    parts.append(EXEC_DIRECTIVE)
    parts.append("")
    parts.append(OUTPUT_FORMAT.rstrip("\n"))
    return "\n".join(parts)


USER_TEMPLATE = (
    "Case {case_id}. Natural-language request:\n{nl_query}\n\n"
    "Execute the governance contract on this request and return the single JSON object now."
)


def load_cases(layer: str):
    cfg = LAYERS[layer]
    rows = read_jsonl(cfg["dir"] / cfg["cases_file"])
    if cfg["cases_are_blind"]:
        for row in rows:
            assert_blind(row)
        return rows
    blind = [strip_gold(row) for row in rows]
    for row in blind:
        assert_blind(row)
    return blind


def load_gold(layer: str):
    cfg = LAYERS[layer]
    if cfg["gold_file"]:
        rows = read_jsonl(cfg["dir"] / cfg["gold_file"])
    else:
        rows = read_jsonl(cfg["dir"] / cfg["cases_file"])
    return {r["case_id"]: r for r in rows}


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


_print_lock = threading.Lock()


def run_case(layer, case, system_prompt, contract_sha256, api_key):
    user = USER_TEMPLATE.format(case_id=case["case_id"], nl_query=case["nl_query"])
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}]
    prompt_sha = hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    record = {
        "layer": layer,
        "case_id": case["case_id"],
        "experiment_id": EXPERIMENT_ID,
        "llmhub_channel": LLMHUB_CHANNEL,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "prompt_sha256": prompt_sha,
        "contract_prompt_sha256": contract_sha256,
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


def cmd_run(layer: str, limit: int | None = None):
    load_env()
    api_key = os.environ["LLM_API_KEY"]
    cases = load_cases(layer)
    system_prompt = build_system_prompt(layer)
    contract_sha256 = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
    sp_path = HERE / "prompts" / f"{layer}_system.txt"
    if sp_path.exists():
        if sp_path.read_text(encoding="utf-8") != system_prompt:
            raise SystemExit(f"system prompt drift for layer {layer}; refusing to run")
    else:
        sp_path.parent.mkdir(parents=True, exist_ok=True)
        sp_path.write_text(system_prompt, encoding="utf-8")
    (HERE / "prompts" / "user_template.txt").write_text(USER_TEMPLATE, encoding="utf-8")

    raw_path = HERE / "raw_responses" / f"{layer}_raw.jsonl"
    done = set()
    if raw_path.exists():
        for row in read_jsonl(raw_path):
            if row.get("error") is None:
                done.add(row["case_id"])
    todo = [c for c in cases if c["case_id"] not in done]
    if limit is not None:
        todo = todo[:limit]
    print(f"[{layer}] cases={len(cases)} done={len(done)} todo={len(todo)}", flush=True)
    if not todo:
        return

    write_lock = threading.Lock()
    completed = 0
    with raw_path.open("a", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {
                pool.submit(run_case, layer, c, system_prompt, contract_sha256, api_key): c["case_id"]
                for c in todo
            }
            for fut in as_completed(futures):
                rec = fut.result()
                with write_lock:
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    fh.flush()
                completed += 1
                if completed % 10 == 0 or completed == len(todo):
                    with _print_lock:
                        print(f"[{layer}] {completed}/{len(todo)} (errors so far: n/a per-line)", flush=True)
    errs = [r for r in read_jsonl(raw_path) if r.get("error")]
    print(f"[{layer}] finished; error records: {len(errs)}", flush=True)


# ---------------- parsing ----------------

FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)


def extract_first_brace_block(text: str):
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
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


def parse_response(raw: str):
    """Pre-registered parsing rules (protocol.md section 5). Returns (parsed_dict|None, status)."""
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
        return {"action": "answer", "pred_metric_id": "__parse_error__", "pred_dimensions": [], "pred_time_window": "", "parse_status": status}
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
        # unexpected action label: keep fields, treat per scorer rule (empty metric -> refused)
        action = action or "answer"
    return {"action": action, "pred_metric_id": metric, "pred_dimensions": dims, "pred_time_window": tw, "parse_status": status, "reason": str(obj.get("reason") or "")[:400]}


# ---------------- scoring (mirror of released evaluators) ----------------

def score_rows(rows):
    """Mirror of the released scorers: same formulas as run_iowa_liquor_eval.py::score etc."""
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


def load_hierarchy(layer):
    cfg = LAYERS[layer]
    parents = {}
    dim_file = {
        "iowa": "dimension_catalog.jsonl",
        "chinook": "chinook_dimension_catalog.jsonl",
        "govtwin": "dimension_catalog.jsonl",
        "multigov": "dimension_catalog.jsonl",
        "ict": "dimension_catalog.jsonl",
    }[layer]
    dims = read_jsonl(cfg["dir"] / dim_file)
    for d in dims:
        if d.get("parent"):
            parents[d["dimension_id"]] = d["parent"]
    edges_file = cfg["dir"] / ("governance_edges.jsonl")
    if layer != "chinook" and edges_file.exists():
        for e in read_jsonl(edges_file):
            if e.get("edge_type") == "rolls_up_to":
                parents[e["src"]] = e["dst"]
    dim_ids = {d["dimension_id"] for d in dims}
    return parents, dim_ids


def load_metric_info(layer):
    cfg = LAYERS[layer]
    mfile = {
        "iowa": "metric_catalog.jsonl",
        "chinook": "chinook_metric_catalog.jsonl",
        "govtwin": "metric_catalog.jsonl",
        "multigov": "metric_catalog.jsonl",
        "ict": "metric_catalog.jsonl",
    }[layer]
    metrics = read_jsonl(cfg["dir"] / mfile)
    ids = {m["metric_id"] for m in metrics}
    allowed = {m["metric_id"]: set(m.get("allowed_dimensions") or []) for m in metrics if m.get("allowed_dimensions") is not None}
    has_allowed = any(m.get("allowed_dimensions") for m in metrics)
    return ids, allowed if has_allowed else None


def ancestors_of(dim, parents):
    out = set()
    cur = parents.get(dim)
    while cur:
        out.add(cur)
        cur = parents.get(cur)
    return out


def conformance(rows, layer):
    parents, dim_ids = load_hierarchy(layer)
    metric_ids, allowed = load_metric_info(layer)
    answers = [r for r in rows if r["action"] != "refuse" and r["pred_metric_id"]]
    n = len(answers)
    stats = {
        "n_answer_predictions": n,
        "metric_not_in_catalog": 0,
        "dimension_not_in_catalog": 0,
        "dimension_not_allowed": 0 if allowed is not None else None,
        "finest_grain_violation": 0,
    }
    for r in answers:
        if r["pred_metric_id"] not in metric_ids:
            stats["metric_not_in_catalog"] += 1
        pdims = set(r["pred_dimensions"])
        if any(d not in dim_ids for d in pdims):
            stats["dimension_not_in_catalog"] += 1
        if allowed is not None and r["pred_metric_id"] in allowed:
            if any(d not in allowed[r["pred_metric_id"]] for d in pdims if d in dim_ids):
                stats["dimension_not_allowed"] += 1
        if any((ancestors_of(d, parents) & pdims) for d in pdims):
            stats["finest_grain_violation"] += 1
    for key in ["metric_not_in_catalog", "dimension_not_in_catalog", "dimension_not_allowed", "finest_grain_violation"]:
        if stats.get(key) is None:
            stats[key + "_rate"] = None
        else:
            stats[key + "_rate"] = stats[key] / max(1, n)
    return stats


def cmd_score():
    out = {}
    all_pred_rows = {}
    for layer in LAYERS:
        raw_path = HERE / "raw_responses" / f"{layer}_raw.jsonl"
        if not raw_path.exists():
            continue
        raws = {}
        for row in read_jsonl(raw_path):
            # keep the last successful record per case; else last record
            prev = raws.get(row["case_id"])
            if prev is None or (prev.get("error") and not row.get("error")):
                raws[row["case_id"]] = row
        cases = load_cases(layer)
        gold = load_gold(layer)
        rows = []
        parse_counter = Counter()
        for case in cases:
            rec = raws.get(case["case_id"])
            if rec is None:
                parse_counter["missing"] += 1
                pred = normalize_prediction(None, "missing")
                extra = {"latency_ms": None, "usage": None, "prompt_sha256": None, "attempts": 0}
            else:
                obj, status = parse_response(rec.get("raw_response") if not rec.get("error") else None)
                pred = normalize_prediction(obj, status if not rec.get("error") else "api_error")
                parse_counter[pred["parse_status"]] += 1
                extra = {
                    "latency_ms": rec.get("latency_ms"),
                    "usage": rec.get("usage"),
                    "prompt_sha256": rec.get("prompt_sha256"),
                    "attempts": rec.get("attempts"),
                }
            g = gold[case["case_id"]]
            rows.append(
                {
                    "mode": "instructed_execution_verbatim_contract",
                    "model": MODEL,
                    "layer": layer,
                    "case_id": case["case_id"],
                    "nl_query": case["nl_query"],
                    "expected_action": g["expected_action"],
                    "expected_metric_id": g["expected_metric_id"],
                    "expected_dimensions": g["expected_dimensions"],
                    **pred,
                    **extra,
                }
            )
        if not rows:
            continue
        summary = score_rows(rows)
        summary["parse_status_counts"] = dict(parse_counter)
        summary["joint_wilson95"] = wilson_ci(summary["counts"]["joint_ok"], summary["n"])
        summary["errors_vs_calibergraph_exact_binomial_n_discordant"] = summary["n"] - summary["counts"]["joint_ok"]
        summary["conformance"] = conformance(rows, layer)
        lat = [r["latency_ms"] for r in rows if r.get("latency_ms")]
        usage_in = sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in rows if r.get("usage"))
        usage_out = sum((r.get("usage") or {}).get("completion_tokens", 0) for r in rows if r.get("usage"))
        summary["latency_ms_mean"] = sum(lat) / len(lat) if lat else None
        summary["total_prompt_tokens"] = usage_in
        summary["total_completion_tokens"] = usage_out
        out[layer] = summary
        all_pred_rows[layer] = rows
        write_jsonl(HERE / f"predictions_{layer}.jsonl", rows)
    (HERE / "scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("n", "metric_accuracy", "dimension_exact_accuracy", "joint_metric_dimension_accuracy", "refusal_precision", "refusal_recall", "parse_status_counts")} for k, v in out.items()}, ensure_ascii=False, indent=2, sort_keys=True))


# ---------------- scorer cross-check against released artifacts ----------------

def crosscheck_one(pred_path, results_path, results_key, mode_field="mode", gold_lookup=None, model_filter=None):
    preds = read_jsonl(pred_path)
    released = json.loads(Path(results_path).read_text(encoding="utf-8"))
    node = released
    for key in results_key:
        node = node[key]
    report = {}
    for mode in sorted({p[mode_field] for p in preds}):
        subset = [dict(p) for p in preds if p[mode_field] == mode]
        if model_filter and subset and subset[0].get("model") and mode.startswith("llm_"):
            pass
        for p in subset:
            if gold_lookup is not None:
                g = gold_lookup[p["case_id"]]
                p["expected_action"] = g["expected_action"]
                p["expected_metric_id"] = g["expected_metric_id"]
                p["expected_dimensions"] = g["expected_dimensions"]
        mine = score_rows(subset)
        theirs = node.get(mode)
        if theirs is None:
            report[mode] = {"status": "mode_not_in_released_results"}
            continue
        diffs = {}
        for key in ["metric_accuracy", "dimension_exact_accuracy", "joint_metric_dimension_accuracy", "refusal_precision", "refusal_recall"]:
            if key in theirs:
                diffs[key] = abs(mine[key] - theirs[key])
        report[mode] = {
            "status": "match" if all(d < 1e-9 for d in diffs.values()) else "MISMATCH",
            "max_abs_diff": max(diffs.values()) if diffs else None,
            "mine": {k: mine[k] for k in diffs},
            "released": {k: theirs[k] for k in diffs},
        }
    return report


def cmd_crosscheck():
    out = {}
    iowa_gold = {g["case_id"]: g for g in read_jsonl(PB / "iowa_liquor_metric_caliber" / "gold_labels.jsonl")}
    out["iowa"] = crosscheck_one(
        PB / "iowa_liquor_metric_caliber" / "results" / "iowa_liquor_predictions.jsonl",
        PB / "iowa_liquor_metric_caliber" / "results" / "iowa_liquor_eval_results.json",
        ["plan"],
        gold_lookup=iowa_gold,
    )
    govtwin_gold = {g["case_id"]: g for g in read_jsonl(PB / "govtwin_metric_caliber" / "gold_labels.jsonl")}
    out["govtwin"] = crosscheck_one(
        PB / "govtwin_metric_caliber" / "results" / "govtwin_predictions.jsonl",
        PB / "govtwin_metric_caliber" / "results" / "govtwin_eval_results.json",
        ["plan"],
        gold_lookup=govtwin_gold,
    )
    mg_gold = {g["case_id"]: g for g in read_jsonl(PB / "multigov_metric_caliber" / "gold_labels.jsonl")}
    out["multigov"] = crosscheck_one(
        PB / "multigov_metric_caliber" / "results" / "multigov_predictions.jsonl",
        PB / "multigov_metric_caliber" / "results" / "multigov_eval_results.json",
        ["summary"],
        gold_lookup=mg_gold,
    )
    ict_gold = {g["case_id"]: g for g in read_jsonl(PB / "industrial_case_text_metric_caliber" / "gold_labels.jsonl")}
    out["ict"] = crosscheck_one(
        PB / "industrial_case_text_metric_caliber" / "results" / "industrial_case_text_predictions.jsonl",
        PB / "industrial_case_text_metric_caliber" / "results" / "industrial_case_text_eval_results.json",
        ["summary"],
        gold_lookup=ict_gold,
    )
    out["chinook"] = crosscheck_one(
        PB / "experiments" / "public_chinook_predictions.jsonl",
        PB / "experiments" / "public_chinook_eval_results.json",
        [],
    )
    overall = all(
        item.get("status") == "match"
        for layer in out.values()
        for item in layer.values()
        if item.get("status") != "mode_not_in_released_results"
    )
    out["_overall_match"] = overall
    out["_ts_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (HERE / "scorer_crosscheck.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: ({m: v["status"] for m, v in rep.items()} if isinstance(rep, dict) else rep) for k, rep in out.items()}, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_prompts():
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "llmhub_channel": LLMHUB_CHANNEL,
        "model": MODEL,
        "layers": {},
    }
    for layer in LAYERS:
        sp = build_system_prompt(layer)
        path = HERE / "prompts" / f"{layer}_system.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sp, encoding="utf-8")
        manifest["layers"][layer] = {
            "system_prompt_file": str(path.relative_to(HERE)),
            "system_prompt_chars": len(sp),
            "system_prompt_bytes": len(sp.encode("utf-8")),
            "system_prompt_sha256": hashlib.sha256(sp.encode("utf-8")).hexdigest(),
            "contract_files": list(LAYERS[layer]["contract_files"]),
            "cases_file": LAYERS[layer]["cases_file"],
            "gold_file": LAYERS[layer]["gold_file"],
        }
        print(f"{layer}: system prompt {len(sp)} chars -> {path.name}")
    (HERE / "prompts" / "user_template.txt").write_text(USER_TEMPLATE, encoding="utf-8")
    (HERE / "prompt_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["crosscheck", "prompts", "run", "score"])
    ap.add_argument("--layer", choices=list(LAYERS), default=None)
    ap.add_argument("--limit", type=int, default=None, help="Run only the first N unfinished cases (canary/resume aid).")
    args = ap.parse_args()
    if args.cmd == "crosscheck":
        cmd_crosscheck()
    elif args.cmd == "prompts":
        cmd_prompts()
    elif args.cmd == "run":
        if not args.layer:
            raise SystemExit("--layer required for run")
        cmd_run(args.layer, args.limit)
    elif args.cmd == "score":
        cmd_score()


if __name__ == "__main__":
    main()
