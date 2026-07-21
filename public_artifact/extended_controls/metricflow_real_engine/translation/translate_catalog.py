#!/usr/bin/env python3
"""Translate the CaliberGraph public governance catalog (jsonl) into MetricFlow YAML.

Reads metric_catalog.jsonl / dimension_catalog.jsonl / governance_edges.jsonl and emits:
  - ../dbt_project/models/semantic_iowa.yml   (semantic model + metrics)
  - inexpressible.json                        (governance semantics with no MetricFlow home)

Translation rules are pre-registered in ../protocol.md section 3. This script is the auditable
"compiler front-end that consumes the third-party engine format" evidence: everything that CAN be
expressed is emitted mechanically; everything that cannot is logged with the exact catalog payload
that was dropped.
"""

import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RUN_ROOT = HERE.parent
BENCH = (
    RUN_ROOT.parents[2]
    / "public_artifact"
    / "public_benchmark"
    / "iowa_liquor_metric_caliber"
)


def read_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# Fixed mapping: catalog dimension_id -> (MetricFlow dimension name, physical expr)
DIM_EXPR = {
    "county_name": ("county_name", None),
    "store_city": ("store_city", None),
    "store_name": ("store_name", None),
    "category_name": ("category_name", None),
    "vendor_name": ("vendor_name", None),
    "item_desc": ("item_desc", "im_desc"),
}
TIME_DIMS = {"ordered_month": "metric_time__month", "ordered_quarter": "metric_time__quarter"}

# metric_id -> (measure agg, physical expr) for simple metrics
SIMPLE = {
    "sales_dollars": ("sum", "sales_dollars"),
    "bottles_sold": ("sum", "sales_bottles"),
    "liters_sold": ("sum", "sales_liters"),
    "invoice_count": ("count_distinct", "invoice_id"),
    "store_count": ("count_distinct", "store_no"),
    "item_count": ("count_distinct", "item_no"),
}
RATIO = {
    "average_bottle_price": ("sales_dollars", "bottles_sold"),
    "average_invoice_value": ("sales_dollars", "invoice_count"),
}


