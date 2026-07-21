#!/usr/bin/env python3
"""Run an optional independent LLM adjudication audit for public labels.

This script is intentionally outside the required key-free rebuild path. It
records prompts and model outputs, but never stores keys. The audit asks an
independent LLM to judge whether released gold labels are plausible under the
released catalog and adjudication rules. It is not a replacement for human
business annotation; it is a reviewer-facing sanity check against circular
labeling.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "public_benchmark"
OUT = ROOT / "experiments" / "model_task_validity_audit"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compact_catalog_iowa() -> dict:
    data = BENCH / "iowa_liquor_metric_caliber"
    metrics = read_jsonl(data / "metric_catalog.jsonl")
    dims = read_jsonl(data / "dimension_catalog.jsonl")
    policies = []
    if (data / "policy_catalog.jsonl").exists():
        policies = read_jsonl(data / "policy_catalog.jsonl")
    return {
        "metrics": [
            {"id": m["metric_id"], "name": m.get("metric_name"), "aliases": m.get("aliases", [])[:4], "formula": m.get("formula"), "allowed_dimensions": m.get("allowed_dimensions", [])}
            for m in metrics
        ],
        "dimensions": [
            {"id": d["dimension_id"], "name": d.get("name"), "aliases": d.get("aliases", [])[:4], "parent": d.get("parent", "")}
            for d in dims
        ],
        "policies": policies,
    }


def compact_catalog_ict() -> dict:
    data = BENCH / "industrial_case_text_metric_caliber"
    metrics = read_jsonl(data / "metric_catalog.jsonl")
    dims = read_jsonl(data / "dimension_catalog.jsonl")
    policies = read_jsonl(data / "policy_catalog.jsonl")
    return {
        "metrics": [
            {"id": m["metric_id"], "name": m.get("metric_name"), "aliases": m.get("aliases", [])[:5], "allowed_dimensions": m.get("allowed_dimensions", [])}
            for m in metrics
        ],
        "dimensions": [
            {"id": d["dimension_id"], "name": d.get("name"), "aliases": d.get("aliases", [])[:5], "parent": d.get("parent", "")}
            for d in dims
        ],
        "policies": policies,
    }


def sample_cases() -> list[dict]:
    rows = []
    iowa = BENCH / "iowa_liquor_metric_caliber"
    for case in read_jsonl(iowa / "test_cases.jsonl")[:16]:
        rows.append(
            {
                "dataset": "iowa",
                "case_id": case["case_id"],
                "query": case["nl_query"],
                "gold": {
                    "action": case["expected_action"],
                    "metric_id": case["expected_metric_id"],
                    "dimensions": case["expected_dimensions"],
                },
            }
        )
    ict = BENCH / "industrial_case_text_metric_caliber"
    gold = {g["case_id"]: g for g in read_jsonl(ict / "gold_labels.jsonl")}
    # Deterministic stratified slice: early cases plus known policy and finest-grain cases.
    wanted = [
        "ict_case_0001",
        "ict_case_0002",
        "ict_case_0008",
        "ict_case_0012",
        "ict_case_0020",
        "ict_case_0030",
        "ict_case_0040",
        "ict_case_0050",
        "ict_case_0060",
        "ict_case_0070",
        "ict_case_0080",
        "ict_case_0090",
        "ict_case_0100",
        "ict_case_0110",
    ]
    blind = {c["case_id"]: c for c in read_jsonl(ict / "blind_cases.jsonl")}
    for cid in wanted:
        if cid not in blind or cid not in gold:
            continue
        g = gold[cid]
        rows.append(
            {
                "dataset": "ict",
                "case_id": cid,
                "query": blind[cid]["nl_query"],
                "gold": {
                    "action": g["expected_action"],
                    "metric_id": g["expected_metric_id"],
                    "dimensions": g["expected_dimensions"],
                },
            }
        )
    return rows[:30]


def make_prompt(cases: list[dict]) -> str:
    instructions = {
        "task": "Judge whether each released gold label is plausible under the released catalog and adjudication rules. Do not optimize the paper; act as an independent label adjudicator.",
        "adjudication_rules": [
            "If a query asks multiple levels on one hierarchy path, the governed finest requested level is the expected dimension.",
            "Unsafe SQL/DDL, raw identifiers, private mappings, unsupported metrics, and off-domain requests should be refused.",
            "Dataset policy catalogs may list ambiguous queries that should be refused even when a term is also a metric alias.",
            "A metric label is plausible only if the query meaning matches the metric id/aliases/formula role.",
            "Return ACCEPT if the label is defensible, QUESTION if ambiguous, or REJECT if clearly wrong.",
        ],
        "catalogs": {
            "iowa": compact_catalog_iowa(),
            "ict": compact_catalog_ict(),
        },
        "cases": cases,
        "required_output": {
            "type": "json",
            "schema": [
                {"case_id": "string", "verdict": "ACCEPT|QUESTION|REJECT", "reason": "short"}
            ],
        },
    }
    return json.dumps(instructions, ensure_ascii=False, indent=2)


def parse_json_array(text: str) -> list[dict]:
    text = text.strip()
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        raise ValueError("no JSON array found")
    return json.loads(match.group(0))


def run_model(channel: str, model: str, prompt: str) -> dict:
    hub = Path.home() / ".agents" / "skills" / "llmhub" / "bin" / "llmhub.py"
    cmd = ["python3", str(hub), "chat", "--channel", channel, "--model", model, "--prompt", prompt]
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=240)
    payload = {
        "channel": channel,
        "model": model,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode == 0:
        try:
            payload["parsed"] = parse_json_array(completed.stdout)
        except Exception as exc:  # keep raw output for audit
            payload["parse_error"] = str(exc)
    return payload


def summarize(cases: list[dict], runs: list[dict]) -> dict:
    case_ids = {c["case_id"] for c in cases}
    summary = {}
    for run in runs:
        key = f"{run['channel']}/{run['model']}"
        parsed = run.get("parsed") or []
        verdicts = {p.get("case_id"): p.get("verdict") for p in parsed if p.get("case_id") in case_ids}
        summary[key] = {
            "parsed_cases": len(verdicts),
            "accept": sum(1 for v in verdicts.values() if v == "ACCEPT"),
            "question": sum(1 for v in verdicts.values() if v == "QUESTION"),
            "reject": sum(1 for v in verdicts.values() if v == "REJECT"),
            "accept_rate": sum(1 for v in verdicts.values() if v == "ACCEPT") / max(1, len(verdicts)),
        }
    return summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = sample_cases()
    prompt = make_prompt(cases)
    (OUT / "prompt.json").write_text(prompt + "\n", encoding="utf-8")
    write_json(OUT / "sample_cases.json", cases)

    model_spec = os.environ.get("release_ADJUDICATOR_MODELS", "gpt-provider:gpt-5.5")
    runs = []
    for spec in model_spec.split(","):
        spec = spec.strip()
        if not spec:
            continue
        channel, model = spec.split(":", 1)
        runs.append(run_model(channel, model, prompt))
    write_json(OUT / "raw_model_outputs.json", runs)
    summary = summarize(cases, runs)
    write_json(OUT / "summary.json", {"n_cases": len(cases), "models": summary})

    lines = [
        "# release Independent Label Adjudication Audit",
        "",
        "Optional LLM-based adjudication over released public labels. The adjudicator sees catalogs, adjudication rules, queries, and gold labels, then judges whether each label is defensible. It is not a human business-annotator replacement; it is a reproducible sanity check against obviously self-serving labels.",
        "",
        "| Model | Parsed cases | Accept | Question | Reject | Accept rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for model, s in summary.items():
        lines.append(f"| {model} | {s['parsed_cases']} | {s['accept']} | {s['question']} | {s['reject']} | {s['accept_rate']:.3f} |")
    lines.extend(["", "Raw prompts and model outputs are stored in this folder; no API keys are stored."])
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"n_cases": len(cases), "models": summary}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
