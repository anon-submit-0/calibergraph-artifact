#!/usr/bin/env python3
"""Arms B/C of protocol.md: LLM verbatim-contract instructed execution on
external_mf_metric_caliber.

Arms (pre-registered): (B) gpt-5.5, (C) deepseek-3.2; temperature=0; canary gate before
any benchmark call; raw responses stored per case (resumable); scoring formulas identical
to the compiler arm (score() copied via import from the validated h1 runner).

Reuse provenance (read-only imports, no historical file modified):
- serialize/prompt/parse/score pattern + parse_response/normalize_prediction/score_rows:
  _20260709/new_experiments/h1_instructed_execution/run_h1.py (imported
  via importlib; that code scored the released iowa/govtwin/multigov/ict runs and was
  cross-checked byte-exactly against released results in scorer_crosscheck.json).
- transport + retry + canary-gate structure:
  _20260709/new_experiments/private_strongest_controls_multimodel/
  run_strongest_controls_models.py (channels validated there and in
  h1_multimodel_extension: gpt-5.5 MUST use the relay group B, base
  RELAY_ENDPOINT, env RELAY_KEY_GROUPB, max_tokens 16000; deepseek-3.2 uses the
  <anon> gateway channel validated in h1: env <anon>_GW_KEY / <anon>_GW_BASE).

This layer ships ZERO private data, so unlike the private-layer experiments the full
system prompt and canary texts ARE persisted (llm_arms/prompts/, llm_arms/raw_responses/).
API keys are read at runtime from ~/.config/llm_keys.env (chmod 600) and are never
written to any file or log.

Canary gate (pre-declared, 2 calls per model, both must pass before the 122-case run):
- canary 1 "tail quotation": a no-metric diagnostic request; correct behavior is refuse;
  the reason field must reproduce the policy_id of the LAST line of policy_catalog.jsonl
  (the tail of the serialized contract) — verifies the contract survived transport
  untruncated and can be cited. Pass: that policy_id substring appears in the reply and
  the parsed action is "refuse" (or empty metric).
- canary 2 "tail behavior": a request for 'stock turnover' — an alias of the
  inventory_turnover protocol-added refusal stub near the catalog tail, chosen because it
  appears in NO benchmark query. Pass: parsed action == "refuse".

Subcommands:
  prompt                 build + persist the system prompt (no LLM)
  canary --model M       run the canary gate for one model
  run --model M          run the 122 blind cases (blocked unless 2/2 canary passes on disk)
  score                  parse + score both arms, pair vs compiler arm, exact McNemar,
                         write llm_arms_results.json + llm_arms/per_case_pairs.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import threading
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "external_mf_metric_caliber"
ARM_DIR = HERE / "llm_arms"
RAW_DIR = ARM_DIR / "raw_responses"
PROMPT_DIR = ARM_DIR / "prompts"
ENV_FILE = Path.home() / ".config" / "llm_keys.env"
H1 = Path(
    "<REPO_ROOT>/releases/"
    "_20260709/new_experiments/h1_instructed_execution/run_h1.py"
)

TEMPERATURE = 0
TIMEOUT_S = 300
CONCURRENCY = 6
RETRY_BACKOFF = [5, 15, 45]
CANARY_N = 2

MODELS = {
    "gpt-5.5": {"base_env": "RELAY_BASE", "base_default": "RELAY_ENDPOINT",
                "key_env": "RELAY_KEY_GROUPB", "max_tokens": 16000},
    "deepseek-3.2": {"base_env": "<anon>_GW_BASE", "base_default": "<GATEWAY_BASE>",
                     "key_env": "<anon>_GW_KEY", "max_tokens": 4000},
}

CONTRACT_FILES = [
    "metric_catalog.jsonl",
    "dimension_catalog.jsonl",
    "governance_edges.jsonl",
    "physical_coverage.jsonl",
    "metric_coverage_bindings.jsonl",
    "policy_catalog.jsonl",
    "contract_profile.json",
]

LAYER_LABEL = (
    "ExternalMF-MetricCaliber (contract mechanically converted from the third-party dbt Labs "
    "MetricFlow simple_manifest semantic layer; refusal policies are protocol-added)"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H1MOD = load_module("h1_run", H1)  # parse_response / normalize_prediction / score_rows / wilson_ci

# ---- policy obligations: h1 text with P3 adapted to this layer (no released time anchors) ----
POLICY_OBLIGATIONS = H1MOD.POLICY_OBLIGATIONS.replace(
    "P3. Time binding: when the request names no time window, bind the governed default time window "
    "(the metric's default_time if released, otherwise the current/default reporting window of this layer); "
    'report it in the "time_window" field.',
    "P3. Time binding: this layer releases NO time anchors (available_time_anchors is empty and "
    'default_time_anchor is ""); therefore the "time_window" field MUST be the empty string "".',
)

USER_TEMPLATE = H1MOD.USER_TEMPLATE

CANARY1 = (
    "TRANSPORT DIAGNOSTIC (not a benchmark case). This request intentionally names no governed metric, "
    'so under policy P2 of the contract your action MUST be "refuse" — that is correct and expected. '
    'To complete the diagnostic, your "reason" field MUST contain the exact policy_id string of the LAST '
    "line of the file policy_catalog.jsonl inside the GOVERNANCE CONTRACT block above, reproduced "
    "character-for-character. Reply with exactly ONE JSON object in the mandated output format and "
    "nothing else."
)
CANARY2 = "Kindly compute the stock turnover for our whole business."
CANARY2_TARGET_METRIC = "inventory_turnover"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def channel(model):
    load_env()
    cfg = MODELS[model]
    key = os.environ.get(cfg["key_env"])
    if not key:
        raise SystemExit(f"{cfg['key_env']} not found in env file")
    base = os.environ.get(cfg["base_env"], cfg["base_default"]).rstrip("/")
    return key, base


def build_system_prompt():
    parts = [
        "You are a governed NL2Metric planner. A governance contract has been compiled for the data layer "
        f"'{LAYER_LABEL}'. The COMPLETE governance contract is reproduced VERBATIM below. "
        "Treat it as binding executable policy, not as advisory context.",
        "",
        "===== BEGIN GOVERNANCE CONTRACT (VERBATIM FILE CONTENTS) =====",
    ]
    for fname in CONTRACT_FILES:
        parts.append(f"----- file: {fname} -----")
        parts.append((DATA / fname).read_text(encoding="utf-8").rstrip("\n"))
    parts.append("===== END GOVERNANCE CONTRACT =====")
    parts.append("")
    parts.append(POLICY_OBLIGATIONS.rstrip("\n"))
    parts.append("")
    parts.append(H1MOD.EXEC_DIRECTIVE)
    parts.append("")
    parts.append(H1MOD.OUTPUT_FORMAT.rstrip("\n"))
    return "\n".join(parts)


def persisted_prompt():
    path = PROMPT_DIR / "system_prompt.txt"
    prompt = build_system_prompt()
    if path.exists():
        if path.read_text(encoding="utf-8") != prompt:
            raise SystemExit("system prompt drift vs persisted copy; refusing to run")
    else:
        PROMPT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(prompt, encoding="utf-8")
        (PROMPT_DIR / "user_template.txt").write_text(USER_TEMPLATE, encoding="utf-8")
    return prompt


# ---------------- transport ----------------

def call_channel(messages, model, api_key, base):
    body = json.dumps(
        {"model": model, "temperature": TEMPERATURE, "max_tokens": MODELS[model]["max_tokens"],
         "messages": messages},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        base + "/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
        return payload, int((time.time() - started) * 1000), resp.status


def call_with_retries(messages, model, api_key, base):
    prompt_sha = sha256_text(json.dumps(messages, ensure_ascii=False, sort_keys=True))
    last_err = None
    for attempt in range(1 + len(RETRY_BACKOFF)):
        try:
            payload, latency_ms, status = call_channel(messages, model, api_key, base)
            content = (payload.get("choices") or [{}])[0].get("message", {}).get("content")
            if not content or not str(content).strip():
                raise RuntimeError("empty content")
            return {
                "prompt_sha256": prompt_sha,
                "prompt_chars": sum(len(m["content"]) for m in messages),
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
            body = ""
            if hasattr(exc, "read"):
                try:
                    body = exc.read().decode("utf-8", "replace")[:300]
                except Exception:
                    body = ""
            last_err = f"{type(exc).__name__}: {exc} {body}".strip()
            if attempt < len(RETRY_BACKOFF):
                time.sleep(RETRY_BACKOFF[attempt])
    return {
        "prompt_sha256": prompt_sha,
        "prompt_chars": sum(len(m["content"]) for m in messages),
        "attempts": 1 + len(RETRY_BACKOFF),
        "latency_ms": None,
        "usage": None,
        "raw_response": None,
        "finish_reason": None,
        "http_status": None,
        "error": f"api_error after {1 + len(RETRY_BACKOFF)} attempts: {last_err}",
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------- canary gate ----------------

def tail_policy_id():
    return read_jsonl(DATA / "policy_catalog.jsonl")[-1]["policy_id"]


def canary_pass(record, which):
    if record.get("error") or not record.get("raw_response"):
        return False
    raw = str(record["raw_response"])
    obj, _status = H1MOD.parse_response(raw)
    pred = H1MOD.normalize_prediction(obj, _status)
    refused = pred["action"] == "refuse" or not pred["pred_metric_id"]
    if which == 1:
        return refused and (tail_policy_id() in raw)
    return refused


def canary_path(model):
    return RAW_DIR / f"canary_{model.replace('/', '_')}.jsonl"


def canary_passes_on_disk(model):
    path = canary_path(model)
    if not path.exists():
        return 0
    return sum(1 for r in read_jsonl(path) if r.get("canary_pass"))


def cmd_canary(model):
    api_key, base = channel(model)
    system_prompt = persisted_prompt()
    already = canary_passes_on_disk(model)
    if already >= CANARY_N:
        print(f"[canary {model}] already {already}/{CANARY_N} passes on disk; gate open")
        return
    # sanity: canary-2 probe alias must collide with no benchmark query (pre-declared)
    queries = [c["nl_query"].lower() for c in read_jsonl(DATA / "blind_cases.jsonl")]
    assert not any("stock turnover" in q for q in queries), "canary probe collides with benchmark"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    plan = [(1, CANARY1), (2, CANARY2)][already:]
    with canary_path(model).open("a", encoding="utf-8") as fh:
        for which, user in plan:
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}]
            rec = call_with_retries(messages, model, api_key, base)
            row = {"is_canary": True, "canary_which": which, "case_id": f"__canary_{which}__",
                   "model": model, "temperature": TEMPERATURE,
                   "max_tokens": MODELS[model]["max_tokens"],
                   "canary_user_message": user,
                   "canary_expectation": ("refuse + cite tail policy_id " + tail_policy_id())
                   if which == 1 else f"refuse (tail stub {CANARY2_TARGET_METRIC})",
                   **rec}
            row["canary_pass"] = canary_pass(row, which)
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            print(f"[canary {model}] #{which} pass={row['canary_pass']}"
                  + (f" error={rec['error']}" if rec.get("error") else ""))
    total = canary_passes_on_disk(model)
    if total < CANARY_N:
        raise SystemExit(f"[canary {model}] FAILED: {total}/{CANARY_N}; benchmark run BLOCKED")
    print(f"[canary {model}] OK: {total}/{CANARY_N} passes; gate open")


# ---------------- benchmark run ----------------

def cmd_run(model):
    api_key, base = channel(model)
    if canary_passes_on_disk(model) < CANARY_N:
        raise SystemExit(f"[{model}] canary gate not passed; run `canary --model {model}` first")
    system_prompt = persisted_prompt()
    cases = read_jsonl(DATA / "blind_cases.jsonl")
    for c in cases:
        leaked = [k for k in c if k.startswith("expected_")]
        if leaked:
            raise AssertionError(f"blind case leaks gold fields: {leaked}")
    raw_path = RAW_DIR / f"{model.replace('/', '_')}_raw.jsonl"
    done = set()
    if raw_path.exists():
        for row in read_jsonl(raw_path):
            if row.get("error") is None and not row.get("is_canary"):
                done.add(row["case_id"])
    todo = [c for c in cases if c["case_id"] not in done]
    print(f"[{model}] cases={len(cases)} done={len(done)} todo={len(todo)}", flush=True)
    if not todo:
        return
    write_lock = threading.Lock()
    completed = 0

    def one(case):
        user = USER_TEMPLATE.format(case_id=case["case_id"], nl_query=case["nl_query"])
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}]
        rec = call_with_retries(messages, model, api_key, base)
        return {"case_id": case["case_id"], "model": model, "temperature": TEMPERATURE,
                "max_tokens": MODELS[model]["max_tokens"], **rec}

    with raw_path.open("a", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {pool.submit(one, c): c["case_id"] for c in todo}
            for fut in as_completed(futures):
                row = fut.result()
                with write_lock:
                    fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    fh.flush()
                completed += 1
                if completed % 10 == 0 or completed == len(todo):
                    print(f"[{model}] {completed}/{len(todo)}", flush=True)
    errs = [r for r in read_jsonl(raw_path) if r.get("error") and not r.get("is_canary")]
    print(f"[{model}] finished; error records: {len(errs)}", flush=True)


# ---------------- scoring + pairing vs compiler arm ----------------

def mcnemar_exact(b, c):
    """Two-sided exact binomial McNemar. b,c = discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    m = min(b, c)
    p = 2.0 * sum(math.comb(n, i) for i in range(0, m + 1)) * (0.5 ** n)
    return min(1.0, p)


