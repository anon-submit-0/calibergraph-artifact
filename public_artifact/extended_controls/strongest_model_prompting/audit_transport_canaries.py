#!/usr/bin/env python3
"""Audit v1 diagnostic exclusion and v2 end-of-contract canary gates."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("h1_ext", HERE / "run_h1_ext.py")
ext = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ext)


def main():
    report = {"models": {}}
    overall = True
    for model in ext.MODELS:
        path = ext.canary_path(model, "multigov")
        rows = ext.h1.read_jsonl(path)
        fname, true_line = ext.canary_true_line("multigov")
        v1 = [row for row in rows if not row.get("canary_version")]
        v2 = [row for row in rows if row.get("canary_version") == "v2_policy_valid_end_anchor"]
        v2_pass = [row for row in v2 if not row.get("error") and ext.canary_pass(row.get("raw_response"), true_line)]
        benchmark_path = HERE / "raw_responses" / f"{ext.safe_model_name(model)}_multigov_raw.jsonl"
        benchmark = ext.h1.read_jsonl(benchmark_path) if benchmark_path.exists() else []
        v2_latest = max((row.get("ts_utc") or "" for row in v2_pass), default="")
        benchmark_earliest = min((row.get("ts_utc") or "" for row in benchmark), default="")
        model_pass = len(v2) == 2 and len(v2_pass) == 2 and (not benchmark or v2_latest <= benchmark_earliest)
        overall = overall and model_pass
        report["models"][model] = {
            "anchor_file": fname,
            "anchor_coverage_id": json.loads(true_line)["coverage_id"],
            "v1_conflicted_quote_diagnostics_excluded": len(v1),
            "v2_calls": len(v2),
            "v2_passes": len(v2_pass),
            "benchmark_calls": len(benchmark),
            "v2_gate_precedes_benchmark": not benchmark or v2_latest <= benchmark_earliest,
            "pass": model_pass,
        }
    report["overall_pass"] = overall
    (HERE / "transport_canary_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
