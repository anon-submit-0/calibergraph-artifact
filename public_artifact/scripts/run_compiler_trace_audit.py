#!/usr/bin/env python3
"""Summarize which formal constraint families are active in each public contract."""

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments"
FILES = {
    "IowaLiquor": ROOT / "public_benchmark/iowa_liquor_metric_caliber/results/iowa_liquor_predictions.jsonl",
    "MultiGov": ROOT / "public_benchmark/multigov_metric_caliber/results/multigov_predictions.jsonl",
    "GovTwin": ROOT / "public_benchmark/govtwin_metric_caliber/results/govtwin_predictions.jsonl",
    "IndustrialCaseText": ROOT
    / "public_benchmark/industrial_case_text_metric_caliber/results/industrial_case_text_predictions.jsonl",
}
FAMILIES = ("field", "caliber", "grain", "coverage", "time", "policy")


def main():
    payload = {"constraint_families": list(FAMILIES), "datasets": {}}
    for name, path in FILES.items():
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = [row for row in rows if row.get("mode") == "caliber_graph"]
        counts = {family: Counter() for family in FAMILIES}
        for row in rows:
            checks = (row.get("trace") or {}).get("checks", {})
            if set(checks) != set(FAMILIES):
                raise AssertionError(f"{name}/{row.get('case_id')} has incomplete checks: {sorted(checks)}")
            for family, check in checks.items():
                counts[family]["active"] += int(check.get("active", False))
                counts[family]["passed"] += int(check.get("active", False) and check.get("passed", False))
                counts[family]["failed"] += int(check.get("active", False) and not check.get("passed", False))
                counts[family]["inactive"] += int(not check.get("active", False))
        payload["datasets"][name] = {
            "n": len(rows),
            "families": {family: dict(counts[family]) for family in FAMILIES},
        }
    (OUT / "compiler_trace_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Compiler Trace Audit",
        "",
        "Active counts are contract-specific. Inactive checks are disclosed rather than recorded as synthetic passes.",
        "",
        "| Dataset | N | Field | Caliber | Grain | Coverage | Time | Policy |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in payload["datasets"].items():
        active = [item["families"][family].get("active", 0) for family in FAMILIES]
        lines.append(f"| {name} | {item['n']} | " + " | ".join(map(str, active)) + " |")
    (OUT / "COMPILER_TRACE_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
