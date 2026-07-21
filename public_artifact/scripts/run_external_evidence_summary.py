#!/usr/bin/env python3
"""Summarize release executed external evidence from released compact artifacts.

The heavy external sources are intentionally not bundled in the submission zip.
This script verifies the compact, reviewer-facing evidence files that were
generated from fixed upstream commits and public downloads.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    spider = read_json(OUT / "spider2_dbt_parse_audit.json")
    trust = read_json(OUT / "trustsql_raw_official_eval" / "trustsql_raw_official_eval.json")
    databench = read_json(OUT / "databench_subset_eval" / "databench_subset_eval.json")
    metricflow = read_json(OUT / "metricflow_validator_control" / "metricflow_validator_control.json")
    lightrag = read_json(OUT / "lightrag_preflight" / "lightrag_preflight.json")

    payload = {
        "version": "release",
        "date": "2026-07-09",
        "claim_boundary": (
            "release reports executed external evidence for Spider2-DBT, TrustSQL raw, "
            "DataBench, and dbt MetricFlow. LightRAG is reported as a runnable "
            "preflight only because a fair numeric baseline requires frozen LLM, "
            "embedding, and query-policy services."
        ),
        "spider2_dbt": {
            "source": spider["source"],
            "commit": spider["commit"],
            "projects": spider["n_projects"],
            "parse_pass": spider["parse_pass"],
            "parse_fail": spider["parse_fail"],
            "yaml_files": spider["total_yaml_files"],
            "sql_files": spider["total_sql_files"],
            "model_entries": spider["total_model_entries"],
            "metric_like_columns": spider["total_metric_like_columns"],
        },
        "trustsql_raw": {
            "source": trust["source"],
            "commit": trust["commit"],
            "datasets": sorted({row["dataset"] for row in trust["results"]}),
            "modes": sorted({row["mode"] for row in trust["results"]}),
            "results": trust["results"],
        },
        "databench_subset": {
            "source": databench["source"],
            "datasets": databench["datasets"],
            "qa_cases": databench["total_qa_cases"],
            "table_rows": databench["total_table_rows"],
        },
        "metricflow_validator": {
            "tool": metricflow["tool"],
            "mf_version": metricflow["mf_version"],
            "returncode": metricflow["returncode"],
        },
        "lightrag_preflight": {
            "source": lightrag["source"],
            "commit": lightrag["commit"],
            "python": lightrag["python"],
            "runtime_status": lightrag["runtime_status"],
            "insert_custom_kg_status": lightrag.get("insert_custom_kg_status"),
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "external_evidence_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    trust_rows = [
        [
            row["dataset"],
            row["mode"],
            str(row["returncode"]),
            str(row.get("RS(0)_total", "")),
            str(row.get("RS(10)_total", "")),
        ]
        for row in trust["results"]
    ]

    lines = [
        "# release External Evidence Summary",
        "",
        payload["claim_boundary"],
        "",
        "## Executed Evidence",
        "",
        f"- Spider2-DBT: {spider['n_projects']} projects; "
        f"{spider['parse_pass']} parse-pass / {spider['parse_fail']} parse-fail; "
        f"{spider['total_yaml_files']} YAML; {spider['total_sql_files']} SQL; "
        f"{spider['total_model_entries']} model entries.",
        f"- DataBench subset: {databench['datasets']} public tables; "
        f"{databench['total_qa_cases']} QA cases; {databench['total_table_rows']} table rows.",
        f"- dbt MetricFlow: `{metricflow['mf_version']}`; return code {metricflow['returncode']}.",
        f"- LightRAG preflight: runtime {lightrag['runtime_status']}; "
        f"custom KG insert {lightrag.get('insert_custom_kg_status')}.",
        "",
        "## TrustSQL Raw Official Scoring",
        "",
        "| Dataset | Mode | Return | RS(0) total | RS(10) total |",
        "|---|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {dataset} | {mode} | {ret} | {rs0} | {rs10} |"
        for dataset, mode, ret, rs0, rs10 in trust_rows
    )
    lines.append("")
    (OUT / "EXTERNAL_EVIDENCE_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"written": ["EXTERNAL_EVIDENCE_SUMMARY.md", "external_evidence_summary.json"]}, indent=2))


if __name__ == "__main__":
    main()
