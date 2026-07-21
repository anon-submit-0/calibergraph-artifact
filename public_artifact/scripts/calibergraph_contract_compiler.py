#!/usr/bin/env python3
"""Executable coverage-caliber contract compiler.

The compiler consumes only released catalogs and a label-free query/plan.  It
does not score predictions and never reads expected_* fields.  Each decision
contains an explicit check for field binding, caliber dependencies, reporting
grain, physical/semantic coverage, valid time, and policy authorization.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path


GAMMA_ORDER = ("field", "caliber", "grain", "coverage", "time", "policy")
SQL_WORDS = {
    "as",
    "cast",
    "count",
    "date",
    "distinct",
    "float",
    "integer",
    "nullif",
    "real",
    "strftime",
    "substr",
    "sum",
}


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_json(path: Path, default):
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text):
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def formula_fields(expression):
    expression = re.sub(r"'[^']*'|\"[^\"]*\"", " ", str(expression or ""))
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expression)
    return sorted({token.lower() for token in tokens if token.lower() not in SQL_WORDS})


def contains_alias(query, alias):
    query = normalize(query)
    alias = normalize(alias)
    if not alias:
        return False
    if re.fullmatch(r"[a-z0-9_ ]+", alias):
        return re.search(rf"(?<![a-z0-9_]){re.escape(alias)}(?![a-z0-9_])", query) is not None
    return alias in query


class ContractCompiler:
    """Compile a candidate plan into a witness or a typed refusal."""

    def __init__(self, dataset_dir: Path, metadata_override=None):
        self.dataset_dir = Path(dataset_dir)
        self.metrics = {row["metric_id"]: row for row in read_jsonl(self.dataset_dir / "metric_catalog.jsonl")}
        self.dimensions = {
            row["dimension_id"]: row for row in read_jsonl(self.dataset_dir / "dimension_catalog.jsonl")
        }
        self.edges = read_jsonl(self.dataset_dir / "governance_edges.jsonl")
        self.policies = read_jsonl(self.dataset_dir / "policy_catalog.jsonl")
        self.coverage = read_jsonl(self.dataset_dir / "physical_coverage.jsonl")
        self.metric_coverage_bindings = read_jsonl(self.dataset_dir / "metric_coverage_bindings.jsonl")
        self.profile = read_json(self.dataset_dir / "contract_profile.json", {})
        self.schema_columns = {
            str(row.get("name", "")).lower()
            for row in read_json(self.dataset_dir / "schema_columns.json", [])
            if row.get("name")
        }
        self.parents = {dim_id: row.get("parent", "") for dim_id, row in self.dimensions.items()}
        self._index_edges()
        if metadata_override:
            self.apply_override(metadata_override)

    def apply_override(self, override):
        if "schema_columns" in override:
            self.schema_columns = {str(value).lower() for value in override["schema_columns"]}
        if "metric_patch" in override:
            for metric_id, patch in override["metric_patch"].items():
                if metric_id in self.metrics:
                    self.metrics[metric_id] = {**self.metrics[metric_id], **patch}
        if "coverage" in override:
            self.coverage = copy.deepcopy(override["coverage"])
        if "metric_coverage_bindings" in override:
            self.metric_coverage_bindings = copy.deepcopy(override["metric_coverage_bindings"])
        if "edges" in override:
            self.edges = copy.deepcopy(override["edges"])
            self._index_edges()

    def _index_edges(self):
        self.edges_by_type = {}
        for edge in self.edges:
            self.edges_by_type.setdefault(edge.get("edge_type", ""), []).append(edge)

    def detect_dimensions(self, query, domain_id=""):
        query_norm = normalize(query)
        scope = ""
        for marker in ("grouped by ", "group by ", " by ", " per ", " across ", "grouping="):
            if marker in query_norm:
                scope = query_norm.split(marker, 1)[1]
                break
        if not scope and "按" in query_norm:
            scope = query_norm.split("按", 1)[1]
        if not scope and "breakdown for" in query_norm:
            scope = query_norm.split("breakdown for", 1)[0]
        if not scope and any(marker in query_norm for marker in ("monthly", "quarterly", "valid time anchor", "with the valid time")):
            scope = query_norm
        if not scope:
            return []
        if "monthly" in query_norm:
            scope += " monthly month"
        if "quarterly" in query_norm:
            scope += " quarterly quarter"
        found = []
        for dim_id, dim in self.dimensions.items():
            if domain_id and dim.get("domain_id") and dim.get("domain_id") != domain_id:
                continue
            aliases = [dim_id, dim.get("name", ""), *dim.get("aliases", [])]
            if any(contains_alias(scope, alias) for alias in aliases):
                found.append(dim_id)
        return sorted(set(found), key=lambda value: (self.dimensions[value].get("grain_rank", 0), value))

    def ancestors(self, dim_id):
        result = []
        seen = set()
        parent = self.parents.get(dim_id, "")
        while parent and parent not in seen:
            seen.add(parent)
            result.append(parent)
            parent = self.parents.get(parent, "")
        return result

    def finest_dimensions(self, dimensions):
        requested = list(dict.fromkeys(dimensions or []))
        shadowed = set()
        for dim_id in requested:
            shadowed.update(self.ancestors(dim_id))
        return [dim_id for dim_id in requested if dim_id not in shadowed]

    def detect_time(self, query):
        query_norm = normalize(query)
        for anchor, aliases in self.profile.get("time_aliases", {}).items():
            if any(contains_alias(query_norm, alias) for alias in aliases):
                return anchor
        year = re.search(r"\b(20\d{2})\b", query_norm)
        return year.group(1) if year else self.profile.get("default_time_anchor", "")

    def policy_hits(self, query, metric):
        query_norm = normalize(query)
        hits = []
        if not metric:
            hits.append({"policy_id": "no_governed_metric", "trigger": "empty_metric_candidate"})
        elif metric.get("answerable") is False:
            hits.append({"policy_id": "unsupported_metric", "trigger": metric.get("metric_id", "")})

        for policy in self.policies:
            policy_id = policy.get("policy_id", "policy")
            ambiguous = {normalize(value) for value in policy.get("ambiguous_queries", [])}
            if query_norm in ambiguous:
                hits.append({"policy_id": policy_id, "trigger": "ambiguous_query"})
            for trigger in policy.get("refusal_triggers", []):
                if normalize(trigger) in query_norm:
                    hits.append({"policy_id": policy_id, "trigger": trigger})
            trigger_text = policy.get("trigger", "")
            for trigger in self._trigger_terms(trigger_text):
                if trigger in query_norm:
                    hits.append({"policy_id": policy_id, "trigger": trigger})

        for rule in self.profile.get("policy_rules", []):
            if any(normalize(trigger) in query_norm for trigger in rule.get("contains", [])):
                hits.append({"policy_id": rule["policy_id"], "trigger": "contains"})
            if query_norm in {normalize(value) for value in rule.get("exact", [])}:
                hits.append({"policy_id": rule["policy_id"], "trigger": "exact"})

        dedup = {(row["policy_id"], row["trigger"]): row for row in hits}
        return list(dedup.values())

    @staticmethod
    def _trigger_terms(trigger_text):
        text = normalize(trigger_text)
        terms = []
        if "sql" in text or "ddl" in text:
            terms.extend(["select ", "drop ", "delete ", "insert ", "update ", "truncate "])
        if "personal" in text or "customer" in text or "identifier" in text:
            terms.extend(["email", "phone", "personal contact", "customer identifier"])
        if "off-domain" in text:
            terms.extend(["weather", "tomorrow"])
        if "unsupported" in text:
            terms.extend(["unsupported", "experimental margin"])
        return terms

    def dependency_evidence(self, metric):
        formula = str(metric.get("formula", ""))
        ratio_like = bool(
            metric.get("scoped_ratio")
            or metric.get("scoped_ratio_kind") not in (None, "", "none")
            or metric.get("metric_type") in {"ratio", "rate", "ratio_caliber"}
            or "/" in formula
            or metric.get("numerator")
            or metric.get("denominator")
        )
        if not ratio_like:
            return {"ratio_like": False, "numerator": [], "denominator": [], "route_source": "not_required"}

        metric_id = metric.get("metric_id", "")
        explicit_numerator_nodes = list(metric.get("numerator_nodes", []))
        explicit_denominator_nodes = list(metric.get("denominator_nodes", []))
        if explicit_numerator_nodes or explicit_denominator_nodes:
            numerator_edges = [
                edge
                for edge in self.edges_by_type.get("numerator_of", [])
                if edge.get("dst") == metric_id
                and edge.get("src") in explicit_numerator_nodes
                and edge.get("metric_id", metric_id) == metric_id
            ]
            denominator_edges = [
                edge
                for edge in self.edges_by_type.get("denominator_of", [])
                if edge.get("dst") == metric_id
                and edge.get("src") in explicit_denominator_nodes
                and edge.get("metric_id", metric_id) == metric_id
            ]
            return {
                "ratio_like": True,
                "metric_id": metric_id,
                "numerator": sorted({edge["src"] for edge in numerator_edges}),
                "denominator": sorted({edge["src"] for edge in denominator_edges}),
                "required_numerator": sorted(explicit_numerator_nodes),
                "required_denominator": sorted(explicit_denominator_nodes),
                "route_source": "metric_specific_typed_graph_edges",
            }

        numerator = formula_fields(metric.get("numerator", ""))
        denominator = formula_fields(metric.get("denominator", ""))
        if "/" in formula:
            left, right = formula.split("/", 1)
            numerator = numerator or formula_fields(left)
            denominator = denominator or formula_fields(right)

        if not numerator or not denominator:
            numerator_edges = [
                edge
                for edge in self.edges_by_type.get("numerator_of", [])
                if edge.get("dst") == metric_id and edge.get("metric_id", metric_id) == metric_id
            ]
            denominator_edges = [
                edge
                for edge in self.edges_by_type.get("denominator_of", [])
                if edge.get("dst") == metric_id and edge.get("metric_id", metric_id) == metric_id
            ]
            numerator = numerator or sorted({edge.get("src", "") for edge in numerator_edges if edge.get("src")})
            denominator = denominator or sorted({edge.get("src", "") for edge in denominator_edges if edge.get("src")})
            route_source = "metric_specific_typed_graph_edges"
        else:
            route_source = "metric_formula"
        return {
            "ratio_like": True,
            "metric_id": metric_id,
            "numerator": numerator,
            "denominator": denominator,
            "route_source": route_source,
        }

    def required_fields(self, metric, dimensions):
        fields = set(formula_fields(metric.get("formula", "")))
        fields.update(formula_fields(metric.get("numerator", "")))
        fields.update(formula_fields(metric.get("denominator", "")))
        for dim_id in dimensions:
            fields.update(formula_fields(self.dimensions.get(dim_id, {}).get("sql", "")))
        return sorted(fields)

    def coverage_check(self, metric, required_fields, override=None):
        if override is not None:
            covered = {str(value).lower() for value in override}
            missing = sorted(set(required_fields) - covered)
            return {
                "active": True,
                "passed": not missing,
                "mode": "explicit_override",
                "required": required_fields,
                "missing": missing,
            }
        if self.schema_columns:
            missing = sorted(set(required_fields) - self.schema_columns)
            return {
                "active": True,
                "passed": not missing,
                "mode": "physical_schema_columns",
                "required": required_fields,
                "missing": missing,
            }
        if self.metric_coverage_bindings:
            metric_id = metric.get("metric_id", "")
            required_nodes = set(metric.get("coverage_nodes", []))
            coverage_required = bool(metric.get("coverage_required") or required_nodes)
            if not coverage_required:
                return {
                    "active": False,
                    "passed": True,
                    "mode": "not_required_by_metric_contract",
                    "metric_id": metric_id,
                    "required_nodes": [],
                    "missing": [],
                }
            metric_rows = [row for row in self.metric_coverage_bindings if row.get("metric_id") == metric_id]
            physical_nodes = {row.get("semantic_node_id", "") for row in self.coverage}
            bound_by_dependency = {}
            for row in metric_rows:
                bound_by_dependency.setdefault(row.get("dependency_node_id", ""), []).append(row)
            missing_bindings = sorted(node for node in required_nodes if not bound_by_dependency.get(node))
            missing_physical_assets = sorted(
                {
                    row.get("physical_node_id", "")
                    for node in required_nodes
                    for row in bound_by_dependency.get(node, [])
                    if not row.get("physical_node_id") or row.get("physical_node_id") not in physical_nodes
                }
            )
            empty_required_set = not required_nodes
            passed = not empty_required_set and not missing_bindings and not missing_physical_assets
            return {
                "active": True,
                "passed": passed,
                "mode": "metric_specific_semantic_to_physical_binding",
                "metric_id": metric_id,
                "required_nodes": sorted(required_nodes),
                "binding_count": len(metric_rows),
                "physical_asset_count": len(physical_nodes),
                "empty_required_set": empty_required_set,
                "missing_bindings": missing_bindings,
                "missing_physical_assets": missing_physical_assets,
                "missing": sorted(set(missing_bindings) | set(missing_physical_assets)),
            }
        if self.coverage:
            domain_id = metric.get("domain_id", "")
            domain_rows = [row for row in self.coverage if not domain_id or row.get("domain_id") == domain_id]
            required_nodes = set(metric.get("coverage_nodes", []))
            if not required_nodes:
                return {
                    "active": False,
                    "passed": True,
                    "mode": "no_metric_specific_coverage_requirement",
                    "required_nodes": [],
                    "missing": [],
                }
            covered_nodes = {row.get("semantic_node_id", "") for row in domain_rows}
            missing = sorted(required_nodes - covered_nodes)
            passed = bool(domain_rows) and not missing
            return {
                "active": True,
                "passed": passed,
                "mode": "released_semantic_to_physical_coverage",
                "required_nodes": sorted(required_nodes),
                "covered_node_count": len(covered_nodes),
                "missing": missing,
            }
        return {
            "active": False,
            "passed": True,
            "mode": "not_available_in_released_contract",
            "required": required_fields,
            "missing": [],
        }

    def compile(
        self,
        query,
        metric_id,
        requested_dimensions=None,
        candidate_metrics=None,
        time_binding=None,
        coverage_override=None,
        disabled_checks=None,
    ):
        disabled = set(disabled_checks or [])
        metric = self.metrics.get(metric_id)
        requested = (
            self.detect_dimensions(query, domain_id=(metric or {}).get("domain_id", ""))
            if requested_dimensions is None
            else list(requested_dimensions)
        )
        resolved = self.finest_dimensions(requested)
        unknown_dims = sorted(dim_id for dim_id in requested if dim_id not in self.dimensions)
        allowed = set(metric.get("allowed_dimensions", [])) if metric else set()
        disallowed = sorted(dim_id for dim_id in resolved if allowed and dim_id not in allowed)
        dependencies = self.dependency_evidence(metric or {})
        caliber_passed = (not dependencies["ratio_like"]) or (
            bool(dependencies["numerator"] and dependencies["denominator"])
            and set(dependencies.get("required_numerator", [])).issubset(dependencies["numerator"])
            and set(dependencies.get("required_denominator", [])).issubset(dependencies["denominator"])
        )
        required = self.required_fields(metric or {}, resolved)
        policy_hits = self.policy_hits(query, metric)
        detected_time = time_binding if time_binding is not None else self.detect_time(query)
        available_times = set(self.profile.get("available_time_anchors", []))
        temporal_required = bool(metric and metric.get("temporal_anchor_required"))
        time_passed = (not temporal_required or bool(detected_time)) and (
            not available_times or not detected_time or detected_time in available_times
        )

        checks = {
            "field": {
                "active": True,
                "passed": metric is not None and not unknown_dims,
                "metric_id": metric_id,
                "unknown_dimensions": unknown_dims,
            },
            "caliber": {
                "active": True,
                "passed": caliber_passed,
                **dependencies,
            },
            "grain": {
                "active": True,
                "passed": not unknown_dims and not disallowed,
                "requested": requested,
                "resolved_finest": resolved,
                "removed_ancestors": sorted(set(requested) - set(resolved)),
                "disallowed": disallowed,
            },
            "coverage": self.coverage_check(metric or {}, required, override=coverage_override),
            "time": {
                "active": temporal_required or bool(available_times),
                "passed": time_passed,
                "required": temporal_required,
                "detected": detected_time,
                "available": sorted(available_times),
            },
            "policy": {
                "active": True,
                "passed": not policy_hits,
                "hits": policy_hits,
            },
        }
        for name in disabled:
            if name in checks:
                checks[name] = {**checks[name], "active": False, "passed": True, "disabled_for_ablation": True}

        failures = [name for name in GAMMA_ORDER if checks[name]["active"] and not checks[name]["passed"]]
        action = "answer" if not failures else "refuse"
        certificate = None
        if failures:
            certificate = {
                "failed_constraints": failures,
                "primary_failure": failures[0],
                "repairable": failures == ["grain"],
            }
        return {
            "action": action,
            "pred_metric_id": metric_id if action == "answer" else "",
            "pred_dimensions": resolved if action == "answer" else [],
            "reason": "witness_satisfied" if action == "answer" else f"constraint_failure:{failures[0]}",
            "trace": {
                "candidate_metrics": list(candidate_metrics or []),
                "checks": checks,
                "certificate": certificate,
                "used_gold_label": False,
            },
        }
