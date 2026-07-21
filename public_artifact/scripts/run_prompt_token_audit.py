#!/usr/bin/env python3
"""Compute reproducible serialized-prompt token counts for ICT baselines."""

from __future__ import annotations

import json
import math
from pathlib import Path

import tiktoken

import run_industrial_llm_panel as panel


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public_benchmark" / "industrial_case_text_metric_caliber"
OUT = ROOT / "experiments"


def percentile(values, q):
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def describe(values):
    return {
        "n": len(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "max": max(values),
    }


def main():
    encoding_name = "cl100k_base"
    encoder = tiktoken.get_encoding(encoding_name)
    cases = panel.read_jsonl(DATA / "blind_cases.jsonl")
    metrics = panel.read_jsonl(DATA / "metric_catalog.jsonl")
    dims = panel.read_jsonl(DATA / "dimension_catalog.jsonl")
    modes = ["llm_direct", "llm_schema_rag", "llm_graph_rag"]
    result = {}
    for mode in modes:
        single = [len(encoder.encode(panel.build_prompt(mode, [case], metrics, dims))) for case in cases]
        batch_amortized = []
        for start in range(0, len(cases), 10):
            batch = cases[start : start + 10]
            tokens = len(encoder.encode(panel.build_prompt(mode, batch, metrics, dims)))
            batch_amortized.extend([tokens / len(batch)] * len(batch))
        result[mode] = {
            "single_case_serialization": describe(single),
            "batch10_amortized_prompt_tokens": describe(batch_amortized),
        }
    payload = {
        "tokenizer": encoding_name,
        "tokenizer_version": tiktoken.__version__,
        "scope": "input prompt only; no completion or hidden reasoning tokens",
        "prediction_input": "industrial_case_text_metric_caliber/blind_cases.jsonl",
        "case_count": len(cases),
        "batch_size": 10,
        "results": result,
    }
    (OUT / "prompt_token_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Prompt Token Audit",
        "",
        "Counts use `cl100k_base` over the released serialized input prompts. They exclude completions and hidden reasoning tokens.",
        "",
        "| Mode | Single mean | Single p95 | Batch-10 amortized mean | Batch-10 p95 |",
        "|---|---:|---:|---:|---:|",
    ]
    for mode in modes:
        one = result[mode]["single_case_serialization"]
        batched = result[mode]["batch10_amortized_prompt_tokens"]
        lines.append(f"| {mode} | {one['mean']:.1f} | {one['p95']:.1f} | {batched['mean']:.1f} | {batched['p95']:.1f} |")
    (OUT / "PROMPT_TOKEN_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
