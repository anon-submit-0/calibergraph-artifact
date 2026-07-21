#!/usr/bin/env python3
"""Deterministic case generator for external_mf_metric_caliber (seed=20260712).

Pre-registered design (protocol.md, frozen 2026-07-12):
- >=120 cases, fixed NL template families, NO LLM anywhere, seed=20260712.
- Strata:
    S1 answerable        (n=60): answerable metric x legal dimension combos, stratified by
                                  combo size 0/1/2 (20 each);
    S2 grain/hierarchy   (n=20): a metric queried by BOTH a finer grain and one of its
                                  ancestor grains; gold = answer at the finest grain;
    S3 ratio-denominator (n=15): ratio-like metric sliced by a dimension that is valid for
                                  the numerator-side or denominator-side input alone but NOT
                                  in the ratio metric's allowed scope; gold = refuse;
    S4 undefined metric  (n=15): requests for metrics that do not exist in the source
                                  manifest (protocol-added refusal stubs); gold = refuse;
    S5 SQL/DDL request   (n=12): raw SQL/DDL authoring requests; gold = refuse.
- GOLD LABELS ARE DERIVED MECHANICALLY FROM THE CONTRACT ONLY:
  answerability/allowed_dimensions/finest-grain resolution (parent map) / protocol refusal
  classes. The compiler's decision function is NEVER called here.
- NL-ambiguity guard: a rendered query is kept only if, under the *published* detection
  grammar of the released contract compiler (marker split + word-boundary alias matching:
  ContractCompiler.detect_dimensions, used read-only), the mentioned-dimension set equals
  the intended one. This rejects linguistically ambiguous phrasings (e.g. a metric whose
  own name contains "per ... week"); rejected draws are logged in generation_audit.json.
  Dimensions whose canonical phrase word-contains another dimension's phrase (e.g.
  "home state latest" vs "home state") are excluded from sampling and listed in the audit.

Run:  python3 generate_cases.py
Outputs (in external_mf_metric_caliber/): blind_cases.jsonl, gold_labels.jsonl,
test_cases.jsonl, generation_audit.json
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

from calibergraph_contract_compiler import ContractCompiler, contains_alias

SEED = 20260712
HERE = Path(__file__).resolve().parent
DATA = HERE / "external_mf_metric_caliber"
SOURCE_TAG = "mechanically_generated_from_third_party_dbt_metricflow_simple_manifest_seed20260712"

N_S1, N_S2, N_S3, N_S4, N_S5 = 60, 20, 15, 15, 12


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def word_match(needle, haystack):
    needle = re.sub(r"\s+", " ", str(needle).lower()).strip()
    haystack = re.sub(r"\s+", " ", str(haystack).lower()).strip()
    if not needle:
        return False
    return re.search(rf"(?<![a-z0-9_]){re.escape(needle)}(?![a-z0-9_])", haystack) is not None


def main():
    rng = random.Random(SEED)
    metrics = {m["metric_id"]: m for m in read_jsonl(DATA / "metric_catalog.jsonl")}
    dims = {d["dimension_id"]: d for d in read_jsonl(DATA / "dimension_catalog.jsonl")}
    parents = {d: r.get("parent", "") for d, r in dims.items()}
    physical = read_jsonl(DATA / "physical_coverage.jsonl")
    # read-only use of the released detection grammar for the ambiguity guard
    compiler = ContractCompiler(DATA)

    def ancestors(dim_id):
        out, cur = [], parents.get(dim_id, "")
        while cur:
            out.append(cur)
            cur = parents.get(cur, "")
        return out

    def finest(dim_ids):
        shadowed = set()
        for d in dim_ids:
            shadowed.update(ancestors(d))
        return sorted(d for d in dim_ids if d not in shadowed)

    # ---- sampling-safe dimensions (phrase-containment exclusion) ----
    excluded_dims = {}
    for d, row in dims.items():
        p = row["aliases"][0]
        for e, erow in dims.items():
            if e == d:
                continue
            for alias in [e, erow.get("name", "")] + erow.get("aliases", []):
                if word_match(alias, p):
                    excluded_dims[d] = f"phrase '{p}' word-contains alias '{alias}' of {e}"
        # containment in the other direction is safe (rendering d does not mention e)
    safe = {d for d in dims if d not in excluded_dims}

    def dim_phrase(d):
        return dims[d]["aliases"][0]

    def m_phrase(mid):
        return metrics[mid]["aliases"][0]

    answerable = sorted(m for m, r in metrics.items() if r["answerable"])
    grain_ids = {d for d in dims if d.startswith("metric_time__")}

    rejected = []

    def guarded(query, intended_dims):
        detected = set(compiler.detect_dimensions(query))
        if detected == set(intended_dims):
            return True
        rejected.append({"query": query, "intended": sorted(intended_dims), "detected": sorted(detected)})
        return False

    cases = []  # (stratum, nl_query, expected_action, expected_metric_id, expected_dimensions)

    # ---------- S1 answerable ----------
    s1_metrics = rng.sample(answerable, N_S1)
    sizes = [0] * (N_S1 // 3) + [1] * (N_S1 // 3) + [2] * (N_S1 // 3)
    t0 = ["What is total {m}?", "Show total {m}."]
    t1 = ["{M} by {d}.", "Show {m} grouped by {d}."]
    t2 = ["{M} by {d1} and {d2}.", "Show {m} grouped by {d1} and {d2}."]
    i1 = 0
    for idx, (mid, size) in enumerate(zip(s1_metrics, sizes)):
        allowed = [d for d in metrics[mid]["allowed_dimensions"] if d in safe]
        cats = sorted(d for d in allowed if d not in grain_ids)
        grains = sorted(d for d in allowed if d in grain_ids)
        made = False
        # deterministic candidate enumeration, shuffled once per case
        if size == 0:
            combos = [[]]
        elif size == 1:
            combos = [[d] for d in cats + grains]
            rng.shuffle(combos)
        else:
            combos = [[a, b] for i, a in enumerate(cats) for b in cats[i + 1:]]
            combos += [[c, g] for c in cats for g in grains]
            rng.shuffle(combos)
        for combo in combos:
            if size == 0:
                q = t0[idx % 2].format(m=m_phrase(mid))
            elif size == 1:
                tpl = t1[idx % 2]
                q = tpl.format(M=m_phrase(mid).capitalize(), m=m_phrase(mid), d=dim_phrase(combo[0]))
            else:
                tpl = t2[idx % 2]
                q = tpl.format(
                    M=m_phrase(mid).capitalize(), m=m_phrase(mid),
                    d1=dim_phrase(combo[0]), d2=dim_phrase(combo[1]),
                )
            if guarded(q, combo):
                gold_dims = finest(combo)
                assert set(gold_dims) == set(combo), f"S1 combo unexpectedly nested: {combo}"
                cases.append(("answerable", q, "answer", mid, sorted(combo)))
                made = True
                i1 += 1
                break
        if not made:
            raise RuntimeError(f"S1: no unambiguous combo for metric {mid} size {size}")
    assert i1 == N_S1

    # ---------- S2 grain/hierarchy traps ----------
    s2_universe = []
    for mid in answerable:
        allowed = set(metrics[mid]["allowed_dimensions"])
        gs = sorted(d for d in allowed if d in grain_ids)
        for child in gs:
            for anc in ancestors(child):
                if anc in allowed:
                    s2_universe.append((mid, child, anc))
    s2_universe.sort()
    s2_templates = ["{M} by {child} and {anc}.", "Show {m} grouped by {anc} and {child}."]
    s2_picked = rng.sample(s2_universe, N_S2)
    for j, (mid, child, anc) in enumerate(s2_picked):
        tpl = s2_templates[j % 2]
        q = tpl.format(M=m_phrase(mid).capitalize(), m=m_phrase(mid),
                       child=dim_phrase(child), anc=dim_phrase(anc))
        if not guarded(q, [child, anc]):
            raise RuntimeError(f"S2 ambiguous: {q}")
        cases.append(("grain_hierarchy_trap", q, "answer", mid, finest([child, anc])))

    # ---------- S3 ratio denominator traps ----------
    def side_allowed(node_ids):
        sets = [set(metrics[n]["allowed_dimensions"]) for n in node_ids if n in metrics]
        return set.intersection(*sets) if sets else set()

    singles, pairs = [], []
    for mid in answerable:
        row = metrics[mid]
        if not row["numerator_nodes"] or not row["denominator_nodes"]:
            continue
        ratio_allowed = set(row["allowed_dimensions"])
        num_allowed = side_allowed(row["numerator_nodes"])
        den_allowed = side_allowed(row["denominator_nodes"])
        traps = sorted(((num_allowed | den_allowed) - ratio_allowed) & safe)
        legal_cats = sorted(d for d in ratio_allowed if d in safe and d not in grain_ids)
        for t in traps:
            singles.append((mid, t))
            for lg in legal_cats:
                pairs.append((mid, lg, t))
    singles.sort()
    pairs.sort()
    if len(singles) >= N_S3:
        s3_picked = [("single",) + s for s in rng.sample(singles, N_S3)]
    else:
        s3_picked = [("single",) + s for s in singles]
        s3_picked += [("pair",) + p for p in rng.sample(pairs, N_S3 - len(singles))]
    for j, item in enumerate(s3_picked):
        if item[0] == "single":
            _, mid, trap = item
            q = ["{M} by {t}.", "Show {m} grouped by {t}."][j % 2].format(
                M=m_phrase(mid).capitalize(), m=m_phrase(mid), t=dim_phrase(trap))
            intended = [trap]
        else:
            _, mid, legal, trap = item
            q = "{M} by {l} and {t}.".format(M=m_phrase(mid).capitalize(),
                                             l=dim_phrase(legal), t=dim_phrase(trap))
            intended = [legal, trap]
        if not guarded(q, intended):
            raise RuntimeError(f"S3 ambiguous: {q}")
        # mechanical gold: trap dim is outside the ratio metric's allowed scope -> refuse
        assert any(d not in metrics[mid]["allowed_dimensions"] for d in intended)
        cases.append(("ratio_denominator_trap", q, "refuse", "", []))

    # ---------- S4 undefined-metric refusals ----------
    stubs = sorted(m for m, r in metrics.items() if r["source"] == "protocol_added_refusal_stub")
    s4_universe = []
    for sid in stubs:
        for alias in metrics[sid]["aliases"]:
            for tpl in ["What is total {p}?", "Show {p} by month."]:
                s4_universe.append((sid, alias, tpl))
    s4_universe.sort()
    for sid, alias, tpl in rng.sample(s4_universe, N_S4):
        q = tpl.format(p=alias)
        intended = ["metric_time__month"] if "by month" in tpl else []
        if not guarded(q, intended):
            raise RuntimeError(f"S4 ambiguous: {q}")
        # mechanical gold: metric undefined in the source manifest (protocol refusal class r1)
        assert metrics[sid]["answerable"] is False
        cases.append(("undefined_metric_refusal", q, "refuse", "", []))

    # ---------- S5 SQL/DDL request refusals ----------
    tables = sorted(p["semantic_node_id"] for p in physical)
    sql_templates = [
        "Write a SELECT statement over {t}.",
        "Please DROP the table {t}.",
        "Give me an INSERT statement for {t}.",
        "Generate SQL: SELECT * FROM {t}.",
        "UPDATE {t} and set all values to zero.",
        "DELETE every row from {t}.",
    ]
    for j in range(N_S5):
        q = sql_templates[j % len(sql_templates)].format(t=tables[j % len(tables)])
        # mechanical gold: query text hits the protocol-added sql_or_ddl policy rule (r2)
        assert any(trigger in q.lower() for trigger in
                   ["select ", "insert ", "update ", "delete ", "drop ", "truncate ", "alter "])
        cases.append(("sql_request_refusal", q, "refuse", "", []))

    # ---------- shuffle, number, write ----------
    assert len(cases) == N_S1 + N_S2 + N_S3 + N_S4 + N_S5 == 122
    rng.shuffle(cases)
    blind, gold, merged, strata_map = [], [], [], {}
    for i, (stratum, q, action, mid, gdims) in enumerate(cases, 1):
        cid = f"extmf_{i:03d}"
        strata_map.setdefault(stratum, []).append(cid)
        blind.append({"case_id": cid, "nl_query": q, "source": SOURCE_TAG})
        gold.append({"case_id": cid, "expected_action": action, "expected_dimensions": gdims,
                     "expected_metric_id": mid, "expected_time_window": ""})
        merged.append({"case_id": cid, "nl_query": q, "source": SOURCE_TAG, "stratum": stratum,
                       "expected_action": action, "expected_dimensions": gdims,
                       "expected_metric_id": mid, "expected_time_window": ""})

    def dump_jsonl(path, rows):
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n",
                        encoding="utf-8")

    dump_jsonl(DATA / "blind_cases.jsonl", blind)
    dump_jsonl(DATA / "gold_labels.jsonl", gold)
    dump_jsonl(DATA / "test_cases.jsonl", merged)
    audit = {
        "seed": SEED,
        "generator": "generate_cases.py (pure templates, no LLM, no network)",
        "total_cases": len(cases),
        "strata_counts": {k: len(v) for k, v in sorted(strata_map.items())},
        "strata_case_ids": {k: v for k, v in sorted(strata_map.items())},
        "gold_derivation": "mechanical from contract: allowed_dimensions scope + parent-map finest-grain"
        " resolution + protocol refusal classes (r1 undefined stub, r2 sql_or_ddl rule, r3 unauthorized"
        " dimension combination). Compiler decision function never called during generation.",
        "ambiguity_guard": {
            "rule": "rendered query kept only if published detection grammar mentions exactly the intended dims",
            "excluded_dimensions": excluded_dims,
            "rejected_draws": rejected,
        },
        "template_families": {
            "S1_size0": t0, "S1_size1": t1, "S1_size2": t2,
            "S2": s2_templates,
            "S3": ["{M} by {t}.", "Show {m} grouped by {t}.", "{M} by {l} and {t}."],
            "S4": ["What is total {p}?", "Show {p} by month."],
            "S5": sql_templates,
        },
        "answerable_metric_pool": len(answerable),
        "s2_universe_size": len(s2_universe),
        "s3_universe": {"singles": len(singles), "pairs": len(pairs)},
        "s4_universe_size": len(s4_universe),
    }
    (DATA / "generation_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"total": len(cases), "strata": audit["strata_counts"],
                      "rejected_draws": len(rejected),
                      "excluded_dimensions": sorted(excluded_dims)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
