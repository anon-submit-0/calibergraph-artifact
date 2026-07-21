#!/usr/bin/env python3
"""Build release mechanism-evidence audits from released public artifacts.

The audit deliberately uses only released public files. It adds two fair
mechanism baselines that address reviewer concerns without claiming official
AutoLink/SafeNLIDB reproduction:

* semantic_layer_validator: policy-aware catalog validation over the retrieved
  candidate plan, but no finest-grain witness repair.
* posthoc_answerability_validator: validates a retrieved/SQL plan and refuses
  invalid plans, but does not re-plan to a repaired answer.

Both baselines are scored with the same released gold files as other public
methods and are meant to isolate whether the gain is merely "having rules" or
requires constructing a witness.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "public_benchmark"
OUT = ROOT / "experiments"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def score_rows(rows: list[dict], gold_by_id: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for mode in sorted({row["mode"] for row in rows}):
        subset = [row for row in rows if row["mode"] == mode]
        c = Counter()
        by_family = defaultdict(Counter)
        for row in subset:
            gold = gold_by_id[row["case_id"]]
            expected_refusal = gold["expected_action"] == "refuse"
            refused = row.get("action") == "refuse" or not row.get("pred_metric_id")
            metric_ok = row.get("pred_metric_id", "") == gold.get("expected_metric_id", "")
            dim_ok = set(row.get("pred_dimensions", [])) == set(gold.get("expected_dimensions", []))
            joint_ok = metric_ok and dim_ok and (not expected_refusal)
            action_ok = refused == expected_refusal
            family = gold.get("query_family") or row.get("query_family") or infer_family(row, gold)
            c["metric"] += int(metric_ok)
            c["dim"] += int(dim_ok)
            c["joint"] += int(metric_ok and dim_ok)
            c["action"] += int(action_ok)
            c["tp"] += int(refused and expected_refusal)
            c["fp"] += int(refused and not expected_refusal)
            c["fn"] += int((not refused) and expected_refusal)
            by_family[family]["n"] += 1
            by_family[family]["joint"] += int(metric_ok and dim_ok)
            by_family[family]["action"] += int(action_ok)
        n = len(subset)
        out[mode] = {
            "n": n,
            "metric_accuracy": c["metric"] / n,
            "dimension_exact_accuracy": c["dim"] / n,
            "joint_metric_dimension_accuracy": c["joint"] / n,
            "action_accuracy": c["action"] / n,
            "refusal_precision": c["tp"] / max(1, c["tp"] + c["fp"]),
            "refusal_recall": c["tp"] / max(1, c["tp"] + c["fn"]),
            "family": {
                fam: {
                    "n": cnt["n"],
                    "joint": cnt["joint"] / cnt["n"],
                    "action": cnt["action"] / cnt["n"],
                }
                for fam, cnt in sorted(by_family.items())
            },
        }
    return out


def infer_family(row: dict, gold: dict) -> str:
    query = str(row.get("nl_query", "")).lower()
    if gold.get("expected_action") == "refuse":
        if any(t in query for t in ["raw", "identifier", "select ", "delete ", "drop "]):
            return "policy_refusal"
        return "unsupported_or_refusal"
    pred_dims = set(row.get("pred_dimensions", []))
    gold_dims = set(gold.get("expected_dimensions", []))
    if gold_dims and gold_dims.issubset(pred_dims) and pred_dims != gold_dims:
        return "hierarchy_overexpansion"
    if row.get("pred_metric_id") != gold.get("expected_metric_id"):
        return "metric_identity"
    return "other"


def hierarchy_parent_map(edges_or_dims: list[dict]) -> dict[str, str]:
    parent = {}
    for row in edges_or_dims:
        if row.get("edge_type") == "rolls_up_to":
            parent[row["src"]] = row["dst"]
        elif row.get("parent"):
            parent[row["dimension_id"]] = row["parent"]
    return parent


def has_hierarchy_conflict(dim_ids: list[str], parent: dict[str, str]) -> bool:
    dim_set = set(dim_ids)
    for dim in dim_ids:
        cur = parent.get(dim, "")
        while cur:
            if cur in dim_set:
                return True
            cur = parent.get(cur, "")
    return False


def public_policy_refusal(dataset: str, query: str, pred_metric_id: str = "") -> bool:
    q = str(query or "").lower()
    common = ["select ", "drop ", "delete ", "insert ", "update ", "truncate "]
    if any(t in q for t in common):
        return True
    if dataset == "iowa":
        return (
            pred_metric_id == "profit_margin"
            or any(t in q for t in ["profit margin", "gross margin", "margin", "invoice id", "raw invoice", "store address", "phone", "customer", "weather"])
        )
    if dataset == "ict":
        return any(t in q for t in ["退款金额", "明细", "原始", "raw", "private", "identifier", "sql"])
    if dataset == "multigov":
        return any(t in q for t in ["raw row", "identifier", "private-to-public", "private mapping", "hidden", "customer contact"])
    return False


def transform_baselines(dataset: str, base_rows: list[dict], gold_by_id: dict[str, dict], parent: dict[str, str]) -> list[dict]:
    transformed = []
    for row in base_rows:
        if row["mode"] not in {"schema_proxy", "open_sql_end_to_end", "autolink_iterative"}:
            continue
        if dataset == "iowa" and row["mode"] != "open_sql_end_to_end":
            continue
        if dataset in {"ict", "multigov"} and row["mode"] != "schema_proxy":
            continue
        policy_refuse = public_policy_refusal(dataset, row.get("nl_query", ""), row.get("pred_metric_id", ""))
        hierarchy_conflict = has_hierarchy_conflict(row.get("pred_dimensions", []), parent)
        for mode in ["semantic_layer_validator", "posthoc_answerability_validator"]:
            new = {
                k: v
                for k, v in row.items()
                if k
                not in {
                    "mode",
                    "metric_ok",
                    "dimension_exact_ok",
                    "joint_ok",
                    "refusal_tp",
                    "refusal_fp",
                    "refusal_fn",
                }
            }
            new["mode"] = mode
            new["source_mode"] = row["mode"]
            if policy_refuse:
                new.update({"action": "refuse", "pred_metric_id": "", "pred_dimensions": [], "reason": f"{mode}_policy_refusal"})
            elif mode == "posthoc_answerability_validator" and hierarchy_conflict:
                new.update({"action": "refuse", "pred_metric_id": "", "pred_dimensions": [], "reason": "posthoc_hierarchy_conflict_no_replan"})
            else:
                new["reason"] = f"{mode}_accepted_candidate"
            transformed.append(new)
    return transformed


def load_dataset(name: str) -> tuple[list[dict], dict[str, dict], dict[str, str]]:
    if name == "iowa":
        data = BENCH / "iowa_liquor_metric_caliber"
        predictions = read_jsonl(data / "results" / "iowa_liquor_predictions.jsonl")
        gold = {
            row["case_id"]: {
                "case_id": row["case_id"],
                "expected_action": row["expected_action"],
                "expected_metric_id": row["expected_metric_id"],
                "expected_dimensions": row["expected_dimensions"],
                "query_family": infer_family(row, row),
            }
            for row in read_jsonl(data / "test_cases.jsonl")
        }
        parent = hierarchy_parent_map(read_jsonl(data / "governance_edges.jsonl"))
        return predictions, gold, parent
    if name == "ict":
        data = BENCH / "industrial_case_text_metric_caliber"
        predictions = read_jsonl(data / "results" / "industrial_case_text_predictions.jsonl")
        gold = {row["case_id"]: row for row in read_jsonl(data / "gold_labels.jsonl")}
        dims = read_jsonl(data / "dimension_catalog.jsonl")
        return predictions, gold, hierarchy_parent_map(dims)
    if name == "multigov":
        data = BENCH / "multigov_metric_caliber"
        predictions = read_jsonl(data / "results" / "multigov_predictions.jsonl")
        gold = {row["case_id"]: row for row in read_jsonl(data / "gold_labels.jsonl")}
        parent = hierarchy_parent_map(read_jsonl(data / "governance_edges.jsonl"))
        return predictions, gold, parent
    raise ValueError(name)


def residual_after_candidate(rows: list[dict], gold_by_id: dict[str, dict], candidate_modes: list[str]) -> dict:
    out = {}
    for mode in candidate_modes:
        subset = [r for r in rows if r["mode"] == mode and gold_by_id[r["case_id"]]["expected_action"] == "answer"]
        if not subset:
            continue
        c = Counter()
        for row in subset:
            gold = gold_by_id[row["case_id"]]
            pred_dims = set(row.get("pred_dimensions", []))
            gold_dims = set(gold.get("expected_dimensions", []))
            metric_hit = row.get("pred_metric_id") == gold.get("expected_metric_id")
            dim_recall = gold_dims.issubset(pred_dims) if gold_dims else True
            final_joint = metric_hit and pred_dims == gold_dims
            c["metric_hit"] += int(metric_hit)
            c["dim_recall"] += int(dim_recall)
            c["candidate_available"] += int(metric_hit and dim_recall)
            c["residual_fail"] += int(metric_hit and dim_recall and not final_joint)
            if metric_hit and dim_recall and not final_joint:
                fam = infer_family(row, gold)
                c[f"residual_{fam}"] += 1
        n = len(subset)
        out[mode] = {
            "n_answerable": n,
            "metric_hit": c["metric_hit"] / n,
            "dimension_recall": c["dim_recall"] / n,
            "candidate_available": c["candidate_available"] / n,
            "residual_failure_given_candidate": c["residual_fail"] / max(1, c["candidate_available"]),
            "residual_counts": {
                k.replace("residual_", ""): v
                for k, v in c.items()
                if k.startswith("residual_") and k != "residual_fail"
            },
        }
    return out


def collect_failure_certificates(dataset: str, rows: list[dict], gold_by_id: dict[str, dict], limit: int = 8) -> list[dict]:
    selected = []
    by_case_mode = {(row["case_id"], row["mode"]): row for row in rows}
    preferred = ["schema_proxy", "open_sql_end_to_end", "autolink_iterative", "safenlidb_guarded", "oracle_candidate_prompt"]
    for case_id, gold in gold_by_id.items():
        cg = by_case_mode.get((case_id, "caliber_graph"))
        if not cg:
            continue
        for mode in preferred:
            row = by_case_mode.get((case_id, mode))
            if not row:
                continue
            pred_dims = set(row.get("pred_dimensions", []))
            gold_dims = set(gold.get("expected_dimensions", []))
            refused = row.get("action") == "refuse" or not row.get("pred_metric_id")
            expected_refusal = gold.get("expected_action") == "refuse"
            if row.get("pred_metric_id") == gold.get("expected_metric_id") and pred_dims == gold_dims and refused == expected_refusal:
                continue
            missing = []
            if expected_refusal and not refused:
                missing.append("policy_refusal_certificate")
            if gold_dims.issubset(pred_dims) and pred_dims != gold_dims:
                missing.append("finest_grain_certificate")
            if row.get("pred_metric_id") != gold.get("expected_metric_id"):
                missing.append("metric_identity_certificate")
            if not missing:
                missing.append("coverage_caliber_certificate")
            selected.append(
                {
                    "dataset": dataset,
                    "case_id": case_id,
                    "query": row.get("nl_query", ""),
                    "gold": {
                        "action": gold.get("expected_action"),
                        "metric_id": gold.get("expected_metric_id"),
                        "dimensions": gold.get("expected_dimensions"),
                    },
                    "baseline": {
                        "mode": mode,
                        "action": row.get("action"),
                        "metric_id": row.get("pred_metric_id"),
                        "dimensions": row.get("pred_dimensions", []),
                    },
                    "missing_witness": missing,
                    "caliber_graph": {
                        "action": cg.get("action"),
                        "metric_id": cg.get("pred_metric_id"),
                        "dimensions": cg.get("pred_dimensions", []),
                    },
                    "trace": cg.get("trace", {"decision": "see released prediction row; deterministic witness checks"}),
                }
            )
            break
        if len(selected) >= limit:
            break
    return selected


def write_protocol_cards() -> None:
    lines = [
        "# MetricCaliberBench Protocol Cards",
        "",
        "These cards state what each public layer is for. They are meant to prevent the benchmark contribution from reading as a pile of datasets.",
        "",
    ]
    cards = [
        ("IowaLiquor-MetricCaliber", "Real public row-level business data", "Tests whether executable SQL over external public rows is sufficient for governed metric planning.", "External State of Iowa rows; authored semantic layer/labels over that schema.", "Use the SQLite file, blind cases, catalogs, and scorer to compare NL2Metric-to-SQL planners."),
        ("Chinook-MetricCaliber", "Compact public stress benchmark", "Tests hierarchy/refusal/unsupported metric behavior on a familiar public database.", "Public sample DB; authored governance layer.", "Use for fast regression tests and ablations."),
        ("BIRD-MetricCaliber", "Text-to-SQL diagnostic", "Tests whether public SQL outputs recover governed aggregate expressions, measures, and group dimensions.", "External NL/SQL/schema records; strict parser may under-credit equivalent SQL.", "Use as diagnostic connection to Text-to-SQL, not as primary governed-BI benchmark."),
        ("GovTwin-MetricCaliber", "Public structural stress test", "Tests denominator, hierarchy, policy, perturbation, and paraphrase robustness with no private terms.", "Synthetic public names preserving private governance structure.", "Use for controlled witness-compiler ablations."),
        ("MultiGov-MetricCaliber", "Production-derived anonymized governance benchmark", "Tests recurring witness traps across 12 production DataGov domain versions.", "Anonymized governance artifacts; no raw enterprise rows or private mappings.", "Use to test cross-domain governed metric planning and policy refusal."),
        ("IndustrialCaseText-MetricCaliber", "Real desensitized enterprise query surface", "Tests actual NL2Metric case text and anonymized labels after conflict removal.", "Real desensitized case text; no raw rows/private ids.", "Use to compare methods on realistic business utterances with blind/gold split."),
        ("DataHub audit", "Aggregate production recurrence evidence", "Shows the same witness traps recur across seven business areas.", "Aggregate only, not a scored public benchmark.", "Use as motivation and recurrence evidence, not as public leaderboard data."),
    ]
    for name, evidence, purpose, boundary, reuse in cards:
        lines.extend(
            [
                f"## {name}",
                "",
                f"- Evidence type: {evidence}.",
                f"- What it tests: {purpose}",
                f"- Boundary: {boundary}",
                f"- How another method can use it: {reuse}",
                "",
            ]
        )
    (OUT / "METRICCALIBERBENCH_PROTOCOL_CARDS.md").write_text("\n".join(lines), encoding="utf-8")


def write_circularity_audit(mechanism_json: dict) -> None:
    lines = [
        "# release Leakage and Circularity Audit",
        "",
        "This audit separates reproducibility from independent validity. Public reproducibility means another method can run on label-free inputs and be scored; it does not pretend that authored governance contracts are external human labels.",
        "",
        "## Separation of Files",
        "",
        "- Prediction inputs: blind cases, public catalogs, graph/policy files, public row data where applicable.",
        "- Scorer-only files: `gold_labels.jsonl` or test-case `expected_*` fields.",
        "- Generated predictions: include `used_gold_label: false` where traces are available; oracle-candidate rows are explicitly flagged as diagnostics.",
        "- Private state: private DataHub rows, source ids, private table/column names, and private-to-public mappings are absent from public artifacts.",
        "",
        "## Rule Visibility",
        "",
        "| Rule family | Used by labels | Visible to baselines | Used by CaliberGraph | Leakage risk and control |",
        "|---|---|---|---|---|",
        "| Metric identity/aliases | Yes | Yes, via public metric catalogs | Yes | Shared contract; not a hidden label leak because catalogs are legal prediction inputs. |",
        "| Dimension hierarchy | Yes | Yes, via dimension catalogs/edges | Yes | Shared contract; mechanism audit compares prompt/validator baselines that see it but do not compile witness repair. |",
        "| Refusal/disclosure | Yes | Yes, via public policy files or trigger text where released | Yes | Scored as answer/refuse; gold labels are not prediction inputs. |",
        "| Physical coverage | Yes | Partly visible through released coverage records where public | Yes | Claims are contract-bound; no private coverage names are released. |",
        "| Gold expected ids | Yes | No | No during prediction | Verified by blind/gold split and label-free source checks. |",
        "",
        "## Held-out or Stress Evidence",
        "",
        "- GovTwin deterministic perturbations and LLM paraphrases stress the same policy contract outside base-case wording.",
        "- IndustrialCaseText conflict-free and deduplicated subsets test whether label conflicts or duplicate weighting drive the result.",
        "- release mechanism baselines show that seeing semantic-layer rules is insufficient without witness construction.",
        "",
        "## release Mechanism Summary",
        "",
    ]
    rows = []
    for dataset, item in mechanism_json["mechanism_baselines"].items():
        for mode in ["semantic_layer_validator", "posthoc_answerability_validator", "caliber_graph"]:
            if mode in item:
                s = item[mode]
                rows.append([dataset, mode, f"{s['joint_metric_dimension_accuracy']:.3f}", f"{s['refusal_precision']:.3f}", f"{s['refusal_recall']:.3f}"])
    lines.extend(md_table(["Dataset", "Method", "Joint", "Ref.P", "Ref.R"], rows))
    lines.extend(
        [
            "",
            "## Remaining Boundary",
            "",
            "The public benchmark is a governed-contract benchmark. The claim supported by these files is not universal NL2BI SOTA; it is that after candidate discovery is available, constructing an executable witness removes specific post-linking failures that retrieval, prompt finalization, semantic-layer validation, and post-hoc SQL validation leave unresolved.",
            "",
        ]
    )
    (OUT / "LEAKAGE_AND_CIRCULARITY_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")


def write_task_validity_audit() -> None:
    lines = [
        "# release Task Validity and Adjudication Audit",
        "",
        "This audit addresses the concern that NL2Metric-Caliber is merely a private scoring game. It gives reviewer-facing adjudication rules, boundary cases, and dispute handling for each label family.",
        "",
    ]
    rows = [
        ["Metric identity", "Choose the governed metric whose numerator/denominator and scope match the request, not the nearest alias.", "Refund amount when only return-rate exists.", "If two metrics share aliases, formula role and required fields decide."],
        ["Dimension grain", "If multiple levels on one hierarchy path are requested, keep the governed finest requested level unless the metric policy says otherwise.", "country+city -> city; level1+level2 -> level2.", "If dimensions are independent rather than hierarchical, keep both."],
        ["Caliber/coverage", "Answer only if required numerator, denominator, filters, time/order fields, and table grain are covered.", "Rate metric without denominator coverage.", "If related table has the metric but lacks requested grain/filter, refuse or certify missing coverage."],
        ["Temporal/as-of", "Use requested or default valid-time binding only when the source supports it.", "Current snapshot asked as historical as-of.", "If valid-time anchor absent, refusal is preferred to silently using load time."],
        ["Disclosure/refusal", "Raw identifiers, private mappings, SQL/DDL, off-domain, and unsupported metrics must be refused.", "show raw row identifiers behind assertion.", "If query asks aggregate plus private ids, refusal dominates."],
        ["Comparison policy", "For multi-metric comparisons, follow released primary-metric or explicit comparison policy.", "A vs. B when only A has coverage.", "If comparison support is under-specified, refuse or return governed primary metric per policy."],
    ]
    lines.extend(md_table(["Label family", "Adjudication rule", "Boundary example", "Dispute rule"], rows))
    lines.extend(
        [
            "",
            "The released `LABEL_POLICY.md`, protocol cards, and failure certificates make these rules inspectable. They do not make the task externally authored; instead, they make the governed-contract boundary explicit and reproducible.",
            "",
        ]
    )
    (OUT / "MODEL_TASK_VALIDITY_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    datasets = {}
    all_certificates = []
    for name in ["iowa", "ict", "multigov"]:
        rows, gold_by_id, parent = load_dataset(name)
        transformed = transform_baselines(name, rows, gold_by_id, parent)
        combined = rows + transformed
        summary = score_rows(combined, gold_by_id)
        datasets[name] = {
            "mechanism_baselines": {mode: summary[mode] for mode in summary if mode in {"semantic_layer_validator", "posthoc_answerability_validator", "caliber_graph"}},
            "candidate_residual": residual_after_candidate(rows, gold_by_id, ["schema_proxy", "open_sql_end_to_end", "autolink_iterative", "safenlidb_guarded", "oracle_candidate_prompt"]),
        }
        all_certificates.extend(collect_failure_certificates(name, combined, gold_by_id, limit=7))

    released_certificates = all_certificates[:20]
    payload = {
        "mechanism_baselines": {name: item["mechanism_baselines"] for name, item in datasets.items()},
        "candidate_residual": {name: item["candidate_residual"] for name, item in datasets.items()},
        "generated_failure_certificate_count": len(all_certificates),
        "released_failure_certificate_count": len(released_certificates),
        "claim_boundary": "fixed governed contracts; mechanism evidence after candidate availability, not universal NL2BI SOTA",
    }
    write_json(OUT / "mechanism_evidence_audit.json", payload)
    write_jsonl(OUT / "witness_failure_certificates.jsonl", released_certificates)
    write_protocol_cards()
    write_circularity_audit(payload)
    write_task_validity_audit()

    lines = [
        "# release Mechanism Evidence Audit",
        "",
        "Generated from released public prediction/gold files only. This audit answers the toxic-review concern that the paper reports perfect contract scores without isolating mechanism.",
        "",
        "## Fair Mechanism Baselines",
        "",
        "Semantic-layer validator sees public catalogs/policies and validates retrieved candidates, but does not construct a finest-grain coverage witness. Post-hoc answerability validator refuses invalid retrieved/SQL plans but does not re-plan to a repaired answer.",
        "",
    ]
    rows = []
    for dataset, item in payload["mechanism_baselines"].items():
        for mode in ["semantic_layer_validator", "posthoc_answerability_validator", "caliber_graph"]:
            s = item.get(mode)
            if s:
                rows.append([dataset, mode, f"{s['joint_metric_dimension_accuracy']:.3f}", f"{s['action_accuracy']:.3f}", f"{s['refusal_precision']:.3f}", f"{s['refusal_recall']:.3f}"])
    lines.extend(md_table(["Dataset", "Method", "Joint", "Action", "Ref.P", "Ref.R"], rows))
    lines.extend(["", "## Residual Failures After Candidate Availability", ""])
    rows = []
    for dataset, item in payload["candidate_residual"].items():
        for mode, s in item.items():
            rows.append([dataset, mode, f"{s['candidate_available']:.3f}", f"{s['residual_failure_given_candidate']:.3f}", json.dumps(s["residual_counts"], ensure_ascii=False, sort_keys=True)])
    lines.extend(md_table(["Dataset", "Mode", "Candidate available", "Residual fail given candidate", "Residual families"], rows))
    lines.extend(
        [
            "",
            "## Released Failure Certificates",
            "",
            f"- `witness_failure_certificates.jsonl` contains {len(released_certificates)} public cases with baseline prediction, missing witness type, and CaliberGraph decision; {len(all_certificates)} certificates were generated before applying the fixed release cap.",
            "- These certificates are evidence for mechanism, not additional benchmark cases.",
            "",
        ]
    )
    (OUT / "mechanism_evidence_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
