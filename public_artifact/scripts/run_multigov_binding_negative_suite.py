#!/usr/bin/env python3
"""Exercise metric-specific MultiGov dependency and coverage isolation.

The suite keeps same-domain evidence for other metrics in place while removing
one binding for the selected metric. It therefore detects domain-level fallback
and empty-required-set passes that a generic mutation fixture cannot expose.
"""

from __future__ import annotations

import json
from pathlib import Path

from calibergraph_contract_compiler import ContractCompiler


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public_benchmark" / "multigov_metric_caliber"
OUT_JSON = ROOT / "experiments" / "multigov_metric_binding_negative_suite.json"
OUT_MD = ROOT / "experiments" / "MULTIGOV_METRIC_BINDING_NEGATIVE_SUITE.md"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run():
    metrics = read_jsonl(DATA / "metric_catalog.jsonl")
    edges = read_jsonl(DATA / "governance_edges.jsonl")
    bindings = read_jsonl(DATA / "metric_coverage_bindings.jsonl")
    cases = read_jsonl(DATA / "test_cases.jsonl")

    metric = next(
        row
        for row in metrics
        if row.get("scoped_ratio")
        and row.get("numerator_nodes")
        and row.get("denominator_nodes")
        and row.get("coverage_nodes")
    )
    metric_id = metric["metric_id"]
    domain_id = metric["domain_id"]
    case = next(
        row
        for row in cases
        if row.get("expected_metric_id") == metric_id and row.get("expected_action") == "answer"
    )
    query = case["nl_query"]
    dims = case["expected_dimensions"]

    other_numerator_edges = [
        row
        for row in edges
        if row.get("domain_id") == domain_id
        and row.get("edge_type") == "numerator_of"
        and row.get("metric_id") != metric_id
    ]
    other_denominator_edges = [
        row
        for row in edges
        if row.get("domain_id") == domain_id
        and row.get("edge_type") == "denominator_of"
        and row.get("metric_id") != metric_id
    ]
    other_bindings = [
        row
        for row in bindings
        if row.get("domain_id") == domain_id and row.get("metric_id") != metric_id
    ]
    if not other_numerator_edges or not other_denominator_edges or not other_bindings:
        raise AssertionError("selected fixture lacks same-domain evidence from other metrics")

    mutations = [
        ("valid_metric_specific_witness", None, None),
        (
            "remove_current_numerator_edge",
            [
                row
                for row in edges
                if not (row.get("metric_id") == metric_id and row.get("edge_type") == "numerator_of")
            ],
            None,
        ),
        (
            "remove_current_denominator_edge",
            [
                row
                for row in edges
                if not (row.get("metric_id") == metric_id and row.get("edge_type") == "denominator_of")
            ],
            None,
        ),
        (
            "remove_current_numerator_coverage_binding",
            None,
            [
                row
                for row in bindings
                if not (
                    row.get("metric_id") == metric_id
                    and row.get("dependency_node_id") in metric["numerator_nodes"]
                )
            ],
        ),
        (
            "remove_current_denominator_coverage_binding",
            None,
            [
                row
                for row in bindings
                if not (
                    row.get("metric_id") == metric_id
                    and row.get("dependency_node_id") in metric["denominator_nodes"]
                )
            ],
        ),
    ]
    expected = {
        "valid_metric_specific_witness": None,
        "remove_current_numerator_edge": "caliber",
        "remove_current_denominator_edge": "caliber",
        "remove_current_numerator_coverage_binding": "coverage",
        "remove_current_denominator_coverage_binding": "coverage",
    }
    rows = []
    for name, edge_override, binding_override in mutations:
        override = {}
        if edge_override is not None:
            override["edges"] = edge_override
        if binding_override is not None:
            override["metric_coverage_bindings"] = binding_override
        result = ContractCompiler(DATA, metadata_override=override or None).compile(
            query,
            metric_id,
            requested_dimensions=dims,
        )
        observed = (result.get("trace", {}).get("certificate") or {}).get("primary_failure")
        row = {
            "mutation": name,
            "expected_primary_failure": expected[name],
            "observed_primary_failure": observed,
            "action": result["action"],
            "passed": observed == expected[name],
        }
        rows.append(row)

    payload = {
        "fixture_metric_id": metric_id,
        "fixture_domain_id": domain_id,
        "same_domain_other_metric_evidence_retained": {
            "numerator_edges": len(other_numerator_edges),
            "denominator_edges": len(other_denominator_edges),
            "coverage_bindings": len(other_bindings),
        },
        "case_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "all_passed": all(row["passed"] for row in rows),
        "results": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# MultiGov Metric-Specific Binding Negative Suite",
        "",
        "Same-domain dependency edges and coverage bindings from other metrics remain present in every negative case.",
        "",
        "| Mutation | Expected failure | Observed failure | Passed |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['mutation']} | {row['expected_primary_failure'] or 'none'} | "
            f"{row['observed_primary_failure'] or 'none'} | {str(row['passed']).lower()} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"case_count": payload["case_count"], "passed_count": payload["passed_count"], "all_passed": payload["all_passed"]}))


if __name__ == "__main__":
    run()