def conformance(rows):
    metrics = read_jsonl(DATA / "metric_catalog.jsonl")
    dims = read_jsonl(DATA / "dimension_catalog.jsonl")
    metric_ids = {m["metric_id"] for m in metrics}
    allowed = {m["metric_id"]: set(m.get("allowed_dimensions") or []) for m in metrics}
    dim_ids = {d["dimension_id"] for d in dims}
    parents = {d["dimension_id"]: d.get("parent", "") for d in dims if d.get("parent")}

    def ancestors_of(dim):
        out, cur = set(), parents.get(dim)
        while cur:
            out.add(cur)
            cur = parents.get(cur)
        return out

    answers = [r for r in rows if r["action"] != "refuse" and r["pred_metric_id"]]
    n = len(answers)
    stats = {"n_answer_predictions": n, "metric_not_in_catalog": 0, "dimension_not_in_catalog": 0,
             "dimension_not_allowed": 0, "finest_grain_violation": 0}
    for r in answers:
        if r["pred_metric_id"] not in metric_ids:
            stats["metric_not_in_catalog"] += 1
        pdims = set(r["pred_dimensions"])
        if any(d not in dim_ids for d in pdims):
            stats["dimension_not_in_catalog"] += 1
        if r["pred_metric_id"] in allowed and any(
                d not in allowed[r["pred_metric_id"]] for d in pdims if d in dim_ids):
            stats["dimension_not_allowed"] += 1
        if any((ancestors_of(d) & pdims) for d in pdims):
            stats["finest_grain_violation"] += 1
    for key in list(stats):
        if key != "n_answer_predictions":
            stats[key + "_rate"] = stats[key] / max(1, n)
    return stats


