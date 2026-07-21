#!/usr/bin/env python3
"""Validate released MultiGov coverage ids without private source keys."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "public_benchmark" / "multigov_metric_caliber" / "physical_coverage.jsonl"
BINDINGS = ROOT / "public_benchmark" / "multigov_metric_caliber" / "metric_coverage_bindings.jsonl"


def main():
    rows = [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    physical_ids = set()
    for row in rows:
        semantic_node_id = row.get("semantic_node_id")
        if not semantic_node_id or not semantic_node_id.startswith(f"{row['domain_id']}_node_"):
            raise ValueError(f"invalid public semantic node id: {semantic_node_id!r}")
        physical_ids.add(semantic_node_id)
    bindings = [json.loads(line) for line in BINDINGS.read_text(encoding="utf-8").splitlines() if line.strip()]
    dangling = sorted(
        {
            row.get("physical_node_id")
            for row in bindings
            if row.get("physical_node_id") not in physical_ids
        }
    )
    if dangling:
        raise ValueError(f"metric bindings reference unknown public physical nodes: {dangling[:10]}")
    PATH.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "coverage_rows": len(rows),
                "metric_bindings": len(bindings),
                "path": str(PATH.relative_to(ROOT)),
                "private_source_keys_required": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
