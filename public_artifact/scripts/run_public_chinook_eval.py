#!/usr/bin/env python3
import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public_benchmark"
DATA = PUBLIC / "data"
OUT = PUBLIC / "experiments"
CACHE = OUT / "llm_cache"
LLMHUB = Path(os.environ.get("LLMHUB_CLI", str(Path.home() / ".agents" / "skills" / "llmhub" / "bin" / "llmhub.py")))
ENV_FILE = Path(os.environ.get("LLMHUB_ENV_FILE", str(Path.home() / ".config" / "llm_keys.env")))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def norm(value):
    if value is None:
        return ""
    return str(value).strip()


def split_terms(text):
    text = norm(text).lower()
    return set(re.findall(r"[a-z0-9_]+", text) + re.findall(r"[\u4e00-\u9fff]{2,}", text))


def char_bigrams(text):
    text = re.sub(r"\s+", "", norm(text).lower())
    return {text[i : i + 2] for i in range(max(0, len(text) - 1))}


def text_score(query, fields):
    q = norm(query).lower()
    q_terms = split_terms(q)
    q_bigrams = char_bigrams(q)
    score = 0.0
    for field, weight in fields:
        f = norm(field).lower()
        if not f:
            continue
        if f in q:
            score += 5.0 * weight
        f_terms = split_terms(f)
        score += weight * len(q_terms & f_terms)
        f_bigrams = char_bigrams(f)
        if f_bigrams:
            score += weight * len(q_bigrams & f_bigrams) / math.sqrt(len(f_bigrams))
    return score


def load_public():
    metrics = {m["metric_id"]: m for m in read_jsonl(DATA / "chinook_metric_catalog.jsonl")}
    dims = {d["dimension_id"]: d for d in read_jsonl(DATA / "chinook_dimension_catalog.jsonl")}
    cases = read_jsonl(DATA / "chinook_metric_cases.jsonl")
    for m in metrics.values():
        m["fields"] = [
            (m.get("metric_name"), 3.0),
            (m.get("metric_id"), 2.0),
            (m.get("formula"), 1.5),
            (m.get("description"), 1.0),
            *[(a, 2.5) for a in m.get("aliases", [])],
        ]
    for d in dims.values():
        d["fields"] = [
            (d.get("name"), 3.0),
            (d.get("dimension_id"), 2.0),
            *[(a, 2.5) for a in d.get("aliases", [])],
        ]
    return metrics, dims, cases


def should_refuse(query):
    q = norm(query).lower()
    unsafe = ["select ", "drop ", "delete ", "insert ", "update ", "truncate "]
    pii = ["email", "emails", "phone", "phone numbers", "address", "birthdate", "fax"]
    off_domain = ["weather", "tomorrow weather", "午餐", "天气"]
    unsupported = ["refund", "refunds", "退款"]
    return any(x in q for x in unsafe + pii + off_domain + unsupported)


def rank_metrics(query, metrics, k=5, direct=False):
    scored = []
    for mid, m in metrics.items():
        if m.get("answerable") is False:
            continue
        fields = m["fields"][:2] if direct else m["fields"]
        score = text_score(query, fields)
        scored.append((score, mid))
    scored.sort(reverse=True)
    return [mid for score, mid in scored[:k] if score > 0]


def explicit_dims(query):
    q = norm(query).lower()
    if "monthly" in q:
        return ["month"]
    group_text = ""
    if " by " in q:
        group_text = q.split(" by ", 1)[1]
    elif "按" in q:
        group_text = q.split("按", 1)[1]
    elif "each " in q:
        group_text = q.split("each ", 1)[1]
    elif "每" in q:
        group_text = q.split("每", 1)[1]
    if not group_text:
        return []
    dims = []
    if any(x in group_text for x in ["country and city", "国家和城市", "国家城市"]):
        return ["city"]
    if any(x in group_text for x in ["year and month", "年份和月份", "monthly", "month", "月份", "月"]):
        return ["month"]
    if any(x in group_text for x in ["artist, album, and track", "artist album track", "艺人、专辑和曲目", "playlist and track"]):
        return ["track"]
    if any(x in group_text for x in ["artist and album", "艺人和专辑"]):
        return ["album"]
    if any(x in group_text for x in ["playlist and genre", "playlist, genre", "歌单和流派"]):
        return ["genre"]
    if any(x in group_text for x in ["country", "国家"]):
        dims.append("country")
    if any(x in group_text for x in ["city", "城市"]):
        dims.append("city")
    if any(x in group_text for x in ["support rep", "employee", "sales rep", "销售"]):
        dims.append("support_rep")
    if any(x in group_text for x in ["genre", "流派", "类别"]):
        dims.append("genre")
    if any(x in group_text for x in ["media type", "format", "媒体类型"]):
        dims.append("media_type")
    if any(x in group_text for x in ["playlist", "歌单"]):
        dims.append("playlist")
    if any(x in group_text for x in ["artist", "艺人"]):
        dims.append("artist")
    if any(x in group_text for x in ["album", "专辑"]):
        dims.append("album")
    if any(x in group_text for x in ["track", "song", "曲目"]):
        dims.append("track")
    # keep only finest dimension within same hierarchy
    if "city" in dims:
        dims = [d for d in dims if d != "country"]
    if "month" in dims:
        dims = [d for d in dims if d != "year"]
    if "track" in dims:
        dims = [d for d in dims if d not in {"artist", "album"}]
    elif "album" in dims:
        dims = [d for d in dims if d != "artist"]
    return list(dict.fromkeys(dims))


