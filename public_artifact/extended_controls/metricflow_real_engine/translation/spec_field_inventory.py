#!/usr/bin/env python3
"""P10: mechanical inexpressibility evidence.

Dump EVERY field (recursively, pydantic model_fields) of the installed dbt-semantic-interfaces
spec objects (semantic model, dimension, measure, entity, metric and their type-params) to
spec_field_inventory.json. This is the auditable proof that no field exists for:
per-metric allowed/denied dimensions, categorical hierarchy, disclosure/aggregate-only policy,
physical coverage windows, as-of binding, or structured refusal reasons.
"""

import importlib.metadata
import json
from pathlib import Path

from dbt_semantic_interfaces.implementations.semantic_model import PydanticSemanticModel
from dbt_semantic_interfaces.implementations.metric import PydanticMetric

HERE = Path(__file__).resolve().parent

SEEN = {}


def _fields(model_cls):
    """Support pydantic v2 (model_fields) and v1-compat (__fields__)."""
    if hasattr(model_cls, "model_fields"):
        return {n: f.annotation for n, f in model_cls.model_fields.items()}
    return {n: getattr(f, "outer_type_", getattr(f, "annotation", None)) for n, f in model_cls.__fields__.items()}


def _is_pydantic_model(obj):
    return isinstance(obj, type) and (hasattr(obj, "model_fields") or hasattr(obj, "__fields__"))


def describe(model_cls, depth=0, max_depth=8):
    key = model_cls.__name__
    if key in SEEN or depth > max_depth:
        return key
    fields = {}
    SEEN[key] = fields
    for name, ann in _fields(model_cls).items():
        fields[name] = str(ann)
        # recurse into nested pydantic models found in the annotation
        stack = [ann]
        while stack:
            a = stack.pop()
            if _is_pydantic_model(a):
                describe(a, depth + 1, max_depth)
            else:
                stack.extend(getattr(a, "__args__", ()) or ())
    return key


def main():
    describe(PydanticSemanticModel)
    describe(PydanticMetric)
    payload = {
        "dbt_semantic_interfaces_version": importlib.metadata.version("dbt-semantic-interfaces"),
        "note": "Exhaustive recursive field inventory of the installed spec. Search it for any field "
        "capable of hosting: allowed/denied dimensions per metric, categorical dimension hierarchy, "
        "disclosure/aggregate-only policy, physical coverage window, as-of binding, refusal reason codes.",
        "models": SEEN,
    }
    out = HERE / "spec_field_inventory.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out} with {len(SEEN)} spec classes")


if __name__ == "__main__":
    main()
