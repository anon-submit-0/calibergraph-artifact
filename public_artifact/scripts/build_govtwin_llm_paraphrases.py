#!/usr/bin/env python3
"""Build an LLM-paraphrased GovTwin split.

The generated split is public and synthetic. The LLM is only used to rewrite
already-public GovTwin queries while preserving synthetic anchor phrases needed
for deterministic metric-caliber evaluation.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public_benchmark" / "govtwin_metric_caliber"
OUT = DATA / "test_cases_llm_paraphrased.jsonl"
META = DATA / "results" / "govtwin_llm_paraphrase_metadata.json"
LLMHUB = Path(os.environ.get("LLMHUB_CLI", str(Path.home() / ".agents" / "skills" / "llmhub" / "bin" / "llmhub.py")))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dim_anchor(dim_ids):
    dim_ids = list(dim_ids or [])
    if "segment_l3" in dim_ids:
        return "segment level 1, segment level 2, and segment level 3"
    if "segment_l2" in dim_ids:
        return "segment level 1 and segment level 2"
    if "segment_l1" in dim_ids:
        return "segment level 1"
    if "issue_type" in dim_ids:
        return "issue type"
    if "market_region" in dim_ids:
        return "market region"
    return ""


def refusal_anchor(query):
    q = query.lower()
    for anchor in [
        "SELECT",
        "delete",
        "personal contact",
        "weather",
        "unsupported experimental margin",
    ]:
        if anchor.lower() in q:
            return anchor
    return "unsupported"


def case_payload(cases, metrics):
    payload = []
    for case in cases:
        if case["expected_action"] == "answer":
            metric = metrics[case["expected_metric_id"]]
            anchor = (metric.get("aliases") or [metric["metric_id"]])[0]
            payload.append(
                {
                    "case_id": case["case_id"],
                    "action": "answer",
                    "original": case["nl_query"],
                    "metric_anchor": anchor,
                    "dimension_anchor": dim_anchor(case.get("expected_dimensions", [])),
                    "time_anchor": "last month" if case.get("expected_time_window") == "last_month" else "current reporting period",
                }
            )
        else:
            payload.append(
                {
                    "case_id": case["case_id"],
                    "action": "refuse",
                    "original": case["nl_query"],
                    "refusal_anchor": refusal_anchor(case["nl_query"]),
                }
            )
    return payload


def build_prompt(batch):
    return f"""You are creating a public synthetic benchmark split.

Rewrite each GovTwin query into one natural English paraphrase.

Rules:
- Return ONLY a JSON array.
- Each object must be {{"case_id":"...", "paraphrase":"..."}}.
- Do not add real company, product, person, email, phone, table, column, or private identifiers.
- For answer cases, keep the metric_anchor phrase exactly once.
- If dimension_anchor is non-empty, keep that dimension_anchor phrase exactly once.
- Keep the time_anchor phrase exactly once.
- For refusal cases, keep the refusal_anchor phrase exactly once while changing the surrounding wording.
- Keep the paraphrase concise and analytics-like.

Cases:
```json
{json.dumps(batch, ensure_ascii=False, indent=2)}
```
"""


def parse_json_array(text):
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\[[\s\S]*\]", cleaned)
    if match:
        cleaned = match.group(0)
    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("LLM output is not a JSON array")
    return data


def call_llm(prompt, args):
    cmd = [
        "python3",
        str(LLMHUB),
        "chat",
        "--best",
        "--max-tokens",
        str(args.max_tokens),
        "--timeout",
        str(args.timeout),
    ]
    proc = subprocess.run(cmd, input=prompt, text=True, capture_output=True, check=False, timeout=args.timeout + 30)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout


def fallback_paraphrase(item):
    if item["action"] == "refuse":
        return f"before any report is prepared, handle this restricted request containing {item['refusal_anchor']}"
    dim = item.get("dimension_anchor") or ""
    if dim:
        return f"for {item['time_anchor']}, provide {item['metric_anchor']} broken down by {dim}"
    return f"for {item['time_anchor']}, provide {item['metric_anchor']} with no extra grouping"


def validate_or_fallback(item, text):
    paraphrase = " ".join(str(text or "").split())
    if not paraphrase:
        return fallback_paraphrase(item), "empty_fallback"
    lower = paraphrase.lower()
    required = []
    if item["action"] == "answer":
        required.extend([item["metric_anchor"], item["time_anchor"]])
        if item.get("dimension_anchor"):
            required.append(item["dimension_anchor"])
    else:
        required.append(item["refusal_anchor"])
    missing = [anchor for anchor in required if anchor.lower() not in lower]
    if missing:
        return fallback_paraphrase(item), "missing_anchor_fallback:" + ",".join(missing)
    return paraphrase, "llm"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=5000)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--reuse", action="store_true", help="Do not call the LLM if the split already exists.")
    args = parser.parse_args()

    if args.reuse and OUT.exists():
        print(f"reusing {OUT}")
        return

    metrics = {m["metric_id"]: m for m in read_jsonl(DATA / "metric_catalog.jsonl")}
    cases = read_jsonl(DATA / "test_cases.jsonl")
    payload = case_payload(cases, metrics)
    paraphrases = {}
    model_headers = []
    failures = []
    for start in range(0, len(payload), args.batch_size):
        batch = payload[start : start + args.batch_size]
        raw = call_llm(build_prompt(batch), args)
        first = raw.splitlines()[0] if raw.strip() else ""
        if re.match(r"^\[[^\]]+\|\s*prompt=", first):
            model_headers.append(first.strip())
            raw = "\n".join(raw.splitlines()[1:])
        elif first.startswith("[") is False and "|" in first:
            model_headers.append(first.strip())
            raw = "\n".join(raw.splitlines()[1:])
        try:
            data = parse_json_array(raw)
        except Exception as exc:
            failures.append({"batch_start": start, "error": f"{type(exc).__name__}: {exc}"})
            data = []
        by_id = {str(item.get("case_id")): item for item in data if isinstance(item, dict)}
        for item in batch:
            row = by_id.get(item["case_id"], {})
            paraphrases[item["case_id"]] = row.get("paraphrase", "")
        print(f"LLM paraphrase {min(start + args.batch_size, len(payload))}/{len(payload)}", flush=True)

    rows = []
    fallback_counts = {}
    for case, item in zip(cases, payload):
        paraphrase, source = validate_or_fallback(item, paraphrases.get(case["case_id"]))
        fallback_counts[source] = fallback_counts.get(source, 0) + 1
        row = dict(case)
        row["case_id"] = f"{case['case_id']}_llm_para"
        row["source_case_id"] = case["case_id"]
        row["nl_query"] = paraphrase
        row["perturbation_type"] = "llm_paraphrase"
        row["llm_paraphrase_source"] = source
        rows.append(row)

    write_jsonl(OUT, rows)
    write_json(
        META,
        {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "llmhub_headers": model_headers,
            "cases": len(rows),
            "fallback_counts": fallback_counts,
            "parse_failures": failures,
            "threat_model_note": "Only public synthetic GovTwin queries were sent to the LLM; no private data or private mapping is included.",
        },
    )
    print(json.dumps({"output": str(OUT), "metadata": str(META), "cases": len(rows), "fallback_counts": fallback_counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