def cmd_score():
    cases = read_jsonl(DATA / "blind_cases.jsonl")
    gold = {g["case_id"]: g for g in read_jsonl(DATA / "gold_labels.jsonl")}
    audit = json.loads((DATA / "generation_audit.json").read_text(encoding="utf-8"))
    strata_of = {cid: s for s, ids in audit["strata_case_ids"].items() for cid in ids}
    compiler_rows = {
        r["case_id"]: r
        for r in read_jsonl(DATA / "results" / "compiler_arm_predictions.jsonl")
        if r["mode"] == "caliber_graph_longest_alias"
    }
    out = {"dataset_id": "external_mf_metric_caliber",
           "arms": {},
           "pairing_reference_arm": "A_compiler (caliber_graph_longest_alias)",
           "compiler_joint": sum(compiler_rows[c["case_id"]]["joint_ok"] for c in cases),
           "n_cases": len(cases)}
    pairs_out = []
    for model in MODELS:
        raw_path = RAW_DIR / f"{model.replace('/', '_')}_raw.jsonl"
        if not raw_path.exists():
            out["arms"][model] = {"status": "not_run"}
            continue
        raws = {}
        for row in read_jsonl(raw_path):
            if row.get("is_canary"):
                continue
            prev = raws.get(row["case_id"])
            if prev is None or (prev.get("error") and not row.get("error")):
                raws[row["case_id"]] = row
        rows, parse_counter = [], Counter()
        for case in cases:
            rec = raws.get(case["case_id"])
            if rec is None:
                pred = H1MOD.normalize_prediction(None, "missing")
                parse_counter["missing"] += 1
                extra = {"latency_ms": None, "usage": None, "prompt_sha256": None, "attempts": 0}
            else:
                obj, status = H1MOD.parse_response(rec.get("raw_response") if not rec.get("error") else None)
                pred = H1MOD.normalize_prediction(obj, status if not rec.get("error") else "api_error")
                parse_counter[pred["parse_status"]] += 1
                extra = {"latency_ms": rec.get("latency_ms"), "usage": rec.get("usage"),
                         "prompt_sha256": rec.get("prompt_sha256"), "attempts": rec.get("attempts")}
            g = gold[case["case_id"]]
            rows.append({
                "mode": f"llm_instructed_execution_{model}",
                "model": model,
                "case_id": case["case_id"],
                "nl_query": case["nl_query"],
                "stratum": strata_of[case["case_id"]],
                "expected_action": g["expected_action"],
                "expected_metric_id": g["expected_metric_id"],
                "expected_dimensions": g["expected_dimensions"],
                **pred,
                **extra,
            })
        summary = H1MOD.score_rows(rows)  # sets joint_ok etc. in place; same formulas as compiler arm
        summary["parse_status_counts"] = dict(parse_counter)
        summary["joint_wilson95"] = H1MOD.wilson_ci(summary["counts"]["joint_ok"], summary["n"])
        by = {}
        for r in rows:
            by.setdefault(r["stratum"], []).append(r)
        summary["per_stratum"] = {
            s: {"n": len(v),
                "joint_metric_dimension_accuracy": sum(r["joint_ok"] for r in v) / len(v),
                "metric_accuracy": sum(r["metric_ok"] for r in v) / len(v),
                "dimension_exact_accuracy": sum(r["dimension_exact_ok"] for r in v) / len(v)}
            for s, v in sorted(by.items())
        }
        summary["conformance"] = conformance(rows)
        lat = [r["latency_ms"] for r in rows if r.get("latency_ms")]
        summary["latency_ms_mean"] = sum(lat) / len(lat) if lat else None
        summary["total_prompt_tokens"] = sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in rows)
        summary["total_completion_tokens"] = sum((r.get("usage") or {}).get("completion_tokens", 0) for r in rows)
        summary["canary"] = {"passes": canary_passes_on_disk(model), "required": CANARY_N}
        # pairing vs compiler arm
        b = c = 0
        disagreements = []
        for r in rows:
            comp = compiler_rows[r["case_id"]]
            pair = {"case_id": r["case_id"], "stratum": r["stratum"],
                    "compiler_joint_ok": comp["joint_ok"], "llm_joint_ok": r["joint_ok"],
                    "model": model}
            pairs_out.append(pair)
            if comp["joint_ok"] and not r["joint_ok"]:
                b += 1
                disagreements.append({"case_id": r["case_id"], "nl_query": r["nl_query"],
                                      "stratum": r["stratum"],
                                      "llm_action": r["action"], "llm_metric": r["pred_metric_id"],
                                      "llm_dims": r["pred_dimensions"],
                                      "expected_action": r["expected_action"],
                                      "expected_metric": r["expected_metric_id"],
                                      "expected_dims": r["expected_dimensions"],
                                      "parse_status": r["parse_status"]})
            elif r["joint_ok"] and not comp["joint_ok"]:
                c += 1
        summary["paired_vs_compiler"] = {
            "discordant_compiler_only_correct_b": b,
            "discordant_llm_only_correct_c": c,
            "mcnemar_exact_two_sided_p": mcnemar_exact(b, c),
            "disagreement_cases": disagreements,
        }
        out["arms"][model] = summary
        (ARM_DIR / f"predictions_{model.replace('/', '_')}.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n",
            encoding="utf-8")
    (ARM_DIR / "per_case_pairs.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in pairs_out) + "\n",
        encoding="utf-8")
    out["repro"] = [
        "python3 run_llm_arms.py prompt",
        "python3 run_llm_arms.py canary --model gpt-5.5",
        "python3 run_llm_arms.py canary --model deepseek-3.2",
        "python3 run_llm_arms.py run --model gpt-5.5",
        "python3 run_llm_arms.py run --model deepseek-3.2",
        "python3 run_llm_arms.py score",
    ]
    (HERE / "llm_arms_results.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact = {m: ({k: v.get(k) for k in ("n", "joint_metric_dimension_accuracy", "metric_accuracy",
                                          "dimension_exact_accuracy", "refusal_precision", "refusal_recall",
                                          "parse_status_counts")}
                   | {"mcnemar_p": v.get("paired_vs_compiler", {}).get("mcnemar_exact_two_sided_p"),
                      "b": v.get("paired_vs_compiler", {}).get("discordant_compiler_only_correct_b"),
                      "c": v.get("paired_vs_compiler", {}).get("discordant_llm_only_correct_c")}
                   if v.get("counts") else v)
               for m, v in out["arms"].items()}
    print(json.dumps(compact, ensure_ascii=False, indent=2, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prompt", "canary", "run", "score"])
    ap.add_argument("--model", choices=list(MODELS), default=None)
    args = ap.parse_args()
    if args.cmd == "prompt":
        prompt = persisted_prompt()
        print(f"system prompt: {len(prompt)} chars, sha256={sha256_text(prompt)}")
    elif args.cmd == "canary":
        if not args.model:
            raise SystemExit("--model required")
        cmd_canary(args.model)
    elif args.cmd == "run":
        if not args.model:
            raise SystemExit("--model required")
        cmd_run(args.model)
    elif args.cmd == "score":
        cmd_score()


if __name__ == "__main__":
    main()
