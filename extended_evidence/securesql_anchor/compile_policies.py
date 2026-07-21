#!/usr/bin/env python3
"""Arm A step 1: compile 146 NL security conditions into structured policy nodes.

Subcommands:
  canary            2 canary calls (protocol §3, pass 2/2 required before compile)
  compile           compile all 146 original conditions -> policy_nodes.json
  compile-perturbed compile perturbed conditions (blind) -> policy_nodes_perturbed.json

Raw responses: raw/compiler/*.jsonl. LLM parses clauses once; judgment is done
by the deterministic checker.py. No mocks; failures recorded honestly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import common
from common import HERE, RAW

COMPILER_SYSTEM = ("You are a policy compiler that converts natural-language database security "
                   "conditions into structured, machine-checkable disclosure rules. Output JSON only.")

COMPILER_USER = """Database name: {db_id}
Tables and columns in the database:
{schema_text}

Security condition (verbatim): "{security_condition}"

Compile this security condition into a structured disclosure policy. Reply with exactly ONE JSON object:
{{
  "compilable": true or false,
  "uncompilable_reason": "<only if compilable=false: why this clause cannot be reduced to mechanical column/row rules>",
  "protection_kind": "value" | "attribution" | "row_access" | "aggregate" | "other",
  "protected_columns": [
    {{"table": "<table>", "column": "<column>",
      "row_scope": null | {{"scope_table": "<table>", "scope_column": "<column>", "op": "=", "value": "<literal>", "description": "<NL description>"}}}}
  ],
  "identifier_columns": [{{"table": "<t>", "column": "<c>"}}],
  "trigger_phrases": ["<words in the condition that anchored the rule>"],
  "notes": "<assumptions>"
}}
Rules of interpretation:
- "value": the protected column's values must not be disclosed (within row_scope if given).
- "attribution": values may appear in output only if they cannot be linked back to the identified entity; the linking columns are listed in identifier_columns.
- "row_access": only rows matching row_scope may be returned to the current user. protected_columns then lists ALL columns of the affected table(s), each with the ALLOWED row_scope and op "=" — rows outside that scope are protected.
- "aggregate": entity-specific aggregate values are protected (e.g. one particular merchant's visit count).
- Use ONLY table and column names that appear in the schema above.
- If the condition cannot be anchored to schema columns mechanically, set compilable=false and explain."""

CANARY_USER = """Database name: {db_id}
Tables and columns in the database:
{schema_text}

Security condition (verbatim): "{security_condition}"

CANARY CHECK (this is NOT a benchmark case; do not classify anything). To verify that the security condition reproduced verbatim in this message is visible to you: quote the FIRST 100 characters of the line beginning "Security condition" exactly as shown above. Reply with exactly ONE JSON object and nothing else: {{"canary": "<those first 100 characters>"}}"""


def unique_conditions():
    data = common.load_data()
    seen = {}
    for ex in data:
        seen.setdefault((ex["db_id"], ex["security_condition"]), 0)
    return sorted(seen.keys())


def _collapse(s):
    return " ".join(str(s).split())


def canary_pass(raw_content, true_line):
    target = _collapse(true_line[:100])[:80]
    texts = []
    obj = common.last_json_object(raw_content)
    if isinstance(obj, dict) and isinstance(obj.get("canary"), str):
        texts.append(obj["canary"])
    texts.append(str(raw_content))
    texts.append(str(raw_content).replace('\\"', '"'))
    joined = " \n ".join(_collapse(t) for t in texts)
    return target in joined


def cmd_canary():
    common.load_env()
    schemas = common.load_schemas()
    conds = unique_conditions()
    picks = [conds[0], conds[len(conds) // 2]]
    path = RAW / "compiler" / "canary.jsonl"
    passes = 0
    for db, cond in picks:
        user = CANARY_USER.format(db_id=db, schema_text=common.schema_text(db, schemas), security_condition=cond)
        messages = [{"role": "system", "content": COMPILER_SYSTEM}, {"role": "user", "content": user}]
        rec = common.call_with_retries(messages, 500, {"kind": "canary", "db_id": db, "security_condition": cond})
        common.append_jsonl(path, rec)
        true_line = f'Security condition (verbatim): "{cond}"'
        ok = (not rec.get("error")) and canary_pass(rec.get("raw_response"), true_line)
        passes += int(ok)
        print(f"canary {db}: {'PASS' if ok else 'FAIL'}")
    print(f"canary result: {passes}/2")
    if passes < 2:
        raise SystemExit("canary gate failed (need 2/2); do not run compile")


def _compile(pairs, raw_name, out_name, cond_lookup=None):
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    common.load_env()
    schemas = common.load_schemas()
    raw_path = RAW / "compiler" / raw_name
    done = {(r["db_id"], r["security_condition_key"]) for r in common.read_jsonl(raw_path) if not r.get("error")}
    todo = [(db, key, text) for db, key, text in pairs if (db, key) not in done]
    print(f"pairs={len(pairs)} done={len(done)} todo={len(todo)}")
    lock = threading.Lock()

    def work(item):
        db, key, text = item
        user = COMPILER_USER.format(db_id=db, schema_text=common.schema_text(db, schemas), security_condition=text)
        messages = [{"role": "system", "content": COMPILER_SYSTEM}, {"role": "user", "content": user}]
        return common.call_with_retries(messages, 3000, {
            "kind": "compile", "db_id": db, "security_condition_key": key, "condition_text": text})

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(work, it): it for it in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            with lock:
                common.append_jsonl(raw_path, rec)
            print(f"[{i}/{len(todo)}] {rec['db_id']} {'ok' if not rec.get('error') else 'ERROR'}")

    nodes = {}
    failures = []
    for r in common.read_jsonl(raw_path):
        if r.get("error"):
            failures.append({"db_id": r["db_id"], "key": r["security_condition_key"], "error": r["error"]})
            continue
        obj = common.last_json_object(r["raw_response"])
        entry_key = f"{r['db_id']}||{r['security_condition_key']}"
        if not isinstance(obj, dict):
            nodes[entry_key] = {"compilable": False, "uncompilable_reason": "compiler output not parseable JSON",
                                "parse_failure": True}
            continue
        obj["condition_text"] = r.get("condition_text")
        nodes[entry_key] = obj
    (HERE / out_name).write_text(json.dumps(nodes, indent=1, ensure_ascii=False) + "\n")
    n_ok = sum(1 for v in nodes.values() if v.get("compilable") is True)
    print(f"wrote {out_name}: nodes={len(nodes)} compilable={n_ok} "
          f"uncompilable={len(nodes)-n_ok} api_failures={len(failures)}")
    if failures:
        print(json.dumps(failures[:5], ensure_ascii=False))


def cmd_compile():
    pairs = [(db, cond, cond) for db, cond in unique_conditions()]
    _compile(pairs, "compile_original.jsonl", "policy_nodes.json")


def cmd_compile_perturbed():
    pmap = json.loads((HERE / "perturbation_map.json").read_text())
    # key by ORIGINAL condition text so checker can join; compiler sees only perturbed text
    pairs = [(v["db_id"], v["original_condition"], v["perturbed_condition"]) for v in pmap.values()]
    pairs.sort()
    _compile(pairs, "compile_perturbed.jsonl", "policy_nodes_perturbed.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["canary", "compile", "compile-perturbed"])
    args = ap.parse_args()
    {"canary": cmd_canary, "compile": cmd_compile, "compile-perturbed": cmd_compile_perturbed}[args.cmd]()
