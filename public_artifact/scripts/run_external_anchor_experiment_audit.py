#!/usr/bin/env python3
"""Build the release external-anchor experiment audit.

This deterministic audit uses only files released in the public artifact. It
turns the baseline-selection review into a reviewer-facing evidence table:
which external anchors are already present and countable, which baselines are
runnable controls, and which adjacent systems are N/A-by-design for particular
metric-caliber failure families. release keeps this historical release audit but adds
executed adjacent evidence in `EXTERNAL_EVIDENCE_SUMMARY.md`.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments"
BENCH = ROOT / "public_benchmark"
BASELINES = ROOT / "external_baselines"


FAMILIES = [
    "metric identity",
    "aggregate caliber",
    "dimension grain",
    "temporal/coverage",
    "refusal/disclosure",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def count_json_records(path: Path) -> int:
    obj = read_json(path)
    if isinstance(obj, dict):
        return len(obj)
    if isinstance(obj, list):
        return len(obj)
    raise TypeError(f"unsupported JSON root in {path}")


def optional_jsonl_count(path: Path) -> int | None:
    if not path.exists():
        return None
    return len(read_jsonl(path))


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def case_family_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        family = (
            row.get("query_family")
            or row.get("failure_family")
            or row.get("case_family")
            or row.get("expected_caliber")
            or row.get("expected_action")
            or "unspecified"
        )
        counter[str(family)] += 1
    return dict(sorted(counter.items()))


def capability_matrix() -> list[dict[str, str]]:
    return [
        {
            "baseline": "AutoLink-derived E3",
            "role": "closest schema/candidate-linking family",
            "metric identity": "mechanism-present candidate recall",
            "aggregate caliber": "N/A-by-design after candidate discovery",
            "dimension grain": "N/A-by-design finest-grain policy absent",
            "temporal/coverage": "N/A-by-design coverage witness absent",
            "refusal/disclosure": "N/A-by-design policy witness absent",
            "release evidence": "fixed AutoLink snapshot plus 547 Spider2-Lite records; MetricCaliber candidate diagnostics",
        },
        {
            "baseline": "SafeNLIDB-derived E3 guard",
            "role": "closest safety/refusal family",
            "metric identity": "N/A-by-design",
            "aggregate caliber": "N/A-by-design",
            "dimension grain": "N/A-by-design",
            "temporal/coverage": "N/A-by-design",
            "refusal/disclosure": "mechanism-present but insufficient for metric caliber",
            "release evidence": "fixed SafeNLIDB snapshot plus 540 ShieldSQL records; refusal-transfer diagnostics",
        },
        {
            "baseline": "Oracle-candidate prompting",
            "role": "perfect-linking stress control",
            "metric identity": "oracle supplied",
            "aggregate caliber": "empirical prompt finalization",
            "dimension grain": "empirical prompt finalization",
            "temporal/coverage": "empirical prompt finalization",
            "refusal/disclosure": "empirical prompt finalization",
            "release evidence": "released MetricCaliberBench scorer outputs",
        },
        {
            "baseline": "LLM Schema-RAG / GraphRAG prompt controls",
            "role": "rules-in-context control",
            "metric identity": "mechanism-present retrieval",
            "aggregate caliber": "mechanism-present but no witness",
            "dimension grain": "mechanism-present but no finest-grain resolver",
            "temporal/coverage": "mechanism-present but no coverage proof",
            "refusal/disclosure": "partial policy visibility",
            "release evidence": "released public predictions and mechanism audit",
        },
        {
            "baseline": "Semantic-layer validator",
            "role": "metrics-as-code style validation control",
            "metric identity": "mechanism-present",
            "aggregate caliber": "mechanism-present validation only",
            "dimension grain": "mechanism-present validation only",
            "temporal/coverage": "partial coverage validation",
            "refusal/disclosure": "partial policy validation",
            "release evidence": "fully runnable key-free mechanism audit",
        },
        {
            "baseline": "SQL post-hoc validator",
            "role": "static/execution validation control",
            "metric identity": "N/A-by-design",
            "aggregate caliber": "partial SQL-shape validation",
            "dimension grain": "partial SQL-shape validation",
            "temporal/coverage": "partial physical-coverage validation",
            "refusal/disclosure": "N/A-by-design unless policy encoded",
            "release evidence": "fully runnable key-free mechanism audit",
        },
        {
            "baseline": "Open SQL end-to-end",
            "role": "executable SQL agent control",
            "metric identity": "empirical SQL planning",
            "aggregate caliber": "empirical SQL planning",
            "dimension grain": "empirical SQL planning",
            "temporal/coverage": "empirical SQL planning",
            "refusal/disclosure": "implicit/weak refusal",
            "release evidence": "IowaLiquor SQLite execution plus MetricCaliber scoring",
        },
        {
            "baseline": "TrustSQL/SecureSQL-style abstention",
            "role": "public abstention and safety anchor",
            "metric identity": "N/A-by-design",
            "aggregate caliber": "N/A-by-design",
            "dimension grain": "N/A-by-design",
            "temporal/coverage": "physical feasibility only",
            "refusal/disclosure": "direct refusal/disclosure anchor",
            "release evidence": "TrustSQL mapped in audit; SafeNLIDB ShieldSQL files countable in artifact",
        },
        {
            "baseline": "dbt MetricFlow validator",
            "role": "third-party semantic-layer validator control",
            "metric identity": "mechanism-present in release MetricFlow validator control",
            "aggregate caliber": "direct metric expression validation",
            "dimension grain": "limited by dbt semantic manifest",
            "temporal/coverage": "limited time-spine/as-of support",
            "refusal/disclosure": "N/A-by-design",
            "release evidence": "release adds dbt MetricFlow validation and Spider2-DBT dbt-parse audit; not a Spider-Agent leaderboard claim",
        },
        {
            "baseline": "LightRAG governed-KG control",
            "role": "graph-in-prompt preflight control",
            "metric identity": "mechanism-present retrieval",
            "aggregate caliber": "rules retrieved, not certified",
            "dimension grain": "rules retrieved, not certified",
            "temporal/coverage": "rules retrieved, not certified",
            "refusal/disclosure": "rules retrieved, not certified",
            "release evidence": "release adds runnable LightRAG custom-KG preflight; no accuracy table because LLM/embedding/query policy are not frozen",
        },
        {
            "baseline": "CaliberGraph",
            "role": "typed witness compiler",
            "metric identity": "compiled witness",
            "aggregate caliber": "compiled witness",
            "dimension grain": "compiled finest-grain witness",
            "temporal/coverage": "compiled coverage/as-of witness",
            "refusal/disclosure": "compiled refusal/disclosure witness",
            "release evidence": "released scorer outputs, ablations, certificates, and audits",
        },
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    anchor_paths = {
        "AutoLink Spider2-Lite records": BASELINES / "AutoLink" / "run" / "spider2_data.json",
        "SafeNLIDB ShieldSQL records": BASELINES / "SAFENLIDB" / "evaluate" / "ShieldSQL" / "RS++" / "test++.json",
        "BIRD-MetricCaliber diagnostic cases": BENCH / "bird_metric_caliber" / "bird_metric_cases.jsonl",
        "Chinook-MetricCaliber scored cases": BENCH / "data" / "chinook_metric_cases.jsonl",
        "IowaLiquor-MetricCaliber scored cases": BENCH / "iowa_liquor_metric_caliber" / "test_cases.jsonl",
        "GovTwin-MetricCaliber base cases": BENCH / "govtwin_metric_caliber" / "test_cases.jsonl",
        "GovTwin-MetricCaliber LLM paraphrase cases": BENCH / "govtwin_metric_caliber" / "test_cases_llm_paraphrased.jsonl",
        "GovTwin-MetricCaliber perturbation cases": BENCH / "govtwin_metric_caliber" / "test_cases_perturbed.jsonl",
        "MultiGov-MetricCaliber scored cases": BENCH / "multigov_metric_caliber" / "gold_labels.jsonl",
        "IndustrialCaseText scored cases": BENCH / "industrial_case_text_metric_caliber" / "gold_labels.jsonl",
    }

    anchors: list[dict[str, Any]] = []
    for name, path in anchor_paths.items():
        if not path.exists():
            anchors.append({"name": name, "path": path.relative_to(ROOT).as_posix(), "status": "missing", "count": 0})
            continue
        count = count_json_records(path) if path.suffix == ".json" else optional_jsonl_count(path)
        anchors.append(
            {
                "name": name,
                "path": path.relative_to(ROOT).as_posix(),
                "status": "present",
                "count": int(count or 0),
            }
        )

    public_scored = sum(
        item["count"]
        for item in anchors
        if item["name"]
        in {
            "Chinook-MetricCaliber scored cases",
            "IowaLiquor-MetricCaliber scored cases",
            "GovTwin-MetricCaliber base cases",
            "GovTwin-MetricCaliber LLM paraphrase cases",
            "GovTwin-MetricCaliber perturbation cases",
            "MultiGov-MetricCaliber scored cases",
            "IndustrialCaseText scored cases",
        }
    )
    public_diagnostic = sum(
        item["count"]
        for item in anchors
        if item["name"]
        in {
            "BIRD-MetricCaliber diagnostic cases",
            "AutoLink Spider2-Lite records",
            "SafeNLIDB ShieldSQL records",
        }
    )

    family_summaries = {
        "iowa": case_family_counts(read_jsonl(BENCH / "iowa_liquor_metric_caliber" / "test_cases.jsonl")),
        "industrial_case_text": case_family_counts(read_jsonl(BENCH / "industrial_case_text_metric_caliber" / "gold_labels.jsonl")),
        "multigov": case_family_counts(read_jsonl(BENCH / "multigov_metric_caliber" / "gold_labels.jsonl")),
    }

    matrix = capability_matrix()
    payload = {
        "version": "release",
        "date": "2026-07-08",
        "claim_boundary": (
            "This historical release audit upgrades external alignment from prose-only triage to key-free "
            "anchor auditing. Counts are computed from released files. release supplements it with "
            "executed Spider2-DBT, TrustSQL raw, DataBench, dbt MetricFlow, and LightRAG-preflight "
            "evidence summarized in EXTERNAL_EVIDENCE_SUMMARY.md."
        ),
        "external_anchors": anchors,
        "public_scored_metric_caliber_cases": public_scored,
        "external_diagnostic_or_official_subtask_records": public_diagnostic,
        "family_summaries": family_summaries,
        "baseline_capability_matrix": matrix,
        "release_executed_adjacent_evidence": [
            "Spider2-DBT dbt-parse audit over public projects.",
            "TrustSQL raw official scorer outputs for answerability/refusal controls.",
            "DataBench fixed public subset audit.",
            "dbt MetricFlow validator control.",
            "LightRAG custom-KG preflight, explicitly excluded from main accuracy tables.",
        ],
    }

    (OUT / "external_anchor_experiment_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    anchor_rows = [
        [item["name"], str(item["count"]), item["status"], item["path"]]
        for item in anchors
    ]
    matrix_rows = [
        [
            row["baseline"],
            row["role"],
            row["metric identity"],
            row["aggregate caliber"],
            row["dimension grain"],
            row["temporal/coverage"],
            row["refusal/disclosure"],
            row["release evidence"],
        ]
        for row in matrix
    ]
    family_rows = []
    for dataset, counts in family_summaries.items():
        for family, n in counts.items():
            family_rows.append([dataset, family, str(n)])

    lines = [
        "# release External Anchor Experiment Audit",
        "",
        payload["claim_boundary"],
        "",
        "## Released Anchor Counts",
        "",
        md_table(["Anchor", "N", "Status", "Released path"], anchor_rows),
        "",
        f"- Public scored MetricCaliber cases counted here: {public_scored}.",
        f"- External diagnostic or official-subtask records counted here: {public_diagnostic}.",
        "",
        "## Failure-Family Surface in Released Public Splits",
        "",
        md_table(["Dataset", "Family/action key", "N"], family_rows),
        "",
        "## Baseline Capability Matrix",
        "",
        md_table(
            [
                "Baseline",
                "Role",
                FAMILIES[0],
                FAMILIES[1],
                FAMILIES[2],
                FAMILIES[3],
                FAMILIES[4],
                "release evidence",
            ],
            matrix_rows,
        ),
        "",
        "## Reviewer-Facing Consequence",
        "",
        "- AutoLink and SafeNLIDB are no longer treated as vague named baselines: the artifact exposes their fixed snapshots, included official records, and which failure families are outside their design scope.",
        "- The paper's numerical tables remain limited to released scorer outputs; release reports adjacent executed evidence separately from full NL2Metric-Caliber witness scoring.",
        "- This audit supports the main mechanism claim: after candidate or safety mechanisms are available, aggregate caliber, finest-grain policy, coverage/as-of binding, and governed refusal still require a typed witness.",
        "",
        "## release Executed Adjacent Evidence",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["release_executed_adjacent_evidence"])
    lines.append("")
    (OUT / "EXTERNAL_ANCHOR_EXPERIMENT_AUDIT.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "written": [
                    "EXTERNAL_ANCHOR_EXPERIMENT_AUDIT.md",
                    "external_anchor_experiment_audit.json",
                ],
                "public_scored_metric_caliber_cases": public_scored,
                "external_diagnostic_or_official_subtask_records": public_diagnostic,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
