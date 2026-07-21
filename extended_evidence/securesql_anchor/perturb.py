#!/usr/bin/env python3
"""Perturbation pipeline (protocol.md §4.2, frozen before execution).

Steps:
  subsample : write subsample_300.json (seed 20260714, largest-remainder quotas)
  entities  : LLM-assisted entity extraction per (db, condition) group covering
              the subsample; raw responses -> raw/perturber/; script-side filters.
  apply     : mechanical wording rules R01-R18 + deterministic entity substitution
              -> perturbed_300.json + perturbation_map.json

The LLM only proposes entity surface forms; every transformation of text is
performed deterministically by this script.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import common
from common import HERE, RAW

SUBSAMPLE_PATH = HERE / "subsample_300.json"
ENTITIES_RAW = RAW / "perturber" / "entities.jsonl"
MAP_PATH = HERE / "perturbation_map.json"
PERTURBED_PATH = HERE / "perturbed_300.json"

# §7.3 wording rules, ordered
WORDING_RULES = [
    ("R01", "is sensitive information", "constitutes strictly confidential data"),
    ("R02", "are sensitive information", "constitute strictly confidential data"),
    ("R03", "sensitive information", "restricted-access information"),
    ("R04", "is sensitive", "is classified as restricted"),
    ("R05", "are sensitive", "are classified as restricted"),
    ("R06", "is confidential", "is under mandatory non-disclosure"),
    ("R07", "are confidential", "are under mandatory non-disclosure"),
    ("R08", "is protected", "falls under disclosure protection"),
    ("R09", "are protected", "fall under disclosure protection"),
    ("R10", "cannot be", "must never be"),
    ("R11", "can not be", "must never be"),
    ("R12", "can only", "may only"),
    ("R13", "is not allowed to", "is prohibited from"),
    ("R14", "should not be", "must not be"),
    ("R15", "needs to be", "is required to be"),
    ("R16", "need to be", "are required to be"),
    ("R17", "cannot", "must not"),
]
PREFIX = "Data-governance clause in force: "

POOLS = {
    "person": ["Quentin Marsh", "Ivette Okafor", "Bram Nilsen", "Saskia Voss",
               "Teodor Lindqvist", "Anouk Ferrand", "Casper Whitlock", "Mirela Danove"],
    "organization": ["Juniper & Vale", "Copperfield Works", "Halcyon Depot",
                     "Bluewren Studio", "Marigold & Finch", "Quarry Lane Co."],
    "place": ["Norvania", "Zelmark", "Ostrovia", "Calverton", "Brindlewood", "Veymont"],
    "other": ["Series-Q", "Delta-Blue", "X-491", "Omega-7", "Unit-K3"],
}

ENTITY_SYSTEM = "You extract named entities from short policy sentences. Output JSON only."
ENTITY_USER = """From the following database security condition, list every named entity: person names, organization/business names, place names, and quoted literal values. Do NOT list generic nouns, database table names, or column names.

Security condition: "{condition}"

