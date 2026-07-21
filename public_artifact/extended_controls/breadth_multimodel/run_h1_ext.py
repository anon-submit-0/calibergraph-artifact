#!/usr/bin/env python3
"""H1 multi-model extension runner (pre-registered in protocol_ext.md).

Reuses the parent run's prompt builder, parser, scorer, and conformance code by
importing ../h1_instructed_execution/run_h1.py as a module. Only the transport
(model id + channel base/key) and the MultiGov stratified subsample are new.

Subcommands:
  subsample             write multigov_subsample_case_ids.json (deterministic, gold-free)
  run --model M --layer L   run one model on one layer (resumable)
  score                 parse + score everything, write scores_ext.json

Honesty: no mocked outputs; every prediction traces to a stored raw response.
Keys are read at runtime from ~/.config/llm_keys.env and never logged.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import sys
import threading
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT_DIR = HERE.parent / "h1_instructed_execution"

_spec = importlib.util.spec_from_file_location("run_h1", PARENT_DIR / "run_h1.py")
h1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h1)

MODELS = {
    "claude-opus-4-6": {"base_env": "RELAY_BASE", "base_default": "RELAY_ENDPOINT", "key_env": "RELAY_KEY_DEFAULT"},
    # 2026-07-11 amendment (protocol_ext.md "Amendment 1"): gpt-5.5 moved from
    # RELAY_KEY_DEFAULT to RELAY_KEY_GROUPB after diagnostics proved the default-group
    # deployment does not deliver long (~69k-token) system messages to the model
    # (systematic "contract not provided" replies despite billed prompt_tokens), while
    # the group-B deployment reads the identical prompt correctly. Transport fix only.
    "gpt-5.5": {"base_env": "RELAY_BASE", "base_default": "RELAY_ENDPOINT", "key_env": "RELAY_KEY_GROUPB"},
}
# Amendment 2 (protocol_ext.md, 2026-07-12): scope extended to the full five-layer matrix.
LAYERS_EXT = ["govtwin", "multigov", "ict", "iowa", "chinook"]
TEMPERATURE = 0
MAX_TOKENS = 4000
TIMEOUT_S = 240
CONCURRENCY = 4
RETRY_BACKOFF = [5, 15, 45]

SUBSAMPLE_SEED = 20260711
SUBSAMPLE_ALLOC = {
    "answerable_direct": 45,
    "denominator_caliber": 11,
    "finest_grain_trap": 64,
    "policy_refusal": 72,
    "temporal_anchor": 8,
}
SUBSAMPLE_PATH = HERE / "multigov_subsample_case_ids.json"


def safe_model_name(model: str) -> str:
    return model.replace("/", "_")


# ---------------- subsample ----------------

def build_subsample():
    cases = h1.load_cases("multigov")  # blind rows, gold-leak asserted absent
    by_family = {}
    for c in cases:
        by_family.setdefault(c["query_family"], []).append(c)
    counts = {f: len(v) for f, v in by_family.items()}
    # verify largest-remainder proportional allocation matches the pre-registered table
    total_n, k = len(cases), sum(SUBSAMPLE_ALLOC.values())
    quotas = {f: counts[f] * k / total_n for f in counts}
    floors = {f: int(quotas[f]) for f in quotas}
    remainder = k - sum(floors.values())
    order = sorted(quotas, key=lambda f: (-(quotas[f] - floors[f]), f))
    for f in order[:remainder]:
        floors[f] += 1
    assert floors == SUBSAMPLE_ALLOC, f"allocation drift: computed {floors} != pre-registered {SUBSAMPLE_ALLOC}"

    rng = random.Random(SUBSAMPLE_SEED)
    chosen = []
    for family in sorted(by_family):
        rows = sorted(by_family[family], key=lambda r: r["case_id"])
        chosen.extend(r["case_id"] for r in rng.sample(rows, SUBSAMPLE_ALLOC[family]))
    chosen = sorted(chosen)
    payload = {
        "seed": SUBSAMPLE_SEED,
        "allocation": SUBSAMPLE_ALLOC,
        "n": len(chosen),
        "sha256_of_ids": hashlib.sha256(json.dumps(chosen).encode()).hexdigest(),
        "case_ids": chosen,
    }
    return payload


def cmd_subsample():
    payload = build_subsample()
    if SUBSAMPLE_PATH.exists():
        prev = json.loads(SUBSAMPLE_PATH.read_text())
        if prev["case_ids"] != payload["case_ids"]:
            raise SystemExit("subsample drift vs existing file; refusing to overwrite")
        print("subsample already on disk and identical; nothing to do")
        return
    SUBSAMPLE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {SUBSAMPLE_PATH.name}: n={payload['n']} sha256={payload['sha256_of_ids'][:16]}...")


def load_subsample_ids():
    return set(json.loads(SUBSAMPLE_PATH.read_text())["case_ids"])


# ---------------- transport ----------------

def call_channel(messages, model, api_key, base):
    body = json.dumps(
        {"model": model, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS, "messages": messages},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
        return payload, int((time.time() - started) * 1000), resp.status


def run_case(layer, case, system_prompt, model, api_key, base):
    user = h1.USER_TEMPLATE.format(case_id=case["case_id"], nl_query=case["nl_query"])
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}]
    prompt_sha = hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    record = {
        "layer": layer,
        "case_id": case["case_id"],
        "model": model,
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
            payload, latency_ms, status = call_channel(messages, model, api_key, base)
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


def layer_cases(layer):
    cases = h1.load_cases(layer)
    if layer == "multigov":
        ids = load_subsample_ids()
        cases = [c for c in cases if c["case_id"] in ids]
        assert len(cases) == len(ids), "subsample ids not all present in blind cases"
    return cases


# ---------------- canary (Amendment 2, protocol_ext.md A2.2) ----------------

CANARY_N = 2
CANARY_USER_TEMPLATE = (
    "CANARY CHECK (this is NOT a benchmark case; do not execute any policy, do not plan any metric). "
    "To verify that the governance contract reproduced verbatim in the system message is visible to you: "
    "quote the FIRST 100 characters of the first line of the contract file '{fname}' exactly as shown above. "
    'Reply with exactly ONE JSON object and nothing else: {{"canary":"<those first 100 characters>"}}'
)
# Amendment 3 (protocol_ext.md): rev-2 wording works WITH the contract instead of against it —
# the model refuses per P2(g) (this request has no governed metric scope) but embeds the quote
# in its "reason" field. Pass criterion is identical to rev 1.
CANARY_USER_TEMPLATE_REV2 = (
    "TRANSPORT DIAGNOSTIC (not a benchmark case). This request intentionally contains no governed "
    'metric or scope, so under policy P2(g) of the contract your action MUST be "refuse" — that is '
    'correct and expected. To complete the diagnostic, your "reason" field MUST contain the exact '
    "first 100 characters of the first line of the contract file '{fname}' reproduced verbatim in the "
    "system message above (copy them character-for-character inside the reason string). Reply with "
    "exactly ONE JSON object in the mandated output format and nothing else."
)
CANARY_TEMPLATES = {1: CANARY_USER_TEMPLATE, 2: CANARY_USER_TEMPLATE_REV2}
# Amendment 3 rev-3: benchmark-style alias-resolution probes (see protocol_ext.md). The alias ->
# metric_id binding exists only in the layer's metric catalog; queries collide with no released case.
CANARY_REV3_PROBES = {
    "ict": ("上个月补发损失", "ict_metric_004"),
    "iowa": ("What was the AOV overall?", "average_invoice_value"),
    "chinook": ("What was the ARPC last year?", "revenue_per_customer"),
}


def canary_pass_rev3(raw_content, target_metric_id):
    """Rev-3 pass criterion: schema-conformant JSON reply AND target metric_id appears in it."""
    obj, _status = h1.parse_response(raw_content)
    if not isinstance(obj, dict) or "action" not in obj:
        return False
    return target_metric_id in str(raw_content)


def canary_true_line(layer):
    cfg = h1.LAYERS[layer]
    fname = cfg["contract_files"][0]
    first_line = (cfg["dir"] / fname).read_text(encoding="utf-8").splitlines()[0]
    return fname, first_line


def _collapse(s):
    return " ".join(str(s).split())


def canary_pass(raw_content, true_line):
    """Pre-registered pass criterion (A2.2): the whitespace-collapsed first 80 chars of the
    true first line appear in the reply (parsed canary field / raw / raw with \\\" unescaped)."""
    target = _collapse(true_line[:100])[:80]
    texts = []
    obj, _status = h1.parse_response(raw_content)
    if isinstance(obj, dict) and isinstance(obj.get("canary"), str):
        texts.append(obj["canary"])
    texts.append(str(raw_content))
    texts.append(str(raw_content).replace('\\"', '"'))
    joined = " \n ".join(_collapse(t) for t in texts)
    return target in joined


def canary_path(model, layer):
    return HERE / "raw_responses" / f"canary_{safe_model_name(model)}_{layer}.jsonl"


def canary_record_pass(r, layer):
    """Rev-aware recomputation of a stored canary record's pass status."""
    if r.get("error") or not r.get("raw_response"):
        return False
    if r.get("canary_rev") == 3:
        return canary_pass_rev3(r["raw_response"], CANARY_REV3_PROBES[layer][1])
    _fname, true_line = canary_true_line(layer)
    return canary_pass(r["raw_response"], true_line)


def canary_passes_on_disk(model, layer):
    path = canary_path(model, layer)
    if not path.exists():
        return 0
    return sum(1 for r in h1.read_jsonl(path) if canary_record_pass(r, layer))


def cmd_canary(model, layer, rev=1):
    h1.load_env()
    cfg = MODELS[model]
    api_key = os.environ.get(cfg["key_env"])
    if not api_key:
        raise SystemExit(f"{cfg['key_env']} not found in env file")
    base = os.environ.get(cfg["base_env"], cfg["base_default"])
    system_prompt = load_system_prompt(layer)
    fname, true_line = canary_true_line(layer)
    if rev == 3:
        if layer not in CANARY_REV3_PROBES:
            raise SystemExit(f"no rev-3 probe registered for layer {layer}")
        probe_query, _target = CANARY_REV3_PROBES[layer]
        user = h1.USER_TEMPLATE.format(case_id="__canary_probe__", nl_query=probe_query)
    else:
        user = CANARY_TEMPLATES[rev].format(fname=fname)
    path = canary_path(model, layer)
    path.parent.mkdir(parents=True, exist_ok=True)
    already = canary_passes_on_disk(model, layer)
    if already >= CANARY_N:
        print(f"[canary {model}/{layer}] already {already} passes on disk; nothing to do")
        return
    with path.open("a", encoding="utf-8") as fh:
        for i in range(CANARY_N - already):
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}]
            prompt_sha = hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            rec = {
                "is_canary": True,
                "canary_rev": rev,
                "layer": layer,
                "case_id": f"__canary_rev{rev}_{i+1+already}__",
                "model": model,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "prompt_sha256": prompt_sha,
                "canary_user_message": user,
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
                rec["attempts"] = attempt + 1
                try:
                    payload, latency_ms, status = call_channel(messages, model, api_key, base)
                    content = (payload.get("choices") or [{}])[0].get("message", {}).get("content")
                    if not content or not str(content).strip():
                        raise RuntimeError("empty content")
                    rec.update(
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
                    break
                except Exception as exc:  # noqa: BLE001 - record and retry honestly
                    last_err = f"{type(exc).__name__}: {exc}"
                    if attempt < len(RETRY_BACKOFF):
                        time.sleep(RETRY_BACKOFF[attempt])
            else:
                rec["error"] = f"api_error after {rec['attempts']} attempts: {last_err}"
                rec["ts_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            ok = canary_record_pass(rec, layer)
            rec["canary_pass"] = bool(ok)
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            print(f"[canary {model}/{layer}] call {i+1+already}/{CANARY_N} pass={ok}" + (f" error={rec['error']}" if rec.get("error") else ""))
    total = canary_passes_on_disk(model, layer)
    if total < CANARY_N:
        raise SystemExit(f"[canary {model}/{layer}] FAILED: only {total}/{CANARY_N} passes; benchmark run is blocked (A2.2)")
    print(f"[canary {model}/{layer}] OK: {total}/{CANARY_N} passes")


def load_system_prompt(layer):
    built = h1.build_system_prompt(layer)
    saved = (PARENT_DIR / "prompts" / f"{layer}_system.txt").read_text(encoding="utf-8")
    if built != saved:
        raise SystemExit(f"system prompt drift vs parent run for layer {layer}; refusing to run")
    return saved


def cmd_run(model, layer):
    h1.load_env()
    cfg = MODELS[model]
    api_key = os.environ.get(cfg["key_env"])
    if not api_key:
        raise SystemExit(f"{cfg['key_env']} not found in env file")
    base = os.environ.get(cfg["base_env"], cfg["base_default"])
    cases = layer_cases(layer)
    system_prompt = load_system_prompt(layer)

    raw_path = HERE / "raw_responses" / f"{safe_model_name(model)}_{layer}_raw.jsonl"
    done = set()
    if raw_path.exists():
        for row in h1.read_jsonl(raw_path):
            if row.get("error") is None:
                done.add(row["case_id"])
    todo = [c for c in cases if c["case_id"] not in done]
    print(f"[{model}/{layer}] cases={len(cases)} done={len(done)} todo={len(todo)}", flush=True)
    if not todo:
        return

    # Amendment 2 (A2.2): no new benchmark call without 2 canary passes on this channel.
    n_canary = canary_passes_on_disk(model, layer)
    if n_canary < CANARY_N:
        raise SystemExit(
            f"[{model}/{layer}] blocked by A2.2: {n_canary}/{CANARY_N} canary passes on disk; "
            f"run `run_h1_ext.py canary --model {model} --layer {layer}` first"
        )

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    write_lock = threading.Lock()
    completed = 0
    with raw_path.open("a", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {pool.submit(run_case, layer, c, system_prompt, model, api_key, base): c["case_id"] for c in todo}
            for fut in as_completed(futures):
                rec = fut.result()
                with write_lock:
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    fh.flush()
                completed += 1
                if completed % 10 == 0 or completed == len(todo):
                    print(f"[{model}/{layer}] {completed}/{len(todo)}", flush=True)
    errs = [r for r in h1.read_jsonl(raw_path) if r.get("error")]
    print(f"[{model}/{layer}] finished; error records: {len(errs)}", flush=True)


# ---------------- scoring ----------------

def score_model_layer(model, layer, gold, cases):
    raw_path = HERE / "raw_responses" / f"{safe_model_name(model)}_{layer}_raw.jsonl"
    if not raw_path.exists():
        return None, None
    raws = {}
    for row in h1.read_jsonl(raw_path):
        prev = raws.get(row["case_id"])
        if prev is None or (prev.get("error") and not row.get("error")):
            raws[row["case_id"]] = row
    rows = []
    parse_counter = Counter()
    for case in cases:
        rec = raws.get(case["case_id"])
        if rec is None:
            parse_counter["missing"] += 1
            pred = h1.normalize_prediction(None, "missing")
            extra = {"latency_ms": None, "usage": None, "prompt_sha256": None, "attempts": 0}
        else:
            obj, status = h1.parse_response(rec.get("raw_response") if not rec.get("error") else None)
            pred = h1.normalize_prediction(obj, status if not rec.get("error") else "api_error")
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
                "model": model,
                "layer": layer,
                "case_id": case["case_id"],
                "nl_query": case["nl_query"],
                "query_family": case.get("query_family"),
                "expected_action": g["expected_action"],
                "expected_metric_id": g["expected_metric_id"],
                "expected_dimensions": g["expected_dimensions"],
                **pred,
                **extra,
            }
        )
    if not rows:
        return None, None
    summary = h1.score_rows(rows)
    summary["parse_status_counts"] = dict(parse_counter)
    summary["joint_wilson95"] = h1.wilson_ci(summary["counts"]["joint_ok"], summary["n"])
    summary["n_errors_vs_calibergraph"] = summary["n"] - summary["counts"]["joint_ok"]
    summary["conformance"] = h1.conformance(rows, layer)
    summary.update(refusal_composition(rows))
    if layer == "multigov":
        summary["by_query_family"] = family_breakdown(rows)
    lat = [r["latency_ms"] for r in rows if r.get("latency_ms")]
    summary["latency_ms_mean"] = sum(lat) / len(lat) if lat else None
    summary["total_prompt_tokens"] = sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in rows if r.get("usage"))
    summary["total_completion_tokens"] = sum((r.get("usage") or {}).get("completion_tokens", 0) for r in rows if r.get("usage"))
    return summary, rows


def refusal_composition(rows):
    """Over-refusal composition: how many errors are false refusals, and where."""
    errors = [r for r in rows if not r["joint_ok"]]
    false_refusals = [r for r in errors if r["refused"] and r["expected_action"] != "refuse"]
    fam = Counter(r.get("query_family") or "n/a" for r in false_refusals)
    return {
        "n_total_errors": len(errors),
        "n_false_refusal_errors": len(false_refusals),
        "false_refusal_share_of_errors": (len(false_refusals) / len(errors)) if errors else None,
        "false_refusals_by_family": dict(fam),
    }


def family_breakdown(rows):
    out = {}
    for family in sorted({r["query_family"] for r in rows if r.get("query_family")}):
        sub = [r for r in rows if r.get("query_family") == family]
        ok = sum(1 for r in sub if r["joint_ok"])
        out[family] = {"n": len(sub), "joint_ok": ok, "joint_accuracy": ok / len(sub)}
    return out


def deepseek_reference(layer, gold, cases):
    """Re-score the parent run's stored deepseek predictions on exactly these cases.

    Parent prediction rows already carry expected_* and pred fields; we re-run the
    identical scorer on the restricted case set (identity on govtwin full set).
    """
    pred_path = PARENT_DIR / f"predictions_{layer}.jsonl"
    preds = {p["case_id"]: p for p in h1.read_jsonl(pred_path)}
    rows = []
    for case in cases:
        p = dict(preds[case["case_id"]])
        p["query_family"] = case.get("query_family")
        rows.append(p)
    summary = h1.score_rows(rows)
    summary["joint_wilson95"] = h1.wilson_ci(summary["counts"]["joint_ok"], summary["n"])
    summary["conformance"] = h1.conformance(rows, layer)
    summary.update(refusal_composition(rows))
    if layer == "multigov":
        summary["by_query_family"] = family_breakdown(rows)
    return summary


def completed_ids(model, layer):
    raw_path = HERE / "raw_responses" / f"{safe_model_name(model)}_{layer}_raw.jsonl"
    if not raw_path.exists():
        return set()
    return {r["case_id"] for r in h1.read_jsonl(raw_path) if not r.get("error")}


def cmd_score():
    out = {"_meta": {
        "protocol": "protocol_ext.md",
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "subsample_sha256": json.loads(SUBSAMPLE_PATH.read_text())["sha256_of_ids"],
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }}
    for layer in LAYERS_EXT:
        cases = layer_cases(layer)
        gold = h1.load_gold(layer)
        out.setdefault(layer, {})
        out[layer]["deepseek-3.2_reference_same_cases"] = deepseek_reference(layer, gold, cases)
        for model in MODELS:
            summary, rows = score_model_layer(model, layer, gold, cases)
            if summary is None:
                continue
            done = completed_ids(model, layer)
            n_blocked = len(cases) - len(done)
            if n_blocked > 0:
                # Transport outage (e.g. quota-blocked): primary scoring restricted to
                # cases with a stored successful response, paired with a deepseek
                # reference on the identical subset; the protocol-literal full-set
                # scoring (missing/api_error scored as wrong) is kept as a variant.
                summary["_partial_run"] = {
                    "n_transport_blocked": n_blocked,
                    "note": "cases without a successful raw response were blocked by channel quota (HTTP 403), not model behavior",
                }
                sub_cases = [c for c in cases if c["case_id"] in done]
                sub_summary, sub_rows = score_model_layer(model, layer, gold, sub_cases)
                out[layer][f"{model}__completed_subset_n{len(sub_cases)}"] = sub_summary
                out[layer][f"deepseek-3.2_reference_same_{len(sub_cases)}_cases"] = deepseek_reference(layer, gold, sub_cases)
                out[layer][f"{model}__protocol_literal_full_set"] = summary
                h1.write_jsonl(HERE / f"predictions_{safe_model_name(model)}_{layer}.jsonl", rows)
                continue
            out[layer][model] = summary
            h1.write_jsonl(HERE / f"predictions_{safe_model_name(model)}_{layer}.jsonl", rows)
    (HERE / "scores_ext.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    brief = {}
    for layer in LAYERS_EXT:
        brief[layer] = {}
        for key, v in out[layer].items():
            brief[layer][key] = {
                "n": v["n"],
                "joint": round(v["joint_metric_dimension_accuracy"], 4),
                "ref_p": round(v["refusal_precision"], 4),
                "ref_r": round(v["refusal_recall"], 4),
                "fgv_rate": v["conformance"]["finest_grain_violation_rate"],
                "false_refusal_errors": f"{v['n_false_refusal_errors']}/{v['n_total_errors']}",
            }
    print(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["subsample", "canary", "run", "score"])
    ap.add_argument("--model", choices=list(MODELS), default=None)
    ap.add_argument("--layer", choices=LAYERS_EXT, default=None)
    ap.add_argument("--canary-rev", type=int, choices=[1, 2, 3], default=1)
    args = ap.parse_args()
    if args.cmd == "subsample":
        cmd_subsample()
    elif args.cmd == "canary":
        if not (args.model and args.layer):
            raise SystemExit("--model and --layer required for canary")
        cmd_canary(args.model, args.layer, rev=args.canary_rev)
    elif args.cmd == "run":
        if not (args.model and args.layer):
            raise SystemExit("--model and --layer required for run")
        cmd_run(args.model, args.layer)
    elif args.cmd == "score":
        cmd_score()


if __name__ == "__main__":
    main()
