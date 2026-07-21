#!/usr/bin/env python3
"""Mechanical converter: dbt/MetricFlow semantic manifest YAML -> MetricCaliberBench contract layer.

Source (third-party, NOT authored by the paper authors; frozen local copy):
  v21_external_baseline_runs_20260708/public_artifact/external_runs/metricflow/
    metricflow_semantics/test_helpers/semantic_manifest_yamls/simple_manifest/
  (upstream: github.com/dbt-labs/metricflow, Apache-2.0; written/maintained by dbt Labs engineers)

Target schema: aligned with v24 public_benchmark layers
  (iowa_liquor_metric_caliber / multigov_metric_caliber field structures):
  metric_catalog.jsonl, dimension_catalog.jsonl, governance_edges.jsonl,
  physical_coverage.jsonl, metric_coverage_bindings.jsonl, policy_catalog.jsonl,
  contract_profile.json (+ README.md).

FROZEN MAPPING RULES (per pre-registered protocol.md, 2026-07-12; no deviation):

1. semantic_models -> physical binding
   Each semantic_model's node_relation (schema `$source_schema`, alias, e.g. `fct_bookings`)
   becomes one physical_coverage row; each metric gets metric_coverage_bindings rows that
   bind every transitive measure dependency node (`measure.<name>`) to the physical table of
   the semantic model that declares the measure. metric_catalog carries
   coverage_nodes/coverage_required so the compiler's coverage check runs in
   "metric_specific_semantic_to_physical_binding" mode.

2. entities/dimensions -> dimension catalog and hierarchy edges
   - Categorical model dimensions become catalog dimensions with id
     `<primary_entity>__<dimension_name>` (MetricFlow qualified-name convention) and
     sql = the dimension's physical expr (or its name when expr is omitted).
   - Time-type model dimensions are NOT emitted as standalone catalog dimensions; per the
     protocol rule "agg_time_dimension -> time grain", time is modeled as the shared
     metric_time grain ladder: metric_time__{hour,day,week,month,quarter,year}.
     rolls_up_to hierarchy edges follow strict containment only:
     hour->day->month->quarter->year (week has no parent: ISO weeks do not nest in months).
   - Join reachability (single hop, MetricFlow entity-join semantics): a metric whose measure
     lives in model M may group by (a) M's own categorical dimensions, (b) categorical
     dimensions of any model M' that declares one of M's entities as `primary` or `unique`,
     and (c) metric_time grains >= the metric's minimum time granularity, where the minimum
     granularity is the measure-level agg_time_dimension granularity (falling back to the
     model default), optionally coarsened by a metric-level `time_granularity`.

3. metrics(simple/ratio/derived) -> metric definitions
   - simple: formula rendered from the measure agg over its physical expr
     (sum->SUM, count->COUNT, count_distinct->COUNT(DISTINCT ..), average->AVG,
      max->MAX, min->MIN, sum_boolean->SUM(CAST(.. AS INTEGER)), median->MEDIAN,
      percentile->PERCENTILE_CONT(.., p)). Metric/measure-level filters and
     join_to_timespine/fill_nulls_with params are preserved verbatim in extra fields
     (`filter`, `measure_input_params`) -- they do not change bindings.
   - measures declaring `create_metric: true` also become simple metrics of the same name
     (dbt semantics).
   - ratio: numerator/denominator EXPLICITLY enter the contract: numerator_nodes /
     denominator_nodes reference the input metric ids, matching numerator_of/denominator_of
     governance edges (with metric_id), plus transparent `numerator`/`denominator` SQL
     strings. allowed_dimensions = intersection of numerator-side and denominator-side
     allowed sets; minimum grain = coarsest input minimum grain.
   - derived: formula = the manifest expr verbatim; input metrics (with alias/offset
     specs preserved in `input_metrics`) resolved transitively. If the expr contains `/`,
     the metric is ratio-like: the expr is split at the first `/` and metric tokens on each
     side become numerator_nodes/denominator_nodes plus the matching typed edges.
     allowed_dimensions = intersection over all inputs.
   - cumulative / conversion metrics, and derived metrics transitively depending on them,
     are NOT expressible in the target contract format: they are kept in the catalog as
     answerable=false entries (source flag `mf_manifest_unsupported_type` /
     `mf_manifest_unsupported_dependency`) so the conversion is complete and lossless at the
     definition level, but no benchmark cases are generated against them.

4. REFUSAL POLICY -- protocol-added, NOT in source manifest.
   The dbt manifest defines no refusal behavior. Per the frozen protocol, exactly three
   refusal classes are added by the conversion and are explicitly flagged as such:
     (r1) undefined-metric requests  -> `protocol_added_refusal_stub` catalog entries
          (answerable=false; aliases list business metrics that do NOT exist in the
          manifest, e.g. profit margin / churn rate), mirroring the iowa `profit_margin`
          stub design;
     (r2) SQL/DDL requests           -> contract_profile policy rule `sql_or_ddl`
          (contains-triggers select/insert/update/delete/drop/truncate/alter);
     (r3) unauthorized dimension combinations -> structural: allowed_dimensions scope
          derived from manifest join topology (rule 2/3 above); grouping outside the scope
          is a contract violation.
   Every one of these artifacts carries provenance "protocol-added, not in source manifest".

Determinism: pure mechanical transformation, no randomness, no LLM, no network.
Run:  python3 convert_mf_manifest.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SOURCE = Path(
    "<REPO_ROOT>/releases/"
    "v21_external_baseline_runs_20260708/public_artifact/external_runs/metricflow/"
    "metricflow_semantics/test_helpers/semantic_manifest_yamls/simple_manifest"
)
OUT = HERE / "external_mf_metric_caliber"

DATASET_ID = "external_mf_metric_caliber"
DOMAIN_ID = "mf_simple_manifest"
PROTOCOL_NOTE = "protocol-added, not in source manifest"

GRAIN_ORDER = ["hour", "day", "week", "month", "quarter", "year"]
# strict containment ladder only (week does not nest in month)
GRAIN_PARENT = {"hour": "day", "day": "month", "week": "", "month": "quarter", "quarter": "year", "year": ""}
GRAIN_RANK = {"year": 1, "quarter": 2, "month": 3, "week": 4, "day": 5, "hour": 6}
# sub-day manifest granularities that collapse onto the hour grain for contract purposes
SUBHOUR = {"nanosecond", "microsecond", "millisecond", "second", "minute"}

AGG_SQL = {
    "sum": "SUM({x})",
    "count": "COUNT({x})",
    "count_distinct": "COUNT(DISTINCT {x})",
    "average": "AVG({x})",
    "max": "MAX({x})",
    "min": "MIN({x})",
    "sum_boolean": "SUM(CAST({x} AS INTEGER))",
    "median": "MEDIAN({x})",
    "percentile": "PERCENTILE_CONT({x}, {p})",
}

REFUSAL_STUBS = [
    ("profit_margin", ["profit margin", "gross margin", "margin", "profit rate"]),
    ("churn_rate", ["churn rate", "customer churn", "churn"]),
    ("customer_acquisition_cost", ["customer acquisition cost", "cac", "acquisition cost"]),
    ("net_promoter_score", ["net promoter score", "nps"]),
    ("inventory_turnover", ["inventory turnover", "stock turnover"]),
    ("employee_headcount", ["employee headcount", "headcount", "number of employees"]),
]


def phrase(name: str) -> str:
    return name.replace("_", " ").strip()


def title(name: str) -> str:
    return " ".join(w.capitalize() for w in phrase(name).split())


def load_yaml_docs():
    files = [SOURCE / "metrics.yaml"] + sorted((SOURCE / "semantic_models").glob("*.yaml"))
    docs = []
    for path in files:
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if doc:
                docs.append((path.name, doc))
    return docs


def normalize_grain(g):
    g = str(g or "day").lower()
    if g in SUBHOUR:
        return "hour"
    return g if g in GRAIN_ORDER else "day"


def coarser(g1, g2):
    return g1 if GRAIN_ORDER.index(g1) >= GRAIN_ORDER.index(g2) else g2


def grains_at_or_above(min_grain):
    idx = GRAIN_ORDER.index(min_grain)
    return [f"metric_time__{g}" for g in GRAIN_ORDER[idx:]]


class Manifest:
    def __init__(self):
        self.models = {}          # name -> model dict
        self.measure_model = {}   # measure name -> model name
        self.measures = {}        # measure name -> measure dict
        self.raw_metrics = []     # (name, metric dict)

    def add_model(self, sm):
        name = sm["name"]
        self.models[name] = sm
        for meas in sm.get("measures", []) or []:
            self.measures[meas["name"]] = meas
            self.measure_model[meas["name"]] = name

    def primary_entity(self, model):
        if model.get("primary_entity"):
            return model["primary_entity"]
        for ent in model.get("entities", []) or []:
            if ent.get("type") == "primary":
                return ent["name"]
        return model["name"]

    def physical_table(self, model):
        rel = model.get("node_relation", {}) or {}
        return rel.get("alias", model["name"])

    def model_entities(self, model):
        ents = {e["name"] for e in model.get("entities", []) or []}
        if model.get("primary_entity"):
            ents.add(model["primary_entity"])
        return ents

    def joinable_models(self, model_name):
        """Single-hop MetricFlow join semantics: target declares a shared entity as primary/unique."""
        model = self.models[model_name]
        out = {model_name}
        for ent in self.model_entities(model):
            for other_name, other in self.models.items():
                if other_name == model_name:
                    continue
                for oe in other.get("entities", []) or []:
                    if oe["name"] == ent and oe.get("type") in ("primary", "unique"):
                        out.add(other_name)
        return sorted(out)

    def categorical_dims(self, model_name):
        model = self.models[model_name]
        prefix = self.primary_entity(model)
        rows = []
        for dim in model.get("dimensions", []) or []:
            if dim.get("type") == "categorical":
                rows.append(
                    {
                        "dimension_id": f"{prefix}__{dim['name']}",
                        "name": title(dim["name"]),
                        "aliases": [phrase(dim["name"]), f"{phrase(prefix)} {phrase(dim['name'])}"],
                        "parent": "",
                        "grain_rank": 1,
                        "sql": dim.get("expr") or dim["name"],
                        "source_model": model_name,
                    }
                )
        return rows

    def time_dim_grain(self, model, dim_name):
        for dim in model.get("dimensions", []) or []:
            if dim["name"] == dim_name and dim.get("type") == "time":
                return normalize_grain((dim.get("type_params") or {}).get("time_granularity"))
        return "day"

    def measure_min_grain(self, measure_name):
        model = self.models[self.measure_model[measure_name]]
        meas = self.measures[measure_name]
        agg_time = meas.get("agg_time_dimension") or (model.get("defaults") or {}).get("agg_time_dimension")
        if not agg_time:
            return "day"
        return self.time_dim_grain(model, agg_time)


def build():
    mf = Manifest()
    docs = load_yaml_docs()
    for fname, doc in docs:
        if "semantic_model" in doc:
            mf.add_model(doc["semantic_model"])
    for fname, doc in docs:
        if "metric" in doc:
            mf.raw_metrics.append((fname, doc["metric"]))

    # ---- dimension catalog ----
    dim_rows = []
    for model_name in sorted(mf.models):
        dim_rows.extend(mf.categorical_dims(model_name))
    for g in GRAIN_ORDER:
        dim_rows.append(
            {
                "dimension_id": f"metric_time__{g}",
                "name": title(g),
                "aliases": [g, f"{g}ly" if g not in ("day",) else "daily"],
                "parent": f"metric_time__{GRAIN_PARENT[g]}" if GRAIN_PARENT[g] else "",
                "grain_rank": GRAIN_RANK[g],
                "sql": "",
                "source_model": "metric_time_grain_ladder(agg_time_dimension)",
            }
        )
    # fix english: weekly/monthly/quarterly/yearly/hourly/daily
    alias_fix = {"hour": ["hour", "hourly"], "day": ["day", "daily"], "week": ["week", "weekly"],
                 "month": ["month", "monthly"], "quarter": ["quarter", "quarterly"], "year": ["year", "yearly"]}
    for row in dim_rows:
        gid = row["dimension_id"]
        if gid.startswith("metric_time__"):
            row["aliases"] = alias_fix[gid.split("__")[1]]
    dims_by_id = {r["dimension_id"]: r for r in dim_rows}

    # allowed categorical dims per model (single-hop join closure)
    model_cat_dims = {}
    for model_name in sorted(mf.models):
        acc = []
        for reach in mf.joinable_models(model_name):
            acc.extend(d["dimension_id"] for d in mf.categorical_dims(reach))
        model_cat_dims[model_name] = sorted(set(acc))

    # ---- metric catalog ----
    metrics = {}
    order = []

    def measure_formula(meas):
        expr = str(meas.get("expr") or meas["name"])
        agg = str(meas.get("agg", "sum")).lower()
        template = AGG_SQL.get(agg)
        if template is None:
            return None
        p = ""
        if agg == "percentile":
            p = str((meas.get("agg_params") or {}).get("percentile", 0.5))
        return template.format(x=expr, p=p)

    def add_simple(name, measure_spec, metric_filter, time_gran, description, origin):
        if isinstance(measure_spec, dict):
            measure_name = measure_spec["name"]
            measure_params = {k: v for k, v in measure_spec.items() if k != "name"}
        else:
            measure_name = measure_spec
            measure_params = {}
        meas = mf.measures[measure_name]
        model_name = mf.measure_model[measure_name]
        formula = measure_formula(meas)
        min_grain = mf.measure_min_grain(measure_name)
        if time_gran:
            min_grain = coarser(min_grain, normalize_grain(time_gran))
        allowed = sorted(set(model_cat_dims[model_name]) | set(grains_at_or_above(min_grain)))
        row = {
            "metric_id": name,
            "metric_name": title(name),
            "aliases": [phrase(name)],
            "description": description or phrase(name),
            "formula": formula or "",
            "allowed_dimensions": allowed if formula else [],
            "answerable": bool(formula),
            "metric_type": "simple",
            "domain_id": DOMAIN_ID,
            "numerator_nodes": [],
            "denominator_nodes": [],
            "numerator": "",
            "denominator": "",
            "coverage_required": bool(formula),
            "coverage_nodes": [f"measure.{measure_name}"] if formula else [],
            "min_time_grain": min_grain,
            "measure_dependencies": [measure_name],
            "filter": metric_filter or "",
            "measure_input_params": measure_params,
            "input_metrics": [],
            "source": origin,
        }
        if not formula:
            row["answerable"] = False
            row["source"] = "mf_manifest_unsupported_aggregation"
            row["description"] += f" [aggregation '{meas.get('agg')}' not expressible in contract SQL subset]"
        metrics[name] = row
        order.append(name)

    # pass 1: simple + placeholders for others
    pending = []
    for fname, m in mf.raw_metrics:
        name, mtype, tp = m["name"], m["type"], m.get("type_params", {}) or {}
        if mtype == "simple":
            add_simple(name, tp["measure"], m.get("filter"), m.get("time_granularity"),
                       m.get("description"), "mf_manifest_metric_simple")
        elif mtype in ("cumulative", "conversion"):
            metrics[name] = {
                "metric_id": name,
                "metric_name": title(name),
                "aliases": [phrase(name)],
                "description": (m.get("description") or phrase(name))
                + f" [metric type '{mtype}' not expressible in the MetricCaliber contract format;"
                " kept for catalog completeness, no cases generated]",
                "formula": "",
                "allowed_dimensions": [],
                "answerable": False,
                "metric_type": mtype,
                "domain_id": DOMAIN_ID,
                "numerator_nodes": [],
                "denominator_nodes": [],
                "numerator": "",
                "denominator": "",
                "coverage_required": False,
                "coverage_nodes": [],
                "min_time_grain": "",
                "measure_dependencies": [],
                "filter": m.get("filter") or "",
                "measure_input_params": {},
                "input_metrics": [],
                "source": "mf_manifest_unsupported_type",
            }
            order.append(name)
        else:
            pending.append((fname, m))

    # measures with create_metric: true also define metrics (dbt semantics)
    for measure_name in sorted(mf.measures):
        meas = mf.measures[measure_name]
        if meas.get("create_metric") and measure_name not in metrics:
            add_simple(measure_name, measure_name, None, None,
                       f"auto-created from measure '{measure_name}' (create_metric: true)",
                       "mf_manifest_create_metric_measure")

    # pass 2: ratio + derived (iterate until fixpoint for derived-on-derived)
    def resolve_inputs(input_specs):
        """returns (ok, input_rows, alias_map)"""
        rows, alias_map = [], {}
        for spec in input_specs:
            iname = spec["name"] if isinstance(spec, dict) else spec
            if iname not in metrics:
                return False, [], {}
            rows.append(spec if isinstance(spec, dict) else {"name": iname})
            alias_map[(spec.get("alias") if isinstance(spec, dict) else None) or iname] = iname
        return True, rows, alias_map

    def combine_inputs(input_names):
        """intersection of allowed dims; coarsest min grain; union coverage; answerable AND."""
        answerable = all(metrics[n]["answerable"] for n in input_names)
        if not answerable:
            return False, [], "", [], []
        allowed_sets = [set(metrics[n]["allowed_dimensions"]) for n in input_names]
        allowed = set.intersection(*allowed_sets) if allowed_sets else set()
        min_grain = "hour"
        for n in input_names:
            g = metrics[n]["min_time_grain"] or "hour"
            min_grain = coarser(min_grain, g)
        coverage = sorted({c for n in input_names for c in metrics[n]["coverage_nodes"]})
        measures = sorted({d for n in input_names for d in metrics[n]["measure_dependencies"]})
        return True, sorted(allowed), min_grain, coverage, measures

    def metric_tokens(text, alias_map):
        import re as _re
        toks = _re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text or "")
        return sorted({alias_map[t] for t in toks if t in alias_map})

    progress = True
    while pending and progress:
        progress = False
        remaining = []
        for fname, m in pending:
            name, mtype, tp = m["name"], m["type"], m.get("type_params", {}) or {}
            if mtype == "ratio":
                num_spec, den_spec = tp["numerator"], tp["denominator"]
                num_name = num_spec["name"] if isinstance(num_spec, dict) else num_spec
                den_name = den_spec["name"] if isinstance(den_spec, dict) else den_spec
                if num_name not in metrics or den_name not in metrics:
                    remaining.append((fname, m))
                    continue
                ok, allowed, min_grain, coverage, measures = combine_inputs([num_name, den_name])
                num_f = metrics[num_name]["formula"]
                den_f = metrics[den_name]["formula"]
                metrics[name] = {
                    "metric_id": name,
                    "metric_name": title(name),
                    "aliases": [phrase(name)],
                    "description": m.get("description") or phrase(name),
                    "formula": f"({num_f}) / NULLIF(({den_f}), 0)" if ok else "",
                    "allowed_dimensions": allowed,
                    "answerable": ok,
                    "metric_type": "ratio",
                    "domain_id": DOMAIN_ID,
                    "numerator_nodes": [num_name],
                    "denominator_nodes": [den_name],
                    "numerator": num_f,
                    "denominator": den_f,
                    "coverage_required": ok,
                    "coverage_nodes": coverage,
                    "min_time_grain": min_grain if ok else "",
                    "measure_dependencies": measures,
                    "filter": m.get("filter") or "",
                    "measure_input_params": {},
                    "input_metrics": [
                        {"role": "numerator", **(num_spec if isinstance(num_spec, dict) else {"name": num_spec})},
                        {"role": "denominator", **(den_spec if isinstance(den_spec, dict) else {"name": den_spec})},
                    ],
                    "source": "mf_manifest_metric_ratio" if ok else "mf_manifest_unsupported_dependency",
                }
                order.append(name)
                progress = True
            elif mtype == "derived":
                ok_resolve, input_rows, alias_map = resolve_inputs(tp.get("metrics", []) or [])
                if not ok_resolve:
                    remaining.append((fname, m))
                    continue
                input_names = sorted({r["name"] for r in input_rows})
                ok, allowed, min_grain, coverage, measures = combine_inputs(input_names)
                if m.get("time_granularity") and ok:
                    min_grain = coarser(min_grain, normalize_grain(m["time_granularity"]))
                    allowed = sorted(
                        (set(allowed) - {d for d in allowed if d.startswith("metric_time__")})
                        | set(grains_at_or_above(min_grain))
                    )
                expr = str(tp.get("expr") or "")
                num_nodes, den_nodes, num_sql, den_sql = [], [], "", ""
                if "/" in expr and ok:
                    left, right = expr.split("/", 1)
                    num_nodes = metric_tokens(left, alias_map)
                    den_nodes = metric_tokens(right, alias_map)
                    num_sql, den_sql = left.strip(), right.strip()
                metrics[name] = {
                    "metric_id": name,
                    "metric_name": title(name),
                    "aliases": [phrase(name)],
                    "description": (m.get("description") or phrase(name))
                    + ("" if ok else " [depends on cumulative/conversion metrics; not expressible"
                       " in the MetricCaliber contract format]"),
                    "formula": expr if ok else "",
                    "allowed_dimensions": allowed,
                    "answerable": ok,
                    "metric_type": "derived",
                    "domain_id": DOMAIN_ID,
                    "numerator_nodes": num_nodes,
                    "denominator_nodes": den_nodes,
                    "numerator": num_sql,
                    "denominator": den_sql,
                    "coverage_required": ok,
                    "coverage_nodes": coverage,
                    "min_time_grain": min_grain if ok else "",
                    "measure_dependencies": measures,
                    "filter": m.get("filter") or "",
                    "measure_input_params": {},
                    "input_metrics": input_rows,
                    "source": "mf_manifest_metric_derived" if ok else "mf_manifest_unsupported_dependency",
                }
                order.append(name)
                progress = True
            else:
                raise ValueError(f"unknown metric type {mtype} for {name}")
        pending = remaining
    if pending:
        raise RuntimeError(f"unresolved metrics after fixpoint: {[m['name'] for _, m in pending]}")

    # protocol-added undefined-metric refusal stubs (r1)
    for stub_id, aliases in REFUSAL_STUBS:
        metrics[stub_id] = {
            "metric_id": stub_id,
            "metric_name": title(stub_id),
            "aliases": aliases,
            "description": f"Not defined anywhere in the source dbt/MetricFlow manifest. [{PROTOCOL_NOTE}:"
            " undefined-metric refusal stub per frozen protocol.md]",
            "formula": "",
            "allowed_dimensions": [],
            "answerable": False,
            "metric_type": "undefined_stub",
            "domain_id": DOMAIN_ID,
            "numerator_nodes": [],
            "denominator_nodes": [],
            "numerator": "",
            "denominator": "",
            "coverage_required": False,
            "coverage_nodes": [],
            "min_time_grain": "",
            "measure_dependencies": [],
            "filter": "",
            "measure_input_params": {},
            "input_metrics": [],
            "source": "protocol_added_refusal_stub",
        }
        order.append(stub_id)

    # ---- governance edges ----
    edges = []
    for name in order:
        row = metrics[name]
        for dim_id in row["allowed_dimensions"]:
            edges.append({"edge_type": "measures_of", "src": name, "dst": dim_id})
        for node in row["numerator_nodes"]:
            edges.append({"edge_type": "numerator_of", "src": node, "dst": name, "metric_id": name})
        for node in row["denominator_nodes"]:
            edges.append({"edge_type": "denominator_of", "src": node, "dst": name, "metric_id": name})
        if row["answerable"]:
            edges.append({"edge_type": "governed_by", "src": name, "dst": "sql_or_ddl_policy"})
            edges.append({"edge_type": "governed_by", "src": name, "dst": "authorized_dimension_scope_policy"})
        else:
            edges.append({"edge_type": "governed_by", "src": name, "dst": "undefined_or_unsupported_metric_policy"})
    for row in dim_rows:
        if row["parent"]:
            edges.append({"edge_type": "rolls_up_to", "src": row["dimension_id"], "dst": row["parent"]})

    # ---- physical binding (rule 1) ----
    physical = []
    for i, model_name in enumerate(sorted(mf.models), 1):
        model = mf.models[model_name]
        physical.append(
            {
                "coverage_id": f"mf_cov_{i:03d}",
                "domain_id": DOMAIN_ID,
                "layer": "SOURCE",
                "semantic_node_id": mf.physical_table(model),
                "semantic_model": model_name,
                "schema_name": (model.get("node_relation", {}) or {}).get("schema_name", ""),
            }
        )
    bindings = []
    b = 0
    for name in order:
        row = metrics[name]
        for node in row["coverage_nodes"]:
            measure_name = node.split(".", 1)[1]
            model = mf.models[mf.measure_model[measure_name]]
            b += 1
            bindings.append(
                {
                    "binding_id": f"mf_binding_{b:04d}",
                    "domain_id": DOMAIN_ID,
                    "metric_id": name,
                    "dependency_node_id": node,
                    "physical_node_id": mf.physical_table(model),
                    "role": "required_asset",
                    "source_provenance_id": f"mf_manifest.{mf.measure_model[measure_name]}",
                }
            )

    # ---- policy catalog + contract profile (rules r1-r3, protocol-added) ----
    policies = [
        {
            "policy_id": "sql_or_ddl_policy",
            "policy_type": "request_form_policy",
            "action": "refuse",
            "domain_id": DOMAIN_ID,
            "public_rule": "refuse raw SQL/DDL authoring requests; only governed metric plans are served",
            "provenance": PROTOCOL_NOTE,
        },
        {
            "policy_id": "undefined_or_unsupported_metric_policy",
            "policy_type": "definition_policy",
            "action": "refuse",
            "domain_id": DOMAIN_ID,
            "public_rule": "refuse metrics that are undefined in the governed catalog or not expressible in the contract",
            "provenance": PROTOCOL_NOTE,
        },
        {
            "policy_id": "authorized_dimension_scope_policy",
            "policy_type": "scope_policy",
            "action": "refuse",
            "domain_id": DOMAIN_ID,
            "public_rule": "refuse grouping by dimensions outside the metric's allowed_dimensions scope"
            " (derived from manifest join topology; ratio metrics use numerator/denominator scope intersection)",
            "provenance": PROTOCOL_NOTE,
        },
    ]
    profile = {
        "dataset_id": DATASET_ID,
        "default_time_anchor": "",
        "available_time_anchors": [],
        "time_aliases": {},
        "policy_rules": [
            {
                "policy_id": "sql_or_ddl",
                "contains": ["select ", "insert ", "update ", "delete ", "drop ", "truncate ", "alter "],
            }
        ],
        "refusal_policy_provenance": f"{PROTOCOL_NOTE} (frozen protocol.md 2026-07-12): "
        "(r1) undefined-metric via protocol_added_refusal_stub catalog entries; "
        "(r2) SQL/DDL via sql_or_ddl policy rule; "
        "(r3) unauthorized dimension combinations via allowed_dimensions scope from manifest join topology.",
        "source_manifest": "dbt-labs/metricflow metricflow_semantics/test_helpers/semantic_manifest_yamls/simple_manifest"
        " (frozen local copy under v21_external_baseline_runs_20260708/public_artifact/external_runs/metricflow)",
    }

    # ---- write ----
    OUT.mkdir(parents=True, exist_ok=True)

    def dump_jsonl(path, rows):
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n", encoding="utf-8"
        )

    metric_rows = [metrics[n] for n in order]
    dump_jsonl(OUT / "metric_catalog.jsonl", metric_rows)
    dump_jsonl(OUT / "dimension_catalog.jsonl", dim_rows)
    dump_jsonl(OUT / "governance_edges.jsonl", edges)
    dump_jsonl(OUT / "physical_coverage.jsonl", physical)
    dump_jsonl(OUT / "metric_coverage_bindings.jsonl", bindings)
    dump_jsonl(OUT / "policy_catalog.jsonl", policies)
    (OUT / "contract_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    stats = {
        "semantic_models": len(mf.models),
        "measures": len(mf.measures),
        "metrics_total": len(metric_rows),
        "metrics_answerable": sum(1 for r in metric_rows if r["answerable"]),
        "metrics_unanswerable_manifest": sum(
            1 for r in metric_rows if not r["answerable"] and r["source"].startswith("mf_manifest")
        ),
        "protocol_added_refusal_stubs": sum(1 for r in metric_rows if r["source"] == "protocol_added_refusal_stub"),
        "by_metric_type": {},
        "dimensions": len(dim_rows),
        "edges": len(edges),
        "physical_tables": len(physical),
        "coverage_bindings": len(bindings),
    }
    for r in metric_rows:
        key = f"{r['metric_type']}|answerable={r['answerable']}"
        stats["by_metric_type"][key] = stats["by_metric_type"].get(key, 0) + 1
    (OUT / "conversion_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    build()