def main():
    metrics = read_jsonl(BENCH / "metric_catalog.jsonl")
    dims = read_jsonl(BENCH / "dimension_catalog.jsonl")
    edges = read_jsonl(BENCH / "governance_edges.jsonl")

    inexpressible = []

    # --- semantic model ---
    sm_dimensions = [
        {"name": "ordered_on", "type": "time", "type_params": {"time_granularity": "day"}}
    ]
    for d in dims:
        did = d["dimension_id"]
        if did in TIME_DIMS:
            # native: handled by metric_time granularity on ordered_on
            continue
        name, expr = DIM_EXPR[did]
        entry = {"name": name, "type": "categorical"}
        if expr:
            entry["expr"] = expr
        sm_dimensions.append(entry)
        if d.get("parent"):
            inexpressible.append(
                {
                    "family": "granularity_hierarchy",
                    "catalog_object": f"dimension:{did}",
                    "dropped_semantics": {"parent": d["parent"], "grain_rank": d["grain_rank"]},
                    "reason": "MetricFlow has no categorical dimension hierarchy / rolls-up-to / "
                    "finest-grain-resolution construct; granularity exists for time dimensions only.",
                }
            )

    sm_measures = []
    yaml_metrics = []
    for m in metrics:
        mid = m["metric_id"]
        if mid in SIMPLE:
            agg, expr = SIMPLE[mid]
            sm_measures.append({"name": f"m_{mid}", "description": m["description"], "agg": agg, "expr": expr})
            yaml_metrics.append(
                {
                    "name": mid,
                    "label": m["metric_name"],
                    "description": m["description"],
                    "type": "simple",
                    "type_params": {"measure": f"m_{mid}"},
                }
            )
        elif mid in RATIO:
            num, den = RATIO[mid]
            yaml_metrics.append(
                {
                    "name": mid,
                    "label": m["metric_name"],
                    "description": m["description"],
                    "type": "ratio",
                    "type_params": {"numerator": num, "denominator": den},
                }
            )
            if "NULLIF" in (m.get("formula") or ""):
                inexpressible.append(
                    {
                        "family": "formula_guard",
                        "catalog_object": f"metric:{mid}",
                        "dropped_semantics": {"formula": m["formula"]},
                        "reason": "Catalog formula guards zero denominators with NULLIF; MetricFlow "
                        "ratio metrics emit plain division (engine-dependent divide-by-zero behavior).",
                    }
                )
        elif m.get("answerable") is False:
            inexpressible.append(
                {
                    "family": "unsupported_metric_policy",
                    "catalog_object": f"metric:{mid}",
                    "dropped_semantics": {
                        "answerable": False,
                        "description": m["description"],
                        "aliases": m["aliases"],
                        "policy_edge": "governed_by -> unsupported_metric_policy",
                    },
                    "reason": "MetricFlow has no 'declared-but-unanswerable / refuse-with-reason' metric "
                    "construct. Only encoding is omission from the YAML: the engine then returns a generic "
                    "'unknown metric' parse error indistinguishable from a typo, with no policy provenance.",
                }
            )
        else:
            raise SystemExit(f"unhandled metric {mid}")

        # allowed_dimensions (metric x dimension governance) has no MetricFlow field
        if m.get("answerable"):
            all_dims = {d["dimension_id"] for d in dims}
            denied = sorted(all_dims - set(m.get("allowed_dimensions") or []))
            if denied:
                inexpressible.append(
                    {
                        "family": "metric_dimension_reachability",
                        "catalog_object": f"metric:{mid}",
                        "dropped_semantics": {"denied_dimensions": denied},
                        "reason": "Within a semantic model every dimension is queryable with every "
                        "measure; dbt-semantic-interfaces 0.9.0 has no per-metric allowed/denied "
                        "dimension field (see spec_field_inventory.json).",
                    }
                )

    # governance policy edges with no home
    for e in edges:
        if e["edge_type"] == "governed_by" and e["dst"] == "aggregate_only_policy" and e["src"] in {"invoice_id", "store_address"}:
            inexpressible.append(
                {
                    "family": "disclosure_policy",
                    "catalog_object": f"column:{e['src']}",
                    "dropped_semantics": {"policy": "aggregate_only_policy (raw row-level disclosure denied)"},
                    "reason": "No disclosure/aggregate-only policy construct. Encodable only by OMITTING "
                    "the column from the semantic model (enforcement-by-absence): no policy object, no "
                    "audit trail, generic 'not found' error; and omission also removes legitimate "
                    "aggregate uses of the column (e.g. invoice_id as a declarable entity for joins).",
                }
            )

    # families with no catalog row but declared in protocol: coverage window, as-of
    inexpressible.append(
        {
            "family": "physical_coverage",
            "catalog_object": "dataset:iowa_liquor_2024_sample (2024-only, 5000-row public snapshot)",
            "dropped_semantics": {"coverage_window": "2024 calendar year, sampled rows"},
            "reason": "No coverage/completeness declaration in the spec; out-of-coverage time windows "
            "return an empty result with exit code 0 instead of a coverage-based refusal (probe P9).",
        }
    )
    inexpressible.append(
        {
            "family": "as_of_binding",
            "catalog_object": "query-time as-of / valid-time binding",
            "dropped_semantics": {"as_of": "bitemporal as-of anchoring of metric definitions"},
            "reason": "mf query exposes only --start-time/--end-time filters on metric_time; no as-of "
            "flag, no bitemporal construct (probe P8).",
        }
    )
    inexpressible.append(
        {
            "family": "structured_refusal",
            "catalog_object": "refusal contract (machine-readable reason codes)",
            "dropped_semantics": {"refusal_object": "action=refuse with policy reason + provenance"},
            "reason": "All rejections surface as CLI error text from query parsing; there is no "
            "structured refusal object and no reason-code taxonomy.",
        }
    )

    semantic_yaml = {
        "semantic_models": [
            {
                "name": "iowa_liquor_sales",
                "description": "Public Iowa 2024 liquor sales snapshot (5000 rows), grain = invoice line item.",
                "model": "ref('iowa_liquor_sales')",
                "defaults": {"agg_time_dimension": "ordered_on"},
                "entities": [{"name": "sale_line", "type": "primary", "expr": "sale_line_id"}],
                "dimensions": sm_dimensions,
                "measures": sm_measures,
            }
        ],
        "metrics": yaml_metrics,
    }

    out_yaml = RUN_ROOT / "dbt_project" / "models" / "semantic_iowa.yml"
    out_yaml.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# GENERATED by translation/translate_catalog.py from the CaliberGraph public governance\n"
        "# catalog (metric_catalog.jsonl / dimension_catalog.jsonl / governance_edges.jsonl).\n"
        "# Do not edit by hand. Semantics that could not be expressed are in translation/inexpressible.json.\n"
    )
    out_yaml.write_text(header + yaml.safe_dump(semantic_yaml, sort_keys=False, width=100), encoding="utf-8")

    (HERE / "inexpressible.json").write_text(
        json.dumps({"n_items": len(inexpressible), "items": inexpressible}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {out_yaml}")
    print(f"inexpressible items: {len(inexpressible)}")


if __name__ == "__main__":
    main()
