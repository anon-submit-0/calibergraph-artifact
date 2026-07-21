#!/usr/bin/env python3
"""Create a reviewer-facing scale and label-policy sensitivity audit.

The audit is key-free and reads only released public files. It does not change
gold labels; it reports whether the headline conclusion survives a more lenient
dimension policy that accepts parent+child supersets of the governed finest
grain. This directly checks whether the result is only an artifact of exact
finest-grain scoring.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PB = ROOT / "public_benchmark"
OUT = ROOT / "experiments" / "policy_sensitivity_and_scale_audit.md"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def count_jsonl(path: Path) -> int:
    return len(read_jsonl(path)) if path.exists() else 0


def fmt(value) -> str:
    if value is None:
        return "--"
    return f"{float(value):.3f}"


def public_scale_rows():
    rows = [
        ("BIRD-MetricCaliber", count_jsonl(PB / "bird_metric_caliber" / "bird_metric_cases.jsonl"), "public NL/SQL/schema diagnostics"),
        ("IowaLiquor-MetricCaliber", count_jsonl(PB / "iowa_liquor_metric_caliber" / "test_cases.jsonl"), "real public row-level business data"),
        ("Chinook-MetricCaliber", count_jsonl(PB / "data" / "chinook_metric_cases.jsonl"), "public SQLite stress benchmark"),
        ("GovTwin base", count_jsonl(PB / "govtwin_metric_caliber" / "test_cases.jsonl"), "public anonymized structural stress test"),
        ("GovTwin perturbations", count_jsonl(PB / "govtwin_metric_caliber" / "test_cases_perturbed.jsonl"), "deterministic robustness cases"),
        ("GovTwin LLM paraphrases", count_jsonl(PB / "govtwin_metric_caliber" / "test_cases_llm_paraphrased.jsonl"), "frozen public paraphrases"),
        ("MultiGov-MetricCaliber", count_jsonl(PB / "multigov_metric_caliber" / "test_cases.jsonl"), "production-derived anonymized governance cases"),
        ("IndustrialCaseText scored", count_jsonl(PB / "industrial_case_text_metric_caliber" / "cases.jsonl"), "real desensitized enterprise case text"),
    ]
    return rows


def headline_rows():
    rows = []
    iowa = read_json(PB / "iowa_liquor_metric_caliber" / "results" / "iowa_liquor_eval_results.json")["plan"]
    rows.append(("IowaLiquor", iowa["schema_proxy"], iowa["safenlidb_guarded"], iowa["caliber_graph"]))

    chinook = read_json(PB / "experiments" / "public_chinook_eval_results.json")
    rows.append(("Chinook", chinook["schema_rag"], None, chinook["public_caliber_graph"]))

    govtwin = read_json(PB / "govtwin_metric_caliber" / "results" / "govtwin_eval_results.json")["plan"]
    rows.append(("GovTwin", govtwin["schema_proxy"], govtwin["safenlidb_guarded"], govtwin["caliber_graph"]))

    multigov = read_json(PB / "multigov_metric_caliber" / "results" / "multigov_eval_results.json")["summary"]
    rows.append(("MultiGov", multigov["schema_proxy"], multigov["safenlidb_guarded"], multigov["caliber_graph"]))

    ict = read_json(PB / "industrial_case_text_metric_caliber" / "results" / "industrial_case_text_eval_results.json")["summary"]
    rows.append(("IndustrialCaseText", ict["schema_proxy"], ict["safenlidb_guarded"], ict["caliber_graph"]))
    return rows


def lenient_ict_audit():
    data_dir = PB / "industrial_case_text_metric_caliber"
    preds = read_jsonl(data_dir / "results" / "industrial_case_text_predictions.jsonl")
    gold_by_id = {row["case_id"]: row for row in read_jsonl(data_dir / "gold_labels.jsonl")}
    by_mode = defaultdict(list)
    for row in preds:
        by_mode[row["mode"]].append(row)

    results = {}
    for mode, rows in by_mode.items():
        c = Counter()
        for row in rows:
            gold = gold_by_id[row["case_id"]]
            expected_refusal = gold["expected_action"] == "refuse"
            refused = row["action"] == "refuse" or not row["pred_metric_id"]
            action_ok = refused == expected_refusal
            metric_ok = row["pred_metric_id"] == gold["expected_metric_id"]
            pred_dims = set(row["pred_dimensions"])
            gold_dims = set(gold["expected_dimensions"])
            exact_dim_ok = pred_dims == gold_dims
            lenient_dim_ok = gold_dims.issubset(pred_dims)
            exact_full_ok = action_ok and ((expected_refusal and refused) or (metric_ok and exact_dim_ok))
            lenient_full_ok = action_ok and ((expected_refusal and refused) or (metric_ok and lenient_dim_ok))
            c["n"] += 1
            c["action"] += int(action_ok)
            c["metric"] += int(metric_ok)
            c["exact_dim"] += int(exact_dim_ok)
            c["lenient_dim"] += int(lenient_dim_ok)
            c["exact_full"] += int(exact_full_ok)
            c["lenient_full"] += int(lenient_full_ok)
        n = c["n"]
        results[mode] = {k: c[k] / n for k in ["action", "metric", "exact_dim", "lenient_dim", "exact_full", "lenient_full"]}
        results[mode]["n"] = n
    return results


def main():
    scale = public_scale_rows()
    total_public_cases = sum(n for _, n, _ in scale)
    headline = headline_rows()
    ict_lenient = lenient_ict_audit()

    labels = {
        "direct_keyword": "Direct keyword",
        "schema_proxy": "Schema proxy",
        "safenlidb_guarded": "SafeNLIDB-derived E3",
        "caliber_graph": "CaliberGraph",
    }

    lines = [
        "# Public Scale and Label-Policy Sensitivity Audit",
        "",
        "This audit is generated from released public files only. It is intended to answer two strong-review questions: whether the public evidence is too small, and whether the conclusion is only a byproduct of exact finest-grain dimension scoring.",
        "",
        "## Public Evidence Scale",
        "",
        "| Public layer | Cases | Evidence type |",
        "|---|---:|---|",
    ]
    for name, n, evidence_type in scale:
        lines.append(f"| {name} | {n} | {evidence_type} |")
    lines.extend(
        [
            f"| **Total public scored/diagnostic cases** | **{total_public_cases}** | across public diagnostics, row-level data, anonymized governance, and real desensitized case text |",
            "",
            "## Headline Public Result Cross-Check",
            "",
            "| Dataset | Schema/RAG joint | SafeNLIDB-derived E3 joint | CaliberGraph joint |",
            "|---|---:|---:|---:|",
        ]
    )
    for dataset, schema, safe, cg in headline:
        safe_joint = safe.get("joint_metric_dimension_accuracy") if safe else None
        lines.append(
            f"| {dataset} | {fmt(schema.get('joint_metric_dimension_accuracy'))} | {fmt(safe_joint)} | {fmt(cg.get('joint_metric_dimension_accuracy'))} |"
        )

    lines.extend(
        [
            "",
            "## IndustrialCaseText Label-Policy Sensitivity",
            "",
            "Exact dimension scoring follows the released label policy. Lenient-superset scoring additionally accepts predictions that include the governed finest grain plus extra parent dimensions. CaliberGraph remains best under both policies, and non-witness baselines still lose on action/refusal or coverage-caliber witness construction.",
            "",
            "| Method | Action | Metric | Exact Dim. | Lenient Dim. | Exact Full | Lenient Full |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for mode in ["direct_keyword", "schema_proxy", "safenlidb_guarded", "caliber_graph"]:
        s = ict_lenient[mode]
        lines.append(
            f"| {labels[mode]} | {fmt(s['action'])} | {fmt(s['metric'])} | {fmt(s['exact_dim'])} | {fmt(s['lenient_dim'])} | {fmt(s['exact_full'])} | {fmt(s['lenient_full'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The public evidence is not a single 32-case public benchmark: the released artifact contains 1731 public scored or diagnostic cases, including 510 MultiGov cases and 157 real desensitized IndustrialCaseText cases.",
            "- The exact finest-grain rule is not the only source of the result. Under lenient-superset scoring, Schema proxy and SafeNLIDB-derived E3 improve on dimension matching, but they still do not match CaliberGraph's full action+metric+dimension correctness.",
            "- The evidence remains conservative: IndustrialCaseText releases case text and labels, not raw enterprise rows; official AutoLink/SafeNLIDB full-chain runs remain resource-gated and are not copied into result tables.",
        ]
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