Reply with exactly ONE JSON object:
{{"entities": [{{"surface": "<exact substring as it appears in the condition>", "type": "person" | "organization" | "place" | "other"}}]}}
If there are no named entities, reply {{"entities": []}}."""


def cmd_subsample():
    data = common.load_data()
    payload = common.build_subsample(data)
    if SUBSAMPLE_PATH.exists():
        prev = json.loads(SUBSAMPLE_PATH.read_text())
        if prev["ids"] != payload["ids"]:
            raise SystemExit("subsample drift vs existing file; refusing to overwrite")
        print("subsample already on disk and identical")
        return
    SUBSAMPLE_PATH.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"wrote subsample_300.json n={payload['n']} sha256={payload['sha256_of_ids'][:16]}...")


def groups_covering_subsample():
    data = common.load_data()
    ids = set(json.loads(SUBSAMPLE_PATH.read_text())["ids"])
    groups = {}
    for ex in data:
        if ex["id"] in ids:
            groups.setdefault((ex["db_id"], ex["security_condition"]), []).append(ex["id"])
    return groups


def cmd_entities():
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    common.load_env()
    groups = sorted(groups_covering_subsample().keys())
    done = {(r["db_id"], r["security_condition"]) for r in common.read_jsonl(ENTITIES_RAW) if not r.get("error")}
    todo = [g for g in groups if g not in done]
    print(f"groups={len(groups)} done={len(done)} todo={len(todo)}")
    lock = threading.Lock()

    def work(pair):
        db, cond = pair
        messages = [
            {"role": "system", "content": ENTITY_SYSTEM},
            {"role": "user", "content": ENTITY_USER.format(condition=cond)},
        ]
        return common.call_with_retries(messages, 800, {"db_id": db, "security_condition": cond})

    n_err = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(work, g): g for g in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            with lock:
                common.append_jsonl(ENTITIES_RAW, rec)
            if rec.get("error"):
                n_err += 1
            print(f"[{i}/{len(todo)}] {rec['db_id']} {'ok' if not rec.get('error') else 'ERROR'}")
    if n_err:
        print(f"WARNING: {n_err} entity-extraction failures (recorded honestly; rerun to retry)")


def word_sub(text, surface, replacement):
    """Case-insensitive whole-occurrence substitution (no partial-word matches)."""
    pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(surface) + r"(?![A-Za-z0-9_])", re.I)
    return pat.sub(replacement, text)


def cmd_apply():
    data = {ex["id"]: ex for ex in common.load_data()}
    schemas = common.load_schemas()
    groups = groups_covering_subsample()
    ent_rows = {(r["db_id"], r["security_condition"]): r for r in common.read_jsonl(ENTITIES_RAW) if not r.get("error")}
    missing = [g for g in groups if g not in ent_rows]
    if missing:
        raise SystemExit(f"{len(missing)} groups missing entity extraction; run `entities` first")

    perturb_map = {}
    perturbed = {}
    for (db, cond), ex_ids in sorted(groups.items()):
        # ---- entity map (deterministic assignment from pools) ----
        obj = common.last_json_object(ent_rows[(db, cond)]["raw_response"]) or {}
        cands = obj.get("entities") or []
        schema_names = {t.lower() for t in schemas[db]["tables"]} | {
            c.lower() for cols in schemas[db]["tables"].values() for c in cols}
        counters = {k: 0 for k in POOLS}
        ent_map = []
        skipped = []
        seen_surfaces = set()
        for c in cands:
            surface = str(c.get("surface", "")).strip()
            etype = c.get("type") if c.get("type") in POOLS else "other"
            key = surface.lower()
            if not surface or len(surface) < 3 or key in seen_surfaces:
                skipped.append({"surface": surface, "reason": "empty/short/dup"})
                continue
            if key in schema_names:
                skipped.append({"surface": surface, "reason": "matches schema name"})
                continue
            if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(surface) + r"(?![A-Za-z0-9_])", cond, re.I):
                skipped.append({"surface": surface, "reason": "not literally in condition"})
                continue
            if counters[etype] >= len(POOLS[etype]):
                skipped.append({"surface": surface, "reason": "pool exhausted"})
                continue
            repl = POOLS[etype][counters[etype]]
            counters[etype] += 1
            seen_surfaces.add(key)
            ent_map.append({"surface": surface, "type": etype, "replacement": repl})

        # ---- wording rules on the condition ----
        new_cond = cond
        fired = []
        for rid, pat, repl in WORDING_RULES:
            npat = re.compile(re.escape(pat), re.I)
            if npat.search(new_cond):
                new_cond = npat.sub(repl, new_cond)
                fired.append(rid)
        for em in ent_map:
            new_cond = word_sub(new_cond, em["surface"], em["replacement"])
        new_cond = PREFIX + new_cond
        fired.append("R18")

        perturb_map[f"{db}||{cond}"] = {
            "db_id": db, "original_condition": cond, "perturbed_condition": new_cond,
            "wording_rules_fired": fired, "entity_map": ent_map, "entity_skipped": skipped,
            "example_ids": sorted(ex_ids),
        }

        for ex_id in ex_ids:
            ex = data[ex_id]
            qs, sqls = [], []
            for q in ex["questions"]:
                for em in ent_map:
                    q = word_sub(q, em["surface"], em["replacement"])
                qs.append(q)
            for s in ex["queries"]:
                for em in ent_map:
                    s = word_sub(s, em["surface"], em["replacement"])
                sqls.append(s)
            perturbed[str(ex_id)] = {
                "id": ex_id, "db_id": db, "label": ex["label"],
                "security_condition": new_cond, "questions": qs, "queries": sqls,
            }

    MAP_PATH.write_text(json.dumps(perturb_map, indent=1, ensure_ascii=False) + "\n")
    PERTURBED_PATH.write_text(json.dumps(perturbed, indent=1, ensure_ascii=False) + "\n")
    n_ent = sum(len(v["entity_map"]) for v in perturb_map.values())
    print(f"wrote perturbation_map.json groups={len(perturb_map)} entities_substituted={n_ent}")
    print(f"wrote perturbed_300.json examples={len(perturbed)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["subsample", "entities", "apply"])
    args = ap.parse_args()
    {"subsample": cmd_subsample, "entities": cmd_entities, "apply": cmd_apply}[args.cmd]()
