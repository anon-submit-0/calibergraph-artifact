#!/usr/bin/env python3
"""Arm A step 2: deterministic disclosure checker (protocol.md §3.1, frozen).

Applies compiled policy nodes to each example's SQL chat history.
Rules R1 / R1a / R2 / R3a / R3b exactly as pre-registered.
Fallbacks (frozen): uncompilable policy -> unsafe (primary; secondary analysis
excludes); unparseable SQL after regex fallback -> unsafe + undecidable flag.

Usage:
  python3 checker.py original   -> armA_original.json   (all 932)
  python3 checker.py perturbed  -> armA_perturbed.json  (300 subsample variants)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import sqlglot
from sqlglot import exp

import common
from common import HERE

AGG_FUNCS = {"sum": exp.Sum, "min": exp.Min, "max": exp.Max, "avg": exp.Avg, "count": exp.Count}


def norm(s):
    return str(s).strip().strip("'\"").lower() if s is not None else None


def quote_spaced_columns(sql, tables):
    """BIRD schemas contain column names with spaces; quote them so sqlglot can parse."""
    spaced = sorted({c for cols in tables.values() for c in cols if " " in c},
                    key=len, reverse=True)
    for col in spaced:
        pat = re.compile(r'(?<!")' + re.escape(col) + r'(?!")', re.I)
        sql = pat.sub('"' + col + '"', sql)
    return sql


class ParsedQuery:
    def __init__(self):
        self.out = []          # list of {"table","column","agg":None|func}
        self.preds = []        # list of {"table","column","op","literal","negated"}
        self.order_sig = None  # normalized order-by signature or None
        self.tables = set()
        self.has_where = False
        self.parse_mode = "sqlglot"


def resolve_column(col_name, table_hint, alias_map, tables):
    """Resolve (table_hint, col_name) to a concrete (table, column) using schema."""
    cl = norm(col_name)
    if table_hint:
        t = alias_map.get(norm(table_hint), norm(table_hint))
        return (t, cl)
    for t in alias_map.values():
        cols = {norm(c) for c in tables.get_real(t)}
        if cl in cols:
            return (t, cl)
    return (None, cl)


class SchemaView:
    def __init__(self, tables):
        self._orig = tables
        self._by_lower = {t.lower(): t for t in tables}

    def get_real(self, t_lower):
        real = self._by_lower.get(t_lower)
        return self._orig.get(real, []) if real else []

    def table_names(self):
        return set(self._by_lower.keys())


def _literals_of(node):
    if isinstance(node, exp.Literal):
        return [norm(node.this)]
    if isinstance(node, (exp.Tuple, exp.Array)):
        return [norm(e.this) for e in node.expressions if isinstance(e, exp.Literal)]
    return []


def parse_with_sqlglot(sql, tables):
    pq = ParsedQuery()
    sv = SchemaView(tables)
    tree = sqlglot.parse_one(sql, read="sqlite")

    alias_map = {}
    for t in tree.find_all(exp.Table):
        real = norm(t.name)
        alias = norm(t.alias) if t.alias else real
        alias_map[alias] = real
        pq.tables.add(real)

    def rescol(c: exp.Column):
        return resolve_column(c.name, c.table or None, alias_map, sv)

    # ---- outputs from the outermost select(s) (handle UNION by walking both sides)
    def outer_selects(node):
        if isinstance(node, exp.Select):
            return [node]
        if isinstance(node, exp.Union):
            return outer_selects(node.left) + outer_selects(node.right)
        found = node.find(exp.Select)
        return [found] if found else []

    for sel in outer_selects(tree):
        for e in sel.expressions:
            expr = e.this if isinstance(e, exp.Alias) else e
            if isinstance(expr, exp.Star):
                for t in {alias_map[a] for a in alias_map}:
                    for c in sv.get_real(t):
                        pq.out.append({"table": t, "column": norm(c), "agg": None})
                continue
            if isinstance(expr, exp.Column) and isinstance(expr.this, exp.Star):
                t = alias_map.get(norm(expr.table), norm(expr.table))
                for c in sv.get_real(t):
                    pq.out.append({"table": t, "column": norm(c), "agg": None})
                continue
            agg = None
            for fname, ftype in AGG_FUNCS.items():
                if isinstance(expr, ftype):
                    agg = fname
                    break
            if agg is None and isinstance(expr, exp.Anonymous):
                nm = norm(expr.this)
                if nm in AGG_FUNCS:
                    agg = nm
            inner_cols = list(expr.find_all(exp.Column))
            if isinstance(expr, exp.Column):
                t, c = rescol(expr)
                pq.out.append({"table": t, "column": c, "agg": None})
            elif inner_cols:
                for c in inner_cols:
                    t, cn = rescol(c)
                    pq.out.append({"table": t, "column": cn, "agg": agg or "expr"})
            elif agg == "count":  # count(*)
                pq.out.append({"table": None, "column": "*", "agg": "count"})

        # ---- order by (outermost select level)
        order = sel.args.get("order")
        if order is not None:
            parts = []
            for o in order.expressions:
                cols = [rescol(c) for c in o.find_all(exp.Column)]
                d = "desc" if o.args.get("desc") else "asc"
                parts.append(("|".join(f"{t}.{c}" for t, c in cols), d))
            if parts:
                pq.order_sig = ";".join(f"{p[0]}:{p[1]}" for p in parts)

        if sel.args.get("where") is not None:
            pq.has_where = True

    # ---- predicates at ALL depths (WHERE/HAVING/ON literal comparisons)
    def neg_context(node):
        """Amendment 1.3: pure count of NOT ancestors, mod 2 (covers NOT IN subqueries)."""
        n, d = node.parent, 0
        while n is not None:
            if isinstance(n, exp.Not):
                d += 1
            n = n.parent
        return d % 2 == 1

    for node in tree.walk():
        if isinstance(node, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Like, exp.ILike)):
            left, right = node.left, node.right
            col, lit_node = None, None
            if isinstance(left, exp.Column) and not isinstance(right, exp.Column):
                col, lit_node = left, right
            elif isinstance(right, exp.Column) and not isinstance(left, exp.Column):
                col, lit_node = right, left
            if col is None:
                continue
            lits = _literals_of(lit_node)
            op = {exp.EQ: "=", exp.NEQ: "!=", exp.GT: ">", exp.GTE: ">=",
                  exp.LT: "<", exp.LTE: "<=", exp.Like: "like", exp.ILike: "like"}[type(node)]
            t, c = rescol(col)
            negated = neg_context(node)
            for lit in (lits or [None]):
                pq.preds.append({"table": t, "column": c, "op": op, "literal": lit, "negated": negated})
        elif isinstance(node, exp.In):
            col = node.this if isinstance(node.this, exp.Column) else None
            if col is None:
                continue
            t, c = rescol(col)
            negated = isinstance(node.parent, exp.Not)
            lits = []
            for e in node.expressions or []:
                lits.extend(_literals_of(e))
            if node.args.get("query") is not None:
                pq.preds.append({"table": t, "column": c, "op": "in_subquery",
                                 "literal": None, "negated": negated})
            for lit in lits:
                pq.preds.append({"table": t, "column": c, "op": "=", "literal": lit, "negated": negated})
    return pq


FALLBACK_SEL = re.compile(r"select\s+(distinct\s+)?(.*?)\s+from\s", re.I | re.S)
FALLBACK_TAB = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", re.I)
FALLBACK_QUAL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)")


def parse_fallback(sql, tables):
    pq = ParsedQuery()
    pq.parse_mode = "regex_fallback"
    sv = SchemaView(tables)
    m = FALLBACK_SEL.search(sql)
    pq.tables = {t.lower() for t in FALLBACK_TAB.findall(sql)}
    alias_map = {t: t for t in pq.tables}
    if not m:
        return None
    for part in m.group(2).split(","):
        part = part.strip()
        agg = None
        am = re.match(r"(sum|min|max|avg|count)\s*\(", part, re.I)
        if am:
            agg = am.group(1).lower()
        qm = FALLBACK_QUAL.search(part)
        if qm:
            pq.out.append({"table": qm.group(1).lower(), "column": qm.group(2).lower(), "agg": agg})
        else:
            tok = re.search(r"([A-Za-z_][A-Za-z0-9_]*)", re.sub(r"(?i)\b(distinct|as|sum|min|max|avg|count)\b", "", part) or "")
            if tok:
                t, c = resolve_column(tok.group(1), None, alias_map, sv)
                pq.out.append({"table": t, "column": c, "agg": agg})
    wpos = re.search(r"\bwhere\b", sql, re.I)
    if wpos:
        pq.has_where = True
        tail = sql[wpos.end():]
        for qm in FALLBACK_QUAL.finditer(tail):
            pq.preds.append({"table": qm.group(1).lower(), "column": qm.group(2).lower(),
                             "op": "?", "literal": None, "negated": bool(re.search(r"\bnot\b", tail, re.I))})
    om = re.search(r"order\s+by\s+(.+?)(?:limit\b|$)", sql, re.I | re.S)
    if om:
        pq.order_sig = " ".join(om.group(1).lower().split())
    return pq if pq.out else None


# ---------------- policy application ----------------

def match_pc(pc, t, c):
    return norm(pc.get("table")) == t and norm(pc.get("column")) == c


def scope_excluded(preds, scope):
    """Frozen R1 exclusion: predicate on scope_column that negates the scope value
    or equals a different literal."""
    if not scope:
        return False
    sc_t, sc_c, sc_v = norm(scope.get("scope_table")), norm(scope.get("scope_column")), norm(scope.get("value"))
    for p in preds:
        if p["column"] != sc_c:
            continue
        if p["table"] not in (sc_t, None):
            continue
        lit = norm(p["literal"])
        if p["op"] in ("=",) and p["negated"] and lit == sc_v:
            return True
        if p["op"] in ("!=",) and not p["negated"] and lit == sc_v:
            return True
        if p["op"] in ("=",) and not p["negated"] and lit is not None and lit != sc_v:
            return True
    return False


def scope_matched(preds, scope):
    """Non-negated equality on scope column with the scope literal (narrowing)."""
    if not scope:
        return False
    sc_t, sc_c, sc_v = norm(scope.get("scope_table")), norm(scope.get("scope_column")), norm(scope.get("value"))
    for p in preds:
        if p["column"] == sc_c and p["table"] in (sc_t, None) and p["op"] == "=" \
                and not p["negated"] and norm(p["literal"]) == sc_v:
            return True
    return False


def judge_example(queries, policy, tables):
    """Returns (pred, fired, undecidable, parse_modes)."""
    fired = []
    if not isinstance(policy, dict) or policy.get("compilable") is not True:
        return "unsafe", ["FALLBACK_uncompilable"], False, []

    kind = policy.get("protection_kind") or "other"
    pcs = policy.get("protected_columns") or []
    idents = {(norm(i.get("table")), norm(i.get("column"))) for i in (policy.get("identifier_columns") or [])}

    parsed = []
    modes = []
    undecidable = False
    for sql in queries:
        sql2 = quote_spaced_columns(sql, tables)
        pq = None
        try:
            pq = parse_with_sqlglot(sql2, tables)
        except Exception:
            pq = None
        if pq is None or not (pq.out or pq.preds):
            fb = parse_fallback(sql, tables)
            if fb is not None:
                pq = fb
            else:
                undecidable = True
                modes.append("undecidable")
                continue
        parsed.append(pq)
        modes.append(pq.parse_mode)

    if undecidable:
        return "unsafe", ["FALLBACK_undecidable_sql"], True, modes

    protected_hit = lambda t, c: next((pc for pc in pcs if match_pc(pc, t, c)), None)

    # ---- per-query rules
    for pq in parsed:
        if kind == "row_access":
            # Amendment 1.2: row_access uses ONLY the dedicated rule; generic R1/R1a/R2 skipped
            affected = {norm(pc.get("table")) for pc in pcs}
            outs_from_affected = [o for o in pq.out if o["table"] in affected]
            if outs_from_affected:
                allowed = next((pc.get("row_scope") for pc in pcs if pc.get("row_scope")), None)
                if not scope_matched(pq.preds, allowed):
                    fired.append("R1_row_access")
            continue
        for o in pq.out:
            pc = protected_hit(o["table"], o["column"])
            if pc is None:
                continue
            scope = pc.get("row_scope")
            if o["agg"] is None or o["agg"] == "expr":
                if scope_excluded(pq.preds, scope):
                    continue
                if kind == "attribution":
                    # Amendment 1.1: attribution requires linkage within the same query
                    others = [x for x in pq.out if protected_hit(x["table"], x["column"]) is None]
                    linked = (any((x["table"], x["column"]) in idents for x in others)
                              if idents else bool(others))
                    if linked:
                        fired.append("R1")
                else:
                    fired.append("R1")
            else:
                if o["agg"] in ("min", "max"):
                    fired.append("R1a_minmax")
                elif kind == "aggregate" and scope is not None and scope_matched(pq.preds, scope):
                    fired.append("R1a_narrowed")
        if kind in ("value", "attribution"):
            for p in pq.preds:
                if protected_hit(p["table"], p["column"]) is not None and pq.out:
                    fired.append("R2")
                    break

    # ---- R3 combination rules (across queries)
    if len(parsed) >= 2:
        for i in range(len(parsed)):
            for j in range(i + 1, len(parsed)):
                a, b = parsed[i], parsed[j]
                aligned = False
                if a.order_sig and a.order_sig == b.order_sig and a.tables == b.tables:
                    aligned = True
                elif (not a.has_where and not b.has_where and a.tables == b.tables
                      and len(a.tables) == 1 and not a.order_sig and not b.order_sig):
                    aligned = True
                if aligned:
                    union_out = [(o["table"], o["column"]) for o in a.out + b.out]
                    prot = [tc for tc in union_out if protected_hit(*tc)]
                    others = [tc for tc in union_out if not protected_hit(*tc)]
                    if prot and others:
                        if kind == "attribution":
                            if idents and not any(tc in idents for tc in others):
                                continue
                            fired.append("R3a")
                        else:
                            fired.append("R3a")
                # complement aggregates
                a_aggs = {(o["table"], o["column"], o["agg"]) for o in a.out if o["agg"] in ("sum", "avg", "count")}
                b_aggs = {(o["table"], o["column"], o["agg"]) for o in b.out if o["agg"] in ("sum", "avg", "count")}
                shared = a_aggs & b_aggs
                if shared:
                    a_neg = any(p["negated"] for p in a.preds)
                    b_neg = any(p["negated"] for p in b.preds)
                    if (a_neg and not b.preds) or (b_neg and not a.preds):
                        fired.append("R3b")

    return ("unsafe" if fired else "safe"), sorted(set(fired)), False, modes


def run(mode):
    schemas = common.load_schemas()
    data = common.load_data()
    if mode == "original":
        nodes = json.loads((HERE / "policy_nodes.json").read_text())
        examples = [(ex, ex["security_condition"], ex["db_id"]) for ex in data]
        out_path = HERE / "armA_original.json"
    else:
        nodes = json.loads((HERE / "policy_nodes_perturbed.json").read_text())
        pert = json.loads((HERE / "perturbed_300.json").read_text())
        by_id = {ex["id"]: ex for ex in data}
        examples = []
        for k, pex in pert.items():
            orig = by_id[pex["id"]]
            examples.append((pex, orig["security_condition"], pex["db_id"]))
        out_path = HERE / "armA_perturbed.json"

    results = {}
    stats = {"unsafe": 0, "safe": 0, "uncompilable": 0, "undecidable": 0}
    for ex, cond_key, db in examples:
        policy = nodes.get(f"{db}||{cond_key}")
        tables = schemas[db]["tables"]
        pred, fired, und, modes = judge_example(ex["queries"], policy, tables)
        results[str(ex["id"])] = {
            "id": ex["id"], "db_id": db, "label": ex["label"], "pred": pred,
            "fired": fired, "undecidable": und, "parse_modes": modes,
            "policy_compilable": bool(isinstance(policy, dict) and policy.get("compilable") is True),
        }
        stats[pred] += 1
        stats["uncompilable"] += int("FALLBACK_uncompilable" in fired)
        stats["undecidable"] += int(und)
    out_path.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path.name}: n={len(results)} {stats}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["original", "perturbed"])
    run(ap.parse_args().mode)
