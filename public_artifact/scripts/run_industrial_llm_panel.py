#!/usr/bin/env python3
"""Run requested LLM models on IndustrialCaseText-MetricCaliber.

The panel uses only blind public cases for prediction. Gold labels are loaded
after inference for scoring.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public_benchmark" / "industrial_case_text_metric_caliber"
OUT = DATA / "results" / "llm_model_panel"
CACHE = OUT / "llm_cache"
POLICY = ROOT / "config" / "llm_model_policy.json"
LLMHUB = Path(os.environ.get("LLMHUB_CLI", str(Path.home() / ".agents" / "skills" / "llmhub" / "bin" / "llmhub.py")))
ENV_FILES = [
    Path(os.environ["LLMHUB_ENV_FILE"]) if os.environ.get("LLMHUB_ENV_FILE") else None,
    Path.home() / ".config" / "llm_keys.env",
]


class PartialModelRunError(RuntimeError):
    def __init__(self, message, rows):
        super().__init__(message)
        self.rows = rows


def load_env_files():
    for path in ENV_FILES:
        if path is None:
            continue
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def norm(value):
    return str(value or "").strip()


def split_terms(text):
    text = norm(text).lower()
    return set(re.findall(r"[a-z0-9_]+", text) + re.findall(r"[\u4e00-\u9fff]{2,}", text))


def char_bigrams(text):
    text = re.sub(r"\s+", "", norm(text).lower())
    return {text[i : i + 2] for i in range(max(0, len(text) - 1))}


def score_text(query, fields):
    q = norm(query).lower()
    q_terms = split_terms(q)
    q_bigrams = char_bigrams(q)
    score = 0.0
    for field, weight in fields:
        f = norm(field).lower()
        if not f:
            continue
        if f in q:
            score += 4.0 * weight
        f_terms = split_terms(f)
        score += weight * len(q_terms & f_terms)
        f_bigrams = char_bigrams(f)
        if f_bigrams:
            score += weight * len(q_bigrams & f_bigrams) / math.sqrt(len(f_bigrams))
    return score


def metric_line(metric):
    return "; ".join(
        [
            f"id={metric['metric_id']}",
            f"name={metric.get('metric_name', '')}",
            f"aliases={', '.join(metric.get('aliases', []))}",
            f"domain={metric.get('domain_id', '')}",
        ]
    )


def dim_line(dim):
    return "; ".join(
        [
            f"id={dim['dimension_id']}",
            f"name={dim.get('name', '')}",
            f"aliases={', '.join(dim.get('aliases', []))}",
            f"parent={dim.get('parent', '')}",
            f"grain_rank={dim.get('grain_rank', '')}",
        ]
    )


def rank_metrics(query, metrics, k=6):
    scored = []
    for metric in metrics:
        fields = [(metric.get("metric_name"), 3.0), (metric.get("metric_id"), 0.5)]
        fields.extend((alias, 2.5) for alias in metric.get("aliases", []))
        scored.append((score_text(query, fields), metric))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [metric for score, metric in scored[:k] if score > 0]


def build_context(case, mode, metrics, dims):
    if mode == "llm_direct":
        return {
            "metrics": [metric_line(m) for m in metrics],
            "dimensions": [dim_line(d) for d in dims],
        }
    ranked = rank_metrics(case["nl_query"], metrics, k=6)
    context = {
        "retrieved_metrics": [metric_line(m) for m in ranked],
        "candidate_dimensions": [dim_line(d) for d in dims],
    }
    if mode == "llm_graph_rag":
        context["typed_policy"] = (
            "Refuse raw SQL/catalog dumps, off-domain requests, PII requests, and requests with no governed metric. "
            "If multiple segment hierarchy levels are requested, output only the finest requested grain: segment_l3 over segment_l2 over segment_l1. "
            "Use only provided metric_id and dimension_id values."
        )
    return context


def build_prompt(mode, batch, metrics, dims):
    payload = [
        {
            "case_id": case["case_id"],
            "nl_query": case["nl_query"],
            "query_family": case.get("query_family", ""),
            "context": build_context(case, mode, metrics, dims),
        }
        for case in batch
    ]
    return f"""You are evaluating an NL2Metric-Caliber system on a public anonymized industrial benchmark.

Mode: {mode}

Return ONLY a JSON array. Each object must use this schema:
{{"case_id":"...", "action":"answer|refuse", "metric_id":"...", "dimensions":["..."], "reason":"brief"}}

Rules:
- Use only provided metric_id and dimension_id values.
- If action is refuse, metric_id="" and dimensions=[].
- Do not output SQL.
- Do not use labels that are not present in the context.
- For hierarchy, output only the finest requested grain.

