#!/usr/bin/env python3
"""Strongest-MODEL controls on the private 159-case set (pre-registered in protocol_ext_models.md).

Models: gpt-5.5 (relay group B) and claude-opus-4-6 (relay default group).
Arms per model (inherited byte-identical from ../private_strongest_controls/run_strongest_controls.py,
which this script IMPORTS as a module rather than copying):
  Arm C: instructed-execution (full private governance contract verbatim in system prompt)
  Arm D: validator-feedback replanning loop (round 0 = original single-case Schema-RAG prompt,
         <=3 repair rounds with the deterministic released-policy validator)

Subcommands:
  canary --model M   2 canary calls with the exact Arm C system prompt; hard gate for benchmark runs
  run --arm c|d --model M   resumable per case; blocked unless 2 canary passes on disk
  score              score all arms, pair against Arm A -> per_case_pairs_models.jsonl + mcnemar_models.json

Honesty: no mocked outputs; every prediction traces to a stored raw response written before scoring.
Privacy: prompts NOT persisted (SHA-256 + char count only); output tables carry identifiers/booleans/
hashes only, never private query text. API keys read from env file, never logged.
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
RAW_DIR = HERE / "raw_responses"
PARENT = HERE.parent / "private_strongest_controls"
ENV_FILE = Path.home() / ".config" / "llm_keys.env"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SC = load_module("sc_parent", PARENT / "run_strongest_controls.py")  # parent runner: prompts/validator/scoring
LE = SC.LE  # original private eval module (loaders, build_prompt, normalize_prediction)

MODELS = {
    # channels validated in ../h1_multimodel_extension/ (gpt-5.5 on group B per its Amendment 1;
    # the relay default group demonstrably drops long system messages for gpt-5.5).
    "gpt-5.5": {"base_default": "RELAY_ENDPOINT", "key_env": "RELAY_KEY_GROUPB", "max_tokens": 16000},
    "claude-opus-4-6": {"base_default": "RELAY_ENDPOINT", "key_env": "RELAY_KEY_DEFAULT", "max_tokens": 8000},
}
TEMPERATURE = 0
TIMEOUT_S = 240
CONCURRENCY = 6
RETRY_BACKOFF = [5, 15, 45]
MAX_REPAIR_ROUNDS = 3
ARM_A_JOINT = 147  # 0.9245283 of 159
CANARY_N = 2

sha256_text = SC.sha256_text
read_jsonl = SC.read_jsonl


def safe_model_name(model: str) -> str:
    return model.replace("/", "_")


def load_env_key(model):
    LE.load_env_file(ENV_FILE)
    cfg = MODELS[model]
    key = os.environ.get(cfg["key_env"])
    if not key:
        raise SystemExit(f"{cfg['key_env']} not found in env file")
    base = os.environ.get("RELAY_BASE", cfg["base_default"]).rstrip("/")
    return key, base


# ---------------- transport (per-model; mirrors parent call_with_retries) ----------------


def call_channel(messages, model, api_key, base):
    cfg = MODELS[model]
    body = json.dumps(
        {"model": model, "temperature": TEMPERATURE, "max_tokens": cfg["max_tokens"], "messages": messages},
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
            last_err = f"{type(exc).__name__}: {exc}"
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


_print_lock = threading.Lock()


# ---------------- canary gate (protocol_ext_models.md section 3) ----------------

CANARY_TEMPLATE = (
    "TRANSPORT DIAGNOSTIC (not a benchmark case). This request intentionally names no governed metric, "
    'so under policy P2 of the contract your action MUST be "refuse" — that is correct and expected. '
    'To complete the diagnostic, your "reason" field MUST contain the exact first 100 characters of the '
    "first line of the GOVERNANCE CONTRACT block (the line immediately after '===== BEGIN GOVERNANCE "
    "CONTRACT ====='), reproduced character-for-character inside the reason string. Reply with exactly "
    "ONE JSON object in the mandated output format and nothing else."
)


def _collapse(s):
    return " ".join(str(s).split())


def contract_first_line(cat):
    return SC.serialize_contract(cat).splitlines()[0]


def canary_pass(raw_content, true_line):
    """Pass criterion (pre-registered): whitespace-collapsed first 80 chars of the true first line
    appear in the reply (parsed object fields / raw / raw with escaped quotes unescaped)."""
    target = _collapse(true_line[:100])[:80]
    texts = []
    obj, _status = SC.parse_single_object(raw_content)
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, str):
                texts.append(v)
    texts.append(str(raw_content))
    texts.append(str(raw_content).replace('\\"', '"'))
    joined = " \n ".join(_collapse(t) for t in texts)
    return target in joined


def canary_path(model):
    return RAW_DIR / f"canary_{safe_model_name(model)}.jsonl"


# Amendment 1 (protocol_ext_models.md): rev-3 behavioral alias-resolution probe, used because gpt-5.5
# categorically refuses quotation canaries while demonstrably citing contract policy labels ("P2").
REV3_PROBE_METRIC = "sale_qty"


def rev3_probe(cat, cases):
    """First catalog-order alias of the probe metric appearing in NO benchmark query text."""
    queries = [c["nl_query"] for c in cases]
    for alias in cat.metric_aliases.get(REV3_PROBE_METRIC, []):
        if alias and not any(alias in q for q in queries):
            return "上个月" + alias + "是多少"
    raise SystemExit("no collision-free alias for rev-3 probe")


def canary_pass_rev3(raw_content):
    obj, _status = SC.parse_single_object(raw_content)
    if not isinstance(obj, dict) or "action" not in obj:
        return False
    return REV3_PROBE_METRIC in str(raw_content)


def canary_record_pass(r, true_line):
    if r.get("error") or not r.get("raw_response"):
        return False
    if r.get("canary_rev") == 3:
        return canary_pass_rev3(r["raw_response"])
    return canary_pass(r["raw_response"], true_line)


def canary_passes_on_disk(model, true_line):
    path = canary_path(model)
    if not path.exists():
        return 0
    return sum(1 for r in read_jsonl(path) if canary_record_pass(r, true_line))


def cmd_canary(model, rev=1):
    api_key, base = load_env_key(model)
    cat = SC.Catalog()
    system_prompt = SC.build_system_prompt(cat)
    true_line = contract_first_line(cat)
    already = canary_passes_on_disk(model, true_line)
    if already >= CANARY_N:
        print(f"[canary {model}] already {already}/{CANARY_N} passes on disk; gate open")
        return
    if rev == 3:
        user = rev3_probe(cat, LE.load_cases())
    else:
        user = CANARY_TEMPLATE
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with canary_path(model).open("a", encoding="utf-8") as fh:
        for i in range(CANARY_N - already):
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}]
            rec = call_with_retries(messages, model, api_key, base)
            row = {"is_canary": True, "canary_rev": rev, "case_id": f"__canary_rev{rev}_{already + i + 1}__",
                   "model": model, "temperature": TEMPERATURE, "max_tokens": MODELS[model]["max_tokens"], **rec}
            if rev == 3:
                # privacy: probe text embeds a private catalog alias; store hash + target id only
                row["canary_probe_sha256"] = sha256_text(user)
                row["canary_target_metric_id"] = REV3_PROBE_METRIC
            else:
                row["canary_user_message"] = user
            ok = canary_record_pass(row, true_line)
            row["canary_pass"] = ok
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            print(f"[canary {model}] rev={rev} call {already + i + 1}/{CANARY_N} pass={ok}"
                  + (f" error={rec['error']}" if rec.get("error") else ""))
    total = canary_passes_on_disk(model, true_line)
    if total < CANARY_N:
        raise SystemExit(f"[canary {model}] FAILED: only {total}/{CANARY_N} passes; benchmark run is BLOCKED")
    print(f"[canary {model}] OK: {total}/{CANARY_N} passes; gate open")


def assert_canary_gate(model, cat):
    total = canary_passes_on_disk(model, contract_first_line(cat))
    if total < CANARY_N:
        raise SystemExit(f"[{model}] blocked by canary gate: {total}/{CANARY_N} passes on disk; run `canary --model {model}` first")


# ---------------- Arm C run (per model) ----------------


def run_arm_c(model):
    api_key, base = load_env_key(model)
    cat = SC.Catalog()
    assert_canary_gate(model, cat)
    cases = LE.load_cases()
    assert len(cases) == 159, f"expected 159 cases, got {len(cases)}"
    system_prompt = SC.build_system_prompt(cat)
    sp_sha = sha256_text(system_prompt)
    print(f"[armC {model}] system prompt sha256={sp_sha} chars={len(system_prompt)} (NOT persisted)", flush=True)

    raw_path = RAW_DIR / f"armC_{safe_model_name(model)}_raw.jsonl"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    done = set()
    if raw_path.exists():
        for row in read_jsonl(raw_path):
            if row.get("error") is None:
                done.add(row["case_id"])
    todo = [c for c in cases if c["case_id"] not in done]
    print(f"[armC {model}] cases={len(cases)} done={len(done)} todo={len(todo)}", flush=True)
    if not todo:
        return

    def one(case):
        user = SC.USER_TEMPLATE.format(case_id=case["case_id"], nl_query=case["nl_query"])
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}]
        rec = call_with_retries(messages, model, api_key, base)
        return {"arm": "C", "case_id": case["case_id"], "model": model, "temperature": TEMPERATURE,
                "max_tokens": MODELS[model]["max_tokens"], "system_prompt_sha256": sp_sha, **rec}

    write_lock = threading.Lock()
    completed = 0
    with raw_path.open("a", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {pool.submit(one, c): c["case_id"] for c in todo}
            for fut in as_completed(futures):
                rec = fut.result()
                with write_lock:
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    fh.flush()
                completed += 1
                if completed % 10 == 0 or completed == len(todo):
                    with _print_lock:
                        print(f"[armC {model}] {completed}/{len(todo)}", flush=True)
    errs = [r for r in read_jsonl(raw_path) if r.get("error")]
    print(f"[armC {model}] finished; error records: {len(errs)}", flush=True)


# ---------------- Arm D run (per model) ----------------


def run_case_loop(cat, case, model, api_key, base):
    catalogs = (cat.metrics, cat.dims, cat.metric_dims, cat.required_fields,
                cat.coverage_by_dim, cat.physical_columns)
    prompt0 = LE.build_prompt("llm_schema_rag", [case], *catalogs)
    messages = [{"role": "user", "content": prompt0}]
    rounds = []
    for rnd in range(MAX_REPAIR_ROUNDS + 1):
        rec = call_with_retries(messages, model, api_key, base)
        if rec["error"] is not None:
            rounds.append({"round": rnd, **rec, "prediction": None, "validator_verdict": None, "feedback_text": None})
            break
        if rnd == 0:
            obj, status = SC.parse_round0(rec["raw_response"], case["case_id"])
        else:
            obj, status = SC.parse_single_object(rec["raw_response"])
        pred = SC.normalize_d(obj, case["case_id"], status)
        violations = SC.validate(cat, pred, case["nl_query"])
        entry = {
            "round": rnd,
            **rec,
            "prediction": pred,
            "validator_verdict": {"pass": not violations, "violations": violations},
            "feedback_text": None,
        }
        if violations and rnd < MAX_REPAIR_ROUNDS:
            feedback = SC.build_feedback(pred, violations)
            entry["feedback_text"] = feedback
            messages.append({"role": "assistant", "content": rec["raw_response"]})
            messages.append({"role": "user", "content": feedback})
        rounds.append(entry)
        if not violations:
            break
    return {
        "arm": "D",
        "case_id": case["case_id"],
        "model": model,
        "temperature": TEMPERATURE,
        "max_tokens": MODELS[model]["max_tokens"],
        "n_llm_calls": len(rounds),
        "rounds": rounds,
    }


def run_arm_d(model):
    api_key, base = load_env_key(model)
    cat = SC.Catalog()
    assert_canary_gate(model, cat)
    cases = LE.load_cases()
    assert len(cases) == 159, f"expected 159 cases, got {len(cases)}"
    raw_path = RAW_DIR / f"armD_{safe_model_name(model)}_loop_raw.jsonl"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    done = set()
    if raw_path.exists():
        for row in read_jsonl(raw_path):
            if row["rounds"] and row["rounds"][-1].get("error") is None:
                done.add(row["case_id"])
    todo = [c for c in cases if c["case_id"] not in done]
    print(f"[armD {model}] cases={len(cases)} done={len(done)} todo={len(todo)}", flush=True)
    if not todo:
        return
    write_lock = threading.Lock()
    completed = 0
    with raw_path.open("a", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {pool.submit(run_case_loop, cat, c, model, api_key, base): c["case_id"] for c in todo}
            for fut in as_completed(futures):
                rec = fut.result()
                with write_lock:
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    fh.flush()
                completed += 1
                if completed % 10 == 0 or completed == len(todo):
                    with _print_lock:
                        print(f"[armD {model}] {completed}/{len(todo)}", flush=True)
    errs = [r for r in read_jsonl(raw_path) if any(x.get("error") for x in r["rounds"])]
    print(f"[armD {model}] finished; case records with api errors: {len(errs)}", flush=True)


# ---------------- scoring (mirrors parent cmd_score; per model) ----------------


def holm_adjust(pvals):
    """Holm-Bonferroni step-down; pvals is dict name->p. Returns dict name->adjusted p."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj, running = {}, 0.0
    for i, (name, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[name] = running
    return adj


def score_model(model, cases, pairs_a, a_flags):
    """Returns (blocks dict, per-case fields dict keyed by case_id)."""
    cat = SC.Catalog()
    mslug = safe_model_name(model)

    c_raws = {}
    c_path = RAW_DIR / f"armC_{mslug}_raw.jsonl"
    if c_path.exists():
        for row in read_jsonl(c_path):
            prev = c_raws.get(row["case_id"])
            if prev is None or (prev.get("error") and not row.get("error")):
                c_raws[row["case_id"]] = row
    preds_c, c_parse = {}, Counter()
    for case in cases:
        rec = c_raws.get(case["case_id"])
        if rec is None or rec.get("error"):
            pred = SC.normalize_c(None, "api_error" if rec else "missing")
        else:
            obj, status = SC.parse_single_object(rec["raw_response"])
            pred = SC.normalize_c(obj, status)
        c_parse[pred["parse_status"]] += 1
        preds_c[case["case_id"]] = pred

    d_path = RAW_DIR / f"armD_{mslug}_loop_raw.jsonl"
    d_recs = {r["case_id"]: r for r in read_jsonl(d_path)} if d_path.exists() else {}
    preds_d0, preds_df, rounds_used, final_pass = {}, {}, {}, {}
    d_missing = [c["case_id"] for c in cases if c["case_id"] not in d_recs]
    for case in cases:
        rec = d_recs.get(case["case_id"])
        if rec is None:
            empty = SC.normalize_d(None, case["case_id"], "missing")
            preds_d0[case["case_id"]] = empty
            preds_df[case["case_id"]] = empty
            rounds_used[case["case_id"]] = 0
            final_pass[case["case_id"]] = None
            continue
        usable = [r for r in rec["rounds"] if r.get("prediction") is not None]
        r0 = rec["rounds"][0]
        preds_d0[case["case_id"]] = r0["prediction"] if r0.get("prediction") else SC.normalize_d(None, case["case_id"], "api_error")
        last = usable[-1] if usable else None
        preds_df[case["case_id"]] = last["prediction"] if last else SC.normalize_d(None, case["case_id"], "api_error")
        rounds_used[case["case_id"]] = rec["n_llm_calls"]
        final_pass[case["case_id"]] = (last["validator_verdict"]["pass"] if last and last.get("validator_verdict") else None)

    block_c, c_flags = SC.arm_block(
        f"Arm C-{model} — instructed-execution (full private contract verbatim, {model}, temperature=0)",
        cases, preds_c, a_flags)
    block_c["parse_status_counts"] = dict(c_parse)
    block_d0, d0_flags = SC.arm_block(
        f"Arm D-{model} round 0 — single-case Schema-RAG replicate", cases, preds_d0, a_flags)
    block_df, df_flags = SC.arm_block(
        f"Arm D-{model} final — validator-feedback replanning loop (<=3 repairs)", cases, preds_df, a_flags)

    b_gain = sum(1 for x, y in zip(d0_flags, df_flags) if not x and y)
    c_loss = sum(1 for x, y in zip(d0_flags, df_flags) if x and not y)
    viol_r0, viol_final = Counter(), Counter()
    invisible = []
    for case in cases:
        rec = d_recs.get(case["case_id"])
        if not rec:
            continue
        r0v = (rec["rounds"][0].get("validator_verdict") or {}).get("violations", [])
        usable = [r for r in rec["rounds"] if r.get("validator_verdict") is not None]
        lastv = (usable[-1]["validator_verdict"] if usable else {"pass": False, "violations": [{"type": "api_error"}]})
        for t in {v["type"] for v in r0v}:
            viol_r0[t] += 1
        for t in {v["type"] for v in lastv.get("violations", [])}:
            viol_final[t] += 1
        _, _, j = SC.score_case(case, preds_df[case["case_id"]])
        if usable and lastv["pass"] and not j:
            p = preds_df[case["case_id"]]
            m_ok, d_ok, _ = SC.score_case(case, p)
            invisible.append({
                "case_id": case["case_id"],
                "kind": ("wrong_metric_only" if (not m_ok and d_ok) else
                         "wrong_dimension_set_only" if (m_ok and not d_ok) else "wrong_metric_and_dimensions"),
                "pred_metric_id": p["pred_metric_id"],
                "expected_metric_id": case["expected_metric_id"],
                "pred_dimensions": p["pred_dimensions"],
                "expected_dimensions": case["expected_dimensions"],
            })
    calls = [rounds_used[c["case_id"]] for c in cases if c["case_id"] in d_recs]
    pt = ct = 0
    for rec in d_recs.values():
        for rd in rec["rounds"]:
            u = rd.get("usage") or {}
            pt += u.get("prompt_tokens") or 0
            ct += u.get("completion_tokens") or 0
    cpt = cct = 0
    for rec in c_raws.values():
        u = rec.get("usage") or {}
        cpt += u.get("prompt_tokens") or 0
        cct += u.get("completion_tokens") or 0

    block_df["loop_diagnostics"] = {
        "round0_joint": block_d0["joint_accuracy"],
        "final_joint": block_df["joint_accuracy"],
        "discordant_wrong_to_right": b_gain,
        "discordant_right_to_wrong": c_loss,
        "sign_test_p_two_sided": SC.sign_test_two_sided(b_gain, c_loss),
        "violations_round0": dict(viol_r0),
        "violations_final": dict(viol_final),
        "validator_invisible_errors_final": {"n": len(invisible),
                                             "by_kind": dict(Counter(x["kind"] for x in invisible)),
                                             "cases": invisible},
        "llm_calls_total": sum(calls),
        "llm_calls_per_case_mean": sum(calls) / max(1, len(calls)),
        "llm_calls_per_case_max": max(calls) if calls else 0,
        "cases_resolved_at_round0": sum(1 for c2 in calls if c2 == 1),
        "total_prompt_tokens": pt,
        "total_completion_tokens": ct,
        "missing_cases": d_missing,
        "compiler_reference_llm_calls": 0,
    }
    block_c["cost"] = {"llm_calls_total": len(c_raws), "total_prompt_tokens": cpt, "total_completion_tokens": cct}

    per_case = {}
    for case, cf, d0f, dff in zip(cases, c_flags, d0_flags, df_flags):
        cid = case["case_id"]
        pc, pd0, pdf = preds_c[cid], preds_d0[cid], preds_df[cid]
        per_case[cid] = {
            f"{mslug}_armC_action": pc["action"], f"{mslug}_armC_pred_metric_id": pc["pred_metric_id"],
            f"{mslug}_armC_pred_dimensions": pc["pred_dimensions"], f"{mslug}_armC_parse_status": pc["parse_status"],
            f"{mslug}_armC_joint_correct": bool(cf),
            f"{mslug}_armD_round0_action": pd0["action"], f"{mslug}_armD_round0_pred_metric_id": pd0["pred_metric_id"],
            f"{mslug}_armD_round0_pred_dimensions": pd0["pred_dimensions"], f"{mslug}_armD_round0_joint_correct": bool(d0f),
            f"{mslug}_armD_final_action": pdf["action"], f"{mslug}_armD_final_pred_metric_id": pdf["pred_metric_id"],
            f"{mslug}_armD_final_pred_dimensions": pdf["pred_dimensions"], f"{mslug}_armD_final_joint_correct": bool(dff),
            f"{mslug}_armD_rounds_used": rounds_used[cid],
            f"{mslug}_armD_final_validator_pass": final_pass[cid],
        }
    return {"arm_c": block_c, "arm_d_round0": block_d0, "arm_d_final": block_df}, per_case


def cmd_score():
    cases = LE.load_cases()
    assert len(cases) == 159
    pairs_a = {r["case_id"]: r for r in read_jsonl(SC.PAIRS_A)}
    a_flags = [1 if pairs_a[c["case_id"]]["armA_joint_correct"] else 0 for c in cases]
    assert sum(a_flags) == ARM_A_JOINT, f"Arm A pairing drift: {sum(a_flags)} != {ARM_A_JOINT}"

    per_model_blocks, per_case_merged = {}, {c["case_id"]: {} for c in cases}
    for model in MODELS:
        blocks, per_case = score_model(model, cases, pairs_a, a_flags)
        per_model_blocks[model] = blocks
        for cid, fields in per_case.items():
            per_case_merged[cid].update(fields)

    # Holm adjustment across the 4 primary arms (protocol section 5)
    raw_p = {}
    for model in MODELS:
        raw_p[f"C-{model}"] = per_model_blocks[model]["arm_c"]["vs_armA"]["mcnemar_exact_two_sided_p"]
        raw_p[f"Dfinal-{model}"] = per_model_blocks[model]["arm_d_final"]["vs_armA"]["mcnemar_exact_two_sided_p"]
    adj_p = holm_adjust(raw_p)

    overtaking = [name for model in MODELS for name, blk in
                  [(f"C-{model}", per_model_blocks[model]["arm_c"]),
                   (f"Dfinal-{model}", per_model_blocks[model]["arm_d_final"])]
                  if blk["joint_accuracy"] >= ARM_A_JOINT / 159 - 1e-12]
    all_sig = all(p < 0.05 for p in raw_p.values())
    if overtaking:
        branch = "a_overtaken_gap_eroded"
    elif all_sig:
        branch = "c_gap_survives_significantly"
    else:
        branch = "b_parity_no_paired_significance_for_some_arm"

    result = {
        "protocol": "protocol_ext_models.md (frozen 2026-07-12T14:13+0800, before any LLM call of this study)",
        "n_cases": 159,
        "arm_a_reference": {
            "name": "CaliberGraph (deterministic compiler; flags from ../private_paired_rerun/per_case_pairs.jsonl)",
            "joint_accuracy": ARM_A_JOINT / 159,
            "joint_correct": ARM_A_JOINT,
        },
        "deepseek_reference": {
            "arm_c_joint": 124 / 159, "arm_d_round0_joint": 124 / 159, "arm_d_final_joint": 143 / 159,
            "source": "../private_strongest_controls/mcnemar_ext.json",
        },
        "arm_b_reference": {"joint_accuracy_rerun": 127 / 159, "joint_accuracy_published": 0.8490566037735849},
        "models": per_model_blocks,
        "primary_arms_mcnemar_p_raw": raw_p,
        "primary_arms_mcnemar_p_holm": adj_p,
        "overtaking_arms": overtaking,
        "preregistered_branch": branch,
        "branch_rule": ("(a) any primary arm joint >= 0.9245283 -> gap eroded, migrate claim to by-construction; "
                        "(b) all < 0.925 but some primary arm p >= 0.05 -> parity posture, no paired-superiority claim vs that arm; "
                        "(c) all < 0.925 and all primary p < 0.05 -> margin survives strongest models"),
    }

    pairs_out = []
    for case in cases:
        cid = case["case_id"]
        pa = pairs_a[cid]
        row = {
            "case_id": cid,
            "nl_query_sha256": sha256_text(case["nl_query"]),
            "expected_metric_id": case["expected_metric_id"],
            "expected_dimensions": case["expected_dimensions"],
            "armA_joint_correct": bool(pa["armA_joint_correct"]),
            "armA_pred_metric_id": pa["armA_pred_metric_id"],
            "armA_pred_dimensions": pa["armA_pred_dimensions"],
        }
        row.update(per_case_merged[cid])
        pairs_out.append(row)
    (HERE / "per_case_pairs_models.jsonl").write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in pairs_out) + "\n", encoding="utf-8")
    (HERE / "mcnemar_models.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    brief = {}
    for model in MODELS:
        b = per_model_blocks[model]
        brief[model] = {
            "armC_joint": round(b["arm_c"]["joint_accuracy"], 4),
            "armD_round0_joint": round(b["arm_d_round0"]["joint_accuracy"], 4),
            "armD_final_joint": round(b["arm_d_final"]["joint_accuracy"], 4),
            "armC_p_vs_A": b["arm_c"]["vs_armA"]["mcnemar_exact_two_sided_p"],
            "armD_final_p_vs_A": b["arm_d_final"]["vs_armA"]["mcnemar_exact_two_sided_p"],
        }
    brief["branch"] = branch
    brief["overtaking_arms"] = overtaking
    print(json.dumps(brief, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["canary", "run", "score"])
    ap.add_argument("--arm", choices=["c", "d"], default=None)
    ap.add_argument("--model", choices=list(MODELS), default=None)
    ap.add_argument("--rev", type=int, choices=[1, 3], default=1)
    args = ap.parse_args()
    if args.cmd == "canary":
        if not args.model:
            raise SystemExit("--model required")
        cmd_canary(args.model, rev=args.rev)
    elif args.cmd == "run":
        if not args.model or not args.arm:
            raise SystemExit("--arm c|d and --model required")
        if args.arm == "c":
            run_arm_c(args.model)
        else:
            run_arm_d(args.model)
    elif args.cmd == "score":
        cmd_score()


if __name__ == "__main__":
    main()
