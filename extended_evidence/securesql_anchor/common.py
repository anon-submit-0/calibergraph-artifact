#!/usr/bin/env python3
"""Shared helpers for the SecureSQL anchor experiment (protocol.md v1.0, frozen).

Honesty: no mocks; every LLM call stores its raw response under raw/.
Keys are read at runtime from ~/.config/llm_keys.env and never written out.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RAW = HERE / "raw"
ENV_FILE = Path.home() / ".config" / "llm_keys.env"

MODEL = "gpt-5.5"
BASE_DEFAULT = "RELAY_ENDPOINT"
# Amendment 2 (transport-only): group-B gpt-5.5 channel pool down (get_channel_failed);
# same gateway, same model, same params on the default group.
KEY_ENV = "RELAY_KEY_DEFAULT"
TEMPERATURE = 0
TIMEOUT_S = 240
# channel intermittently returns 500 get_channel_failed (upstream pool); long tail retries needed
RETRY_BACKOFF = [5, 15, 45, 90, 180]
SUBSAMPLE_SEED = 20260714
SUBSAMPLE_ALLOC = {"SA": 103, "DI": 71, "SU": 47, "PR": 41, "RE": 38}

GOLD = {"SA": "safe", "SU": "safe", "DI": "unsafe", "PR": "unsafe", "RE": "unsafe"}


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
    if not os.environ.get(KEY_ENV):
        raise SystemExit(f"{KEY_ENV} not found in env file")


def call_channel(messages, max_tokens, model=MODEL):
    api_key = os.environ[KEY_ENV]
    base = os.environ.get("RELAY_BASE", BASE_DEFAULT)
    body = json.dumps(
        {"model": model, "temperature": TEMPERATURE, "max_tokens": max_tokens, "messages": messages},
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


def call_with_retries(messages, max_tokens, meta):
    """Returns a full record dict; raw response preserved; errors recorded honestly."""
    record = dict(meta)
    prompt_sha = hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    record.update({
        "model": MODEL, "temperature": TEMPERATURE, "max_tokens": max_tokens,
        "prompt_sha256": prompt_sha, "attempts": 0, "latency_ms": None, "usage": None,
        "raw_response": None, "finish_reason": None, "http_status": None, "error": None, "ts_utc": None,
    })
    last_err = None
    for attempt in range(1 + len(RETRY_BACKOFF)):
        record["attempts"] = attempt + 1
        try:
            payload, latency_ms, status = call_channel(messages, max_tokens)
            content = (payload.get("choices") or [{}])[0].get("message", {}).get("content")
            if not content or not str(content).strip():
                raise RuntimeError("empty content")
            record.update({
                "latency_ms": latency_ms, "usage": payload.get("usage"), "raw_response": content,
                "finish_reason": (payload.get("choices") or [{}])[0].get("finish_reason"),
                "http_status": status, "error": None,
                "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            return record
        except Exception as exc:  # noqa: BLE001 - record honestly and retry
            detail = ""
            if hasattr(exc, "read"):
                try:
                    detail = " body=" + exc.read().decode("utf-8", "replace")[:300]
                except Exception:
                    pass
            last_err = f"{type(exc).__name__}: {exc}{detail}"
            if attempt < len(RETRY_BACKOFF):
                time.sleep(RETRY_BACKOFF[attempt])
    record["error"] = f"api_error after {record['attempts']} attempts: {last_err}"
    record["ts_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return record


def last_json_object(text):
    """Extract the last balanced JSON object from a text blob."""
    if not text:
        return None
    s = str(text)
    end = len(s)
    while True:
        close = s.rfind("}", 0, end)
        if close < 0:
            return None
        depth = 0
        for i in range(close, -1, -1):
            if s[i] == "}":
                depth += 1
            elif s[i] == "{":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[i:close + 1])
                    except Exception:
                        break
        end = close
    return None


def load_data():
    return json.load(open(DATA / "data_unzipped" / "data.json"))


def load_schemas():
    return json.load(open(DATA / "schemas_57.json"))


def schema_text(db_id, schemas):
    tables = schemas[db_id]["tables"]
    lines = []
    for t, cols in tables.items():
        lines.append(f"      {t}({', '.join(cols)})")
    return "\n".join(lines)


def read_jsonl(path):
    out = []
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def append_jsonl(path, rec):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def build_subsample(data):
    import random
    by_label = {}
    for ex in data:
        by_label.setdefault(ex["label"], []).append(ex)
    rng = random.Random(SUBSAMPLE_SEED)
    chosen = []
    for label in sorted(by_label):
        rows = sorted(by_label[label], key=lambda r: r["id"])
        chosen.extend(r["id"] for r in rng.sample(rows, SUBSAMPLE_ALLOC[label]))
    chosen = sorted(chosen)
    return {
        "seed": SUBSAMPLE_SEED,
        "allocation": SUBSAMPLE_ALLOC,
        "n": len(chosen),
        "sha256_of_ids": hashlib.sha256(json.dumps(chosen).encode()).hexdigest(),
        "ids": chosen,
    }