Cases:
```json
{json.dumps(payload, ensure_ascii=False, indent=2)}
```
"""


def model_slug(channel, model):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{channel}__{model}")


def call_llm(prompt, channel, model, max_tokens, timeout):
    cmd = [
        "python3",
        str(LLMHUB),
        "chat",
        "--channel",
        channel,
        "--model",
        model,
        "--max-tokens",
        str(max_tokens),
        "--timeout",
        str(timeout),
    ]
    proc = subprocess.run(cmd, input=prompt, text=True, capture_output=True, check=False, timeout=timeout + 30)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:800])
    return proc.stdout.strip()


def parse_json_array(text):
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if not match:
            raise
        return json.loads(match.group(0))


def select_cases(cases, limit):
    if not limit or limit >= len(cases):
        return cases
    refusals = [case for case in cases if case.get("query_family") == "policy_refusal"]
    answers = [case for case in cases if case.get("query_family") != "policy_refusal"]
    keep = refusals[: min(len(refusals), max(5, limit // 5))]
    keep_ids = {case["case_id"] for case in keep}
    for case in answers:
        if len(keep) >= limit:
            break
        if case["case_id"] not in keep_ids:
            keep.append(case)
            keep_ids.add(case["case_id"])
    return keep[:limit]


def run_model_mode(entry, mode, cases, metrics, dims, args):
    channel = entry["channel"]
    model = entry["model"]
    slug = model_slug(channel, model)
    rows = []
    for start in range(0, len(cases), args.batch_size):
        batch = cases[start : start + args.batch_size]
        cache_path = CACHE / f"{slug}_{mode}_{start:04d}_{start+len(batch)-1:04d}.json"
        try:
            if cache_path.exists() and not args.refresh:
                out = json.loads(cache_path.read_text(encoding="utf-8"))["stdout"]
            else:
                out = call_llm(build_prompt(mode, batch, metrics, dims), channel, model, args.max_tokens, args.timeout)
                cache_path.write_text(
                    json.dumps({"channel": channel, "model": model, "mode": mode, "stdout": out}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            parsed = parse_json_array(out)
        except Exception as exc:
            raise PartialModelRunError(f"{type(exc).__name__}: {exc}", rows) from exc
        by_id = {norm(row.get("case_id")): row for row in parsed if isinstance(row, dict)}
        for case in batch:
            item = by_id.get(case["case_id"], {})
            dims_out = item.get("dimensions") or []
            if not isinstance(dims_out, list):
                dims_out = []
            rows.append(
                {
                    "channel": channel,
                    "model": model,
                    "mode": mode,
                    **case,
                    "pred_action": norm(item.get("action") or "answer").lower(),
                    "pred_metric_id": norm(item.get("metric_id")),
                    "pred_dimensions": [norm(d) for d in dims_out if norm(d)],
                    "reason": norm(item.get("reason")),
                }
            )
        print(f"{channel}/{model} {mode} {start + len(batch)}/{len(cases)}", flush=True)
    return rows


def score(rows, gold_by_id):
    summary = {}
    for key in sorted({(row["channel"], row["model"], row["mode"]) for row in rows}):
        channel, model, mode = key
        subset = [row for row in rows if (row["channel"], row["model"], row["mode"]) == key]
        c = Counter()
        for row in subset:
            gold = gold_by_id[row["case_id"]]
            exp_refuse = gold["expected_action"] == "refuse"
            pred_refuse = row["pred_action"] == "refuse" or not row["pred_metric_id"]
            action_ok = pred_refuse == exp_refuse
            metric_ok = row["pred_metric_id"] == gold["expected_metric_id"]
            dim_ok = set(row["pred_dimensions"]) == set(gold["expected_dimensions"])
            c["action_ok"] += int(action_ok)
            c["metric_ok"] += int((exp_refuse and pred_refuse) or ((not exp_refuse) and metric_ok))
            c["dim_ok"] += int(exp_refuse or dim_ok)
            c["full_ok"] += int(action_ok and (exp_refuse or (metric_ok and dim_ok)))
            c["tp"] += int(pred_refuse and exp_refuse)
            c["fp"] += int(pred_refuse and not exp_refuse)
            c["fn"] += int((not pred_refuse) and exp_refuse)
        n = len(subset)
        summary[f"{channel}/{model}/{mode}"] = {
            "channel": channel,
            "model": model,
            "mode": mode,
            "n": n,
            "action_accuracy": c["action_ok"] / n,
            "metric_accuracy_with_refusal": c["metric_ok"] / n,
            "dimension_accuracy_with_refusal": c["dim_ok"] / n,
            "full_case_accuracy": c["full_ok"] / n,
            "refusal_precision": c["tp"] / max(1, c["tp"] + c["fp"]),
            "refusal_recall": c["tp"] / max(1, c["tp"] + c["fn"]),
        }
    return summary


def write_summary(summary, failures):
    lines = [
        "# IndustrialCaseText LLM Model Panel",
        "",
        "Predictions use `blind_cases.jsonl`; `gold_labels.jsonl` is used only for scoring.",
        "",
        "| Channel | Model | Mode | N | Full Acc. | Action Acc. | Metric Acc. | Dim. Acc. | Ref.P | Ref.R | Status |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key, item in summary.items():
        status = "ok"
        failure = failures.get(key)
        if failure:
            status = failure[:120].replace("|", "/")
        lines.append(
            f"| {item['channel']} | {item['model']} | {item['mode']} | {item['n']} | {item['full_case_accuracy']:.3f} | {item['action_accuracy']:.3f} | {item['metric_accuracy_with_refusal']:.3f} | {item['dimension_accuracy_with_refusal']:.3f} | {item['refusal_precision']:.3f} | {item['refusal_recall']:.3f} | {status} |"
        )
    for key, failure in failures.items():
        if key not in summary:
            channel, model, mode = key.split("/", 2)
            lines.append(f"| {channel} | {model} | {mode} | 0 |  |  |  |  |  |  | {failure[:120].replace('|', '/')} |")
    (OUT / "industrial_llm_model_panel_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="0 means all released cases")
    parser.add_argument("--modes", default="llm_graph_rag")
    parser.add_argument("--models", default="", help="comma-separated model ids; empty means all policy models")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--max-tokens", type=int, default=5000)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--merge-existing", action="store_true")
    args = parser.parse_args()

    load_env_files()
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    requested = {m.strip() for m in args.models.split(",") if m.strip()}
    models = [entry for entry in policy["models"] if not requested or entry["model"] in requested]
    modes = [mode.strip() for mode in args.modes.split(",") if mode.strip()]
    metrics = read_jsonl(DATA / "metric_catalog.jsonl")
    dims = read_jsonl(DATA / "dimension_catalog.jsonl")
    cases = select_cases(read_jsonl(DATA / "blind_cases.jsonl"), args.limit)
    gold_by_id = {row["case_id"]: row for row in read_jsonl(DATA / "gold_labels.jsonl")}
    selected_keys = {(entry["channel"], entry["model"], mode) for entry in models for mode in modes}
    existing_result_path = OUT / "industrial_llm_model_panel_results.json"
    existing_prediction_path = OUT / "industrial_llm_model_panel_predictions.jsonl"
    all_rows = []
    failures = {}
    if args.merge_existing and existing_prediction_path.exists():
        all_rows = [
            row
            for row in read_jsonl(existing_prediction_path)
            if (row["channel"], row["model"], row["mode"]) not in selected_keys
        ]
        if existing_result_path.exists():
            previous = json.loads(existing_result_path.read_text(encoding="utf-8"))
            failures = {
                key: value
                for key, value in previous.get("failures", {}).items()
                if tuple(key.split("/", 2)) not in selected_keys
            }
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for entry in models:
        for mode in modes:
            key = f"{entry['channel']}/{entry['model']}/{mode}"
            try:
                all_rows.extend(run_model_mode(entry, mode, cases, metrics, dims, args))
            except PartialModelRunError as exc:
                all_rows.extend(exc.rows)
                failures[key] = f"partial_n={len(exc.rows)}; {str(exc)[:460]}"
                print(f"FAILED {key}: {failures[key]}", flush=True)
            except Exception as exc:
                failures[key] = f"{type(exc).__name__}: {str(exc)[:500]}"
                print(f"FAILED {key}: {failures[key]}", flush=True)
    summary = score(all_rows, gold_by_id) if all_rows else {}
    payload = {
        "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "policy_models": policy["models"],
        "modes": modes,
        "case_count": len(cases),
        "prediction_input": "blind_cases.jsonl",
        "scoring_input": "gold_labels.jsonl",
        "gold_field_leaks_in_predictions": sum(
            any(k.startswith("expected_") or k.endswith("_hash") for k in row) for row in all_rows
        ),
        "summary": summary,
        "failures": failures,
    }
    write_jsonl(OUT / "industrial_llm_model_panel_predictions.jsonl", all_rows)
    write_json(OUT / "industrial_llm_model_panel_results.json", payload)
    write_summary(summary, failures)
    print(json.dumps({"summary": summary, "failures": failures}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
