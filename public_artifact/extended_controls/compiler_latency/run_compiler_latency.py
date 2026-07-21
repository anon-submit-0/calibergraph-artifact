#!/usr/bin/env python3
"""Measure deterministic finalization latency using released label-free plans."""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
RELEASE = HERE.parents[2]
PB = RELEASE / "public_artifact" / "public_benchmark"
sys.path.insert(0, str(RELEASE / "public_artifact" / "scripts"))
from calibergraph_contract_compiler import ContractCompiler  # noqa: E402

REPEATS = 20
LAYERS = {
    "iowa": {
        "dir": PB / "iowa_liquor_metric_caliber",
        "pred": "results/iowa_liquor_predictions.jsonl",
    },
    "govtwin": {
        "dir": PB / "govtwin_metric_caliber",
        "pred": "results/govtwin_predictions.jsonl",
    },
    "multigov": {
        "dir": PB / "multigov_metric_caliber",
        "pred": "results/multigov_predictions.jsonl",
    },
    "ict": {
        "dir": PB / "industrial_case_text_metric_caliber",
        "pred": "results/industrial_case_text_predictions.jsonl",
    },
}


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(q * (len(ordered) - 1))))]


def call_spec(row):
    trace = row["trace"]
    checks = trace["checks"]
    metric_id = checks["field"]["metric_id"]
    requested = checks["grain"].get("requested") or []
    detected_time = checks["time"].get("detected")
    return {
        "query": row["nl_query"],
        "metric_id": metric_id,
        "requested_dimensions": requested,
        "candidate_metrics": trace.get("candidate_metrics") or [],
        "time_binding": detected_time,
    }


def main():
    report = {
        "scope": "ContractCompiler finalization after candidate generation; no online LLM",
        "repeats": REPEATS,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
        },
        "layers": {},
    }
    pooled_times = []
    for layer, cfg in LAYERS.items():
        compiler = ContractCompiler(cfg["dir"])
        rows = [row for row in read_jsonl(cfg["dir"] / cfg["pred"]) if row["mode"] == "caliber_graph"]
        specs = [call_spec(row) for row in rows]
        mismatches = []
        for row, spec in zip(rows, specs):
            decision = compiler.compile(**spec)
            if (
                decision["action"] != row["action"]
                or decision["pred_metric_id"] != row["pred_metric_id"]
                or set(decision["pred_dimensions"]) != set(row["pred_dimensions"])
            ):
                mismatches.append(row["case_id"])
        if mismatches:
            raise SystemExit(f"{layer}: compile replay mismatch for {mismatches[:10]}")
        for spec in specs:
            compiler.compile(**spec)
        times_us = []
        started = time.perf_counter_ns()
        for _ in range(REPEATS):
            for spec in specs:
                t0 = time.perf_counter_ns()
                compiler.compile(**spec)
                times_us.append((time.perf_counter_ns() - t0) / 1000.0)
        elapsed_s = (time.perf_counter_ns() - started) / 1e9
        pooled_times.extend(times_us)
        report["layers"][layer] = {
            "n_cases": len(specs),
            "n_timed_calls": len(times_us),
            "replay_mismatches": mismatches,
            "latency_us_median": statistics.median(times_us),
            "latency_us_p95": percentile(times_us, 0.95),
            "latency_us_p99": percentile(times_us, 0.99),
            "latency_us_max": max(times_us),
            "throughput_calls_per_second": len(times_us) / elapsed_s,
        }
    report["pooled"] = {
        "n_timed_calls": len(pooled_times),
        "latency_us_median": statistics.median(pooled_times),
        "latency_us_p95": percentile(pooled_times, 0.95),
        "latency_us_p99": percentile(pooled_times, 0.99),
    }
    (HERE / "compiler_latency_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
