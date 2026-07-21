#!/usr/bin/env python3
"""Write the release external benchmark/baseline alignment audit.

The audit is deterministic and uses no network access. It records which recent
public benchmarks and systems are direct baselines, mechanism controls, or
diagnostics for NL2Metric-Caliber. release keeps this historical release audit but
adds executed adjacent evidence in `EXTERNAL_EVIDENCE_SUMMARY.md`.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments"


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "release",
        "date": "2026-07-08",
        "claim_boundary": (
            "This historical release audit maps adjacent BI, reliability, and Text-to-SQL "
            "benchmarks to the MetricCaliberBench evidence boundary. release supplements "
            "it with executed Spider2-DBT, TrustSQL raw, DataBench, and MetricFlow "
            "evidence in EXTERNAL_EVIDENCE_SUMMARY.md."
        ),
        "benchmark_candidates": [
            {
                "name": "BIS",
                "source": "arXiv:2410.22925",
                "role": "external BI NL2SQL benchmark alignment",
                "why_relevant": "production BI questions rather than generic academic SQL only",
                "why_not_primary_yet": "does not directly release CaliberGraph-style metric-contract witness labels",
                "paper_action": "discuss as closest external BI benchmark; use release DataBench/Spider2-DBT evidence as executed adjacent anchors",
            },
            {
                "name": "BI-Bench",
                "source": "ACL Industry Track 2025, doi:10.18653/v1/2025.acl-industry.90",
                "role": "end-to-end BI-system benchmark alignment",
                "why_relevant": "descriptive, diagnostic, predictive, and prescriptive BI query coverage",
                "why_not_primary_yet": "benchmarks BI system insight quality rather than typed metric-caliber witness conformance",
                "paper_action": "use to position the BI system boundary and motivate broader evaluation",
            },
            {
                "name": "TrustSQL",
                "source": "arXiv:2403.15879",
                "role": "answerability/refusal reliability baseline family",
                "why_relevant": "scores feasible SQL generation and infeasible-question abstention",
                "why_not_primary_yet": "refusal is one contract facet; it lacks denominator, grain, coverage, and metric-caliber witnesses",
                "paper_action": "add as refusal/reliability comparison axis; release includes raw official scorer outputs",
            },
            {
                "name": "Spider 2.0 / Spider2-Lite",
                "source": "arXiv:2411.07763",
                "role": "enterprise-scale schema/workflow diagnostic",
                "why_relevant": "real-world enterprise workflows over large schemas and warehouses",
                "why_not_primary_yet": "schema/workflow success does not define governed metric contracts or disclosure policy",
                "paper_action": "retain as Text-to-SQL diagnostic, not the main metric-caliber benchmark",
            },
            {
                "name": "BIRD",
                "source": "bird-bench.github.io",
                "role": "existing SQL diagnostic already included",
                "why_relevant": "public SQL benchmark with aggregate queries and external knowledge",
                "why_not_primary_yet": "does not provide complete governance graph, refusal policy, or coverage contract",
                "paper_action": "keep BIRD-MetricCaliber as plan-level diagnostic",
            },
        ],
        "baseline_candidates": [
            {
                "name": "AutoLink",
                "role": "candidate-availability and schema-linking control",
                "directness": "adjacent closest published family, not direct metric-caliber compiler",
                "release_action": "report evidence-labeled E3 candidate-linking diagnostics and resource-gated upstream audit",
            },
            {
                "name": "SafeNLIDB",
                "role": "security/refusal guard control",
                "directness": "adjacent safety system, not denominator/grain witness compiler",
                "release_action": "report ShieldSQL guard transfer and resource-gated upstream audit",
            },
            {
                "name": "TrustSQL-style abstention",
                "role": "public answerability/reliability control",
                "directness": "direct for refusal policy, partial for metric-caliber",
                "release_action": "map as refusal baseline family; release includes TrustSQL raw official scorer outputs",
            },
            {
                "name": "CHESS / MAC-SQL / DIN-SQL",
                "role": "strong NL2SQL agent baselines",
                "directness": "strong SQL baselines, indirect for governed metric contracts",
                "release_action": "rank as next SQL-planner controls with oracle-candidate finalizer interface",
            },
            {
                "name": "Semantic-layer validator / SQL post-hoc validator",
                "role": "fully runnable non-witness controls",
                "directness": "direct mechanism controls under released contracts",
                "release_action": "keep as primary reproducible non-witness comparisons",
            },
        ],
        "release_decision": [
            "Numerical result tables remain limited to released/rebuildable MetricCaliberBench splits and evidence-labeled controls.",
            "External benchmarks are cited and mapped to specific evaluation roles, avoiding false SOTA claims.",
            "release executes adjacent checks for Spider2-DBT, TrustSQL raw, DataBench, and dbt MetricFlow; those checks remain boundary evidence, not full NL2Metric-Caliber witness benchmarks.",
        ],
        "sources": [
            "https://arxiv.org/abs/2410.22925",
            "https://aclanthology.org/2025.acl-industry.90/",
            "https://arxiv.org/abs/2403.15879",
            "https://arxiv.org/abs/2411.07763",
            "https://bird-bench.github.io/",
            "https://ojs.aaai.org/index.php/AAAI/article/view/40672",
            "https://ojs.aaai.org/index.php/AAAI/article/view/40484",
        ],
    }

    (OUT / "external_benchmark_baseline_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    bench_rows = [
        [
            item["name"],
            item["role"],
            item["why_relevant"],
            item["why_not_primary_yet"],
            item["paper_action"],
        ]
        for item in payload["benchmark_candidates"]
    ]
    baseline_rows = [
        [
            item["name"],
            item["role"],
            item["directness"],
            item["release_action"],
        ]
        for item in payload["baseline_candidates"]
    ]
    lines = [
        "# release External Benchmark and Baseline Alignment Audit",
        "",
        payload["claim_boundary"],
        "",
        "## Benchmark Triage",
        "",
        md_table(
            ["Benchmark", "Role", "Why relevant", "Why not primary evidence yet", "release paper action"],
            bench_rows,
        ),
        "",
        "## Baseline Triage",
        "",
        md_table(["Baseline family", "Role", "Directness", "release action"], baseline_rows),
        "",
        "## Decision for the Submission Text",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["release_decision"])
    lines.extend(["", "## Source URLs", ""])
    lines.extend(f"- {url}" for url in payload["sources"])
    lines.append("")
    (OUT / "EXTERNAL_BENCHMARK_BASELINE_AUDIT.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    print(json.dumps({"written": ["EXTERNAL_BENCHMARK_BASELINE_AUDIT.md", "external_benchmark_baseline_audit.json"]}, indent=2))


if __name__ == "__main__":
    main()
