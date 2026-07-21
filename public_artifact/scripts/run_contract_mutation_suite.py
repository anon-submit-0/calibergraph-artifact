#!/usr/bin/env python3
"""Execute one positive and six counterfactual contract checks on Iowa data."""

from __future__ import annotations

import json
from pathlib import Path

from calibergraph_contract_compiler import ContractCompiler


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public_benchmark" / "iowa_liquor_metric_caliber"
OUT = ROOT / "experiments"


CASES = [
    {
        "case_id": "contract_valid",
        "query": "Average bottle price by category in 2024",
        "metric_id": "average_bottle_price",
        "dimensions": ["category_name"],
        "expected_action": "answer",
        "expected_primary_failure": None,
    },
    {
        "case_id": "contract_field_failure",
        "query": "Unknown governed metric in 2024",
        "metric_id": "not_in_catalog",
        "dimensions": [],
        "expected_action": "refuse",
        "expected_primary_failure": "field",
    },
    {
        "case_id": "contract_caliber_failure",
        "query": "Average bottle price in 2024",
        "metric_id": "average_bottle_price",
        "dimensions": [],
        "metric_patch": {"formula": "SUM(sales_dollars) / 1"},
        "expected_action": "refuse",
        "expected_primary_failure": "caliber",
    },
    {
        "case_id": "contract_grain_failure",
        "query": "Store count by store name in 2024",
        "metric_id": "store_count",
        "dimensions": ["store_name"],
        "expected_action": "refuse",
        "expected_primary_failure": "grain",
    },
    {
        "case_id": "contract_coverage_failure",
        "query": "Average bottle price by category in 2024",
        "metric_id": "average_bottle_price",
        "dimensions": ["category_name"],
        "coverage_remove": ["sales_bottles"],
        "expected_action": "refuse",
        "expected_primary_failure": "coverage",
    },
    {
        "case_id": "contract_time_failure",
        "query": "Sales dollars in 2025",
        "metric_id": "sales_dollars",
        "dimensions": [],
        "time_binding": "2025",
        "expected_action": "refuse",
        "expected_primary_failure": "time",
    },
    {
        "case_id": "contract_policy_failure",
        "query": "Show raw invoice ids in 2024",
        "metric_id": "invoice_count",
        "dimensions": [],
        "expected_action": "refuse",
        "expected_primary_failure": "policy",
    },
]


def main():
    base = ContractCompiler(DATA)
    rows = []
    for case in CASES:
        override = {}
        if case.get("metric_patch"):
            override["metric_patch"] = {case["metric_id"]: case["metric_patch"]}
        compiler = ContractCompiler(DATA, metadata_override=override)
        coverage_override = None
        if case.get("coverage_remove"):
            coverage_override = sorted(base.schema_columns - set(case["coverage_remove"]))
        result = compiler.compile(
            case["query"],
            case["metric_id"],
            requested_dimensions=case["dimensions"],
            candidate_metrics=[case["metric_id"]],
            time_binding=case.get("time_binding"),
            coverage_override=coverage_override,
        )
        primary = (result["trace"].get("certificate") or {}).get("primary_failure")
        passed = result["action"] == case["expected_action"] and primary == case["expected_primary_failure"]
        rows.append(
            {
                "case_id": case["case_id"],
                "expected_action": case["expected_action"],
                "expected_primary_failure": case["expected_primary_failure"],
                "observed_action": result["action"],
                "observed_primary_failure": primary,
                "passed": passed,
                "decision": result,
            }
        )
    payload = {
        "dataset": "IowaLiquor-MetricCaliber",
        "purpose": "executable unit tests for each formal constraint family",
        "case_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "all_passed": all(row["passed"] for row in rows),
        "cases": rows,
    }
    (OUT / "contract_mutation_suite_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Contract Mutation Suite",
        "",
        "The suite mutates one released contract input at a time. It is an implementation test, not an accuracy benchmark.",
        "",
        "| Case | Expected | Observed | Pass |",
        "|---|---|---|---:|",
    ]
    for row in rows:
        expected = row["expected_primary_failure"] or "witness"
        observed = row["observed_primary_failure"] or "witness"
        lines.append(f"| {row['case_id']} | {expected} | {observed} | {str(row['passed']).lower()} |")
    (OUT / "CONTRACT_MUTATION_SUITE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"case_count": len(rows), "passed_count": payload["passed_count"], "all_passed": payload["all_passed"]}))
    if not payload["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