def predict_scaffold(case, metrics):
    q = case["nl_query"]
    if should_refuse(q):
        return {"action": "refuse", "pred_metric_id": "", "pred_dimensions": [], "reason": "policy_refusal"}
    ranked = rank_metrics(q, metrics, k=1)
    return {
        "action": "answer",
        "pred_metric_id": ranked[0] if ranked else "",
        "pred_dimensions": explicit_dims(q),
        "reason": "coverage_caliber_witness",
    }


def predict_proxy(case, metrics, mode):
    q = case["nl_query"]
    ranked = rank_metrics(q, metrics, k=1, direct=(mode == "direct_keyword"))
    dims = [] if mode == "direct_keyword" else explicit_dims(q)
    return {
        "action": "answer",
        "pred_metric_id": ranked[0] if ranked else "",
        "pred_dimensions": dims,
        "reason": mode,
    }


def metric_line(m):
    return "; ".join(
        [
            f"id={m['metric_id']}",
            f"name={m.get('metric_name','')}",
            f"aliases={', '.join(m.get('aliases', []))}",
            f"formula={m.get('formula','')}",
            f"allowed_dimensions={','.join(m.get('allowed_dimensions', []))}",
            f"desc={m.get('description','')}",
        ]
    )


def dim_line(d):
    return "; ".join(
        [
            f"id={d['dimension_id']}",
            f"name={d.get('name','')}",
            f"aliases={', '.join(d.get('aliases', []))}",
            f"parent={d.get('parent','')}",
            f"grain_rank={d.get('grain_rank','')}",
        ]
    )


def build_context(case, mode, metrics, dims):
    if mode == "llm_direct":
        return {
            "metrics": [metric_line(m) for m in metrics.values()],
            "dimensions": [dim_line(d) for d in dims.values()],
        }
    mids = rank_metrics(case["nl_query"], metrics, k=5)
    context = {
        "retrieved_metrics": [metric_line(metrics[mid]) for mid in mids],
        "retrieved_dimensions": [dim_line(d) for d in dims.values()],
    }
    if mode == "llm_graph_rag":
        context["graph_policy"] = (
            "If multiple hierarchy levels are requested, return only the finest requested grain: "
            "country+city -> city, year+month -> month, artist+album -> album, artist+album+track -> track. "
            "Refuse PII requests, SQL/DDL requests, off-domain requests, and unsupported refund metrics."
        )
        context["metric_allowed_dimensions"] = {
            mid: metrics[mid].get("allowed_dimensions", []) for mid in mids
        }
    return context


def build_prompt(mode, batch, metrics, dims):
    payload = [
        {
            "case_id": c["case_id"],
            "nl_query": c["nl_query"],
            "context": build_context(c, mode, metrics, dims),
        }
        for c in batch
    ]
    return f"""You are evaluating an NL2Metric baseline on the public Chinook-MetricCaliber benchmark.

Mode: {mode}

Return ONLY a JSON array. Each object must use this schema:
{{"case_id":"...", "action":"answer|refuse", "metric_id":"...", "dimensions":["..."], "time_window":"...", "reason":"brief"}}

Rules:
- Use only provided metric ids and dimension ids.
- If action is refuse, metric_id="" and dimensions=[].
- Do not output SQL.
- Do not invent unsupported refund metrics.
- PII requests, SQL/DDL requests, and off-domain weather/lunch/random requests should be refused.
- For hierarchy, output only the finest requested grain.

Cases:
```json
{json.dumps(payload, ensure_ascii=False, indent=2)}
```
"""


def call_llm(prompt, model, max_tokens=3000, timeout=120):
    cmd = ["python3", str(LLMHUB), "chat", "--model", model, "--max-tokens", str(max_tokens), "--timeout", str(timeout)]
    proc = subprocess.run(cmd, input=prompt, text=True, capture_output=True, check=False, timeout=timeout + 30)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def parse_json_array(text):
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        m = re.search(r"\[[\s\S]*\]", cleaned)
        if not m:
            raise
        return json.loads(m.group(0))


def model_slug(model):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model)


