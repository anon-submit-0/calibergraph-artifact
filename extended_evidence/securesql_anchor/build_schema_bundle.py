#!/usr/bin/env python3
"""Build the frozen schema bundle for SecureSQL anchor experiment.

Sources (mirrored under data/, provenance in data/SOURCES.md):
  - spider_union_tables.json : Spider tables.json union (162 schemas, incl. train_others/yelp)
  - bird_dev_tables.json     : official BIRD dev_tables.json (bird-bench OSS)
  - bird_train_tables.json   : official BIRD train_tables.json (bird-bench OSS)

Output: data/schemas_57.json  {db_id: {"source":..., "tables": {table: [cols...]}}}

Validation: every table referenced in every example's queries (FROM/JOIN
targets) must exist in the chosen schema; every qualified table.column must
exist. For db_ids present in multiple sources the source with full coverage
is chosen (tie -> spider). Any residual mismatch is printed honestly.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


def load_spider_format(path):
    out = {}
    for e in json.load(open(path)):
        tables = e["table_names_original"]
        cols = defaultdict(list)
        for ti, col in e["column_names_original"]:
            if ti < 0:
                continue
            cols[tables[ti]].append(col)
        out[e["db_id"]] = {t: cols[t] for t in tables}
    return out


TABLE_RE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", re.I)
QUAL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)")
ALIAS_RE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:as\s+)?([A-Za-z_][A-Za-z0-9_]*)", re.I)
KEYWORDS = {"where", "on", "join", "inner", "left", "right", "outer", "group",
            "order", "having", "limit", "union", "intersect", "except", "select", "as", "cross"}


def referenced(sql):
    tables = set(m.group(1).lower() for m in TABLE_RE.finditer(sql))
    aliases = {}
    for m in ALIAS_RE.finditer(sql):
        t, a = m.group(1), m.group(2)
        if a.lower() not in KEYWORDS:
            aliases[a.lower()] = t.lower()
    quals = set()
    for m in QUAL_RE.finditer(sql):
        t, c = m.group(1).lower(), m.group(2).lower()
        t = aliases.get(t, t)
        quals.add((t, c))
    return tables, quals


def coverage_errors(schema, examples):
    tset = {t.lower() for t in schema}
    cset = {(t.lower(), c.lower()) for t, cols in schema.items() for c in cols}
    errs = []
    for ex in examples:
        for sql in ex["queries"]:
            tabs, quals = referenced(sql)
            for t in tabs:
                if t not in tset:
                    errs.append((ex["id"], "table", t))
            for t, c in quals:
                if t in tset and (t, c) not in cset:
                    errs.append((ex["id"], "column", f"{t}.{c}"))
    return errs


def main():
    data = json.load(open(DATA / "data_unzipped" / "data.json"))
    by_db = defaultdict(list)
    for ex in data:
        by_db[ex["db_id"]].append(ex)

    sources = {
        "spider": load_spider_format(DATA / "spider_union_tables.json"),
        "bird_dev": load_spider_format(DATA / "bird_dev_tables.json"),
        "bird_train": load_spider_format(DATA / "bird_train_tables.json"),
    }
    order = ["spider", "bird_dev", "bird_train"]

    bundle = {}
    report = []
    for db, exs in sorted(by_db.items()):
        candidates = [(name, sources[name][db]) for name in order if db in sources[name]]
        if not candidates:
            report.append(f"MISSING schema for {db}")
            continue
        scored = []
        for name, schema in candidates:
            errs = coverage_errors(schema, exs)
            scored.append((len(errs), name, schema, errs))
        scored.sort(key=lambda x: (x[0], order.index(x[1])))
        nerr, name, schema, errs = scored[0]
        bundle[db] = {"source": name, "tables": schema}
        line = f"{db}: source={name} examples={len(exs)} coverage_errors={nerr}"
        if nerr:
            line += " " + json.dumps(errs[:6])
        report.append(line)

    out = DATA / "schemas_57.json"
    json.dump(bundle, open(out, "w"), indent=1, ensure_ascii=False)
    print("\n".join(report))
    total_err = sum(1 for r in report if "coverage_errors=0" not in r)
    print(f"\ndbs={len(bundle)} dbs_with_any_error={total_err}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