def run_llm(mode, cases, metrics, dims, args):
    rows = []
    slug = model_slug(args.model)
    for start in range(0, len(cases), args.batch_size):
        batch = cases[start : start + args.batch_size]
        cache_path = CACHE / f"{slug}_{mode}_{start:04d}_{start+len(batch)-1:04d}.json"
        if cache_path.exists() and not args.refresh:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            out = cached["stdout"]
        else:
            out = call_llm(build_prompt(mode, batch, metrics, dims), args.model, args.max_tokens, args.timeout)
            cache_path.write_text(json.dumps({"mode": mode, "model": args.model, "stdout": out}, ensure_ascii=False, indent=2) + "\n")
        try:
            data = parse_json_array(out)
        except Exception as exc:
            print(f"parse failed {mode} {start}: {exc}", file=sys.stderr)
            data = []
        by_id = {norm(x.get("case_id")): x for x in data if isinstance(x, dict)}
        for case in batch:
            item = by_id.get(case["case_id"], {})
            action = norm(item.get("action")).lower()
            pred_metric = norm(item.get("metric_id"))
            pred_dims = item.get("dimensions") or []
            if not isinstance(pred_dims, list):
                pred_dims = []
            if action == "refuse" or not pred_metric:
                action = "refuse"
                pred_metric = ""
                pred_dims = []
            rows.append(
                {
                    "mode": mode,
                    "model": args.model,
                    **case,
                    "action": action,
                    "pred_metric_id": pred_metric,
                    "pred_dimensions": [norm(d) for d in pred_dims if norm(d)],
                    "reason": norm(item.get("reason")),
                }
            )
        print(f"{mode} {start + len(batch)}/{len(cases)}", flush=True)
    return rows


def score(rows):
    summary = {}
    for mode in sorted({r["mode"] for r in rows}):
        sub = [r for r in rows if r["mode"] == mode]
        c = Counter()
        for r in sub:
            expected_refusal = r["expected_action"] == "refuse"
            refused = r["action"] == "refuse" or not r["pred_metric_id"]
            metric_ok = r["pred_metric_id"] == r["expected_metric_id"]
            dim_ok = set(r["pred_dimensions"]) == set(r["expected_dimensions"])
            if metric_ok:
                c["metric_ok"] += 1
            if dim_ok:
                c["dim_ok"] += 1
            if metric_ok and dim_ok:
                c["joint_ok"] += 1
            if refused and expected_refusal:
                c["refusal_tp"] += 1
            if refused and not expected_refusal:
                c["refusal_fp"] += 1
            if (not refused) and expected_refusal:
                c["refusal_fn"] += 1
            r["metric_ok"] = metric_ok
            r["dimension_exact_ok"] = dim_ok
            r["joint_ok"] = metric_ok and dim_ok
        n = len(sub)
        summary[mode] = {
            "n": n,
            "metric_accuracy": c["metric_ok"] / n,
            "dimension_exact_accuracy": c["dim_ok"] / n,
            "joint_metric_dimension_accuracy": c["joint_ok"] / n,
            "refusal_precision": c["refusal_tp"] / max(1, c["refusal_tp"] + c["refusal_fp"]),
            "refusal_recall": c["refusal_tp"] / max(1, c["refusal_tp"] + c["refusal_fn"]),
        }
    return summary


def write_outputs(rows, summary):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "public_chinook_predictions.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    (OUT / "public_chinook_eval_results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# Public Chinook-MetricCaliber Evaluation",
        "",
        "Cases: 40",
        "",
        "| Mode | Metric Acc. | Dimension Exact | Joint Metric+Dim | Refusal P | Refusal R |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mode, s in summary.items():
        lines.append(
            f"| {mode} | {s['metric_accuracy']:.3f} | {s['dimension_exact_accuracy']:.3f} | {s['joint_metric_dimension_accuracy']:.3f} | {s['refusal_precision']:.3f} | {s['refusal_recall']:.3f} |"
        )
    (OUT / "public_chinook_eval_summary.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("NL2METRIC_MODEL", "deepseek-3.2"))
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--max-tokens", type=int, default=3000)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    load_env_file(ENV_FILE)
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    metrics, dims, cases = load_public()
    rows = []
    for mode in ["direct_keyword", "schema_rag", "public_caliber_graph"]:
        for case in cases:
            if mode == "public_caliber_graph":
                pred = predict_scaffold(case, metrics)
            else:
                pred = predict_proxy(case, metrics, mode)
            rows.append({"mode": mode, "model": "", **case, **pred})
    for mode in ["llm_direct", "llm_schema_rag", "llm_graph_rag"]:
        rows.extend(run_llm(mode, cases, metrics, dims, args))
    summary = score(rows)
    write_outputs(rows, summary)


if __name__ == "__main__":
    main()
