#!/usr/bin/env python3
"""Engine capability probes P1-P7, P9 (pre-registered in protocol.md section 6).

Each probe is one real `mf query` invocation; full stdout/stderr goes to probes/PN_<name>.txt
and a machine-readable verdict to probes/probes_results.json. P8 evidence is the captured
`mf query --help` (P8_mf_query_help.txt); P10 is produced by spec_field_inventory.py.
"""

import csv
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ROOT = HERE.parent
DBT_PROJECT = RUN_ROOT / "dbt_project"
MF_BIN = sys.argv[1] if len(sys.argv) > 1 else "mf"

PROBES = [
    {
        "id": "P1",
        "name": "governance_denied_combo_invoice_count_x_item_desc",
        "metrics": "invoice_count",
        "group_by": "sale_line__item_desc",
        "extra": [],
        "governance_says": "DENIED (no measures_of edge invoice_count->item_desc; invoice grain does not nest in item)",
        "prediction": "engine compiles and runs (no per-metric dimension policy)",
    },
    {
        "id": "P2",
        "name": "governance_denied_combo_store_count_x_store_name",
        "metrics": "store_count",
        "group_by": "sale_line__store_name",
        "extra": [],
        "governance_says": "DENIED (no measures_of edge store_count->store_name)",
        "prediction": "engine compiles and runs",
    },
    {
        "id": "P3",
        "name": "hierarchy_no_finest_grain_collapse",
        "metrics": "sales_dollars",
        "group_by": "sale_line__county_name,sale_line__store_city",
        "extra": [],
        "governance_says": "county rolls up to city's parent; finest-grain resolution should collapse to store_city",
        "prediction": "engine returns both columns, no collapse",
    },
    {
        "id": "P4",
        "name": "undeclared_column_store_address",
        "metrics": "sales_dollars",
        "group_by": "sale_line__store_address",
        "extra": [],
        "governance_says": "store_address is aggregate_only (disclosure denied); encoded only by omission",
        "prediction": "resolver error (blocking-by-absence, generic message)",
    },
    {
        "id": "P5",
        "name": "unknown_metric_profit_margin",
        "metrics": "profit_margin",
        "group_by": "",
        "extra": [],
        "governance_says": "declared metric with answerable=false + unsupported_metric_policy",
        "prediction": "generic unknown-metric error, no policy provenance",
    },
    {
        "id": "P6",
        "name": "injection_string_as_metric_name",
        "metrics": "sales_dollars; DROP TABLE iowa_liquor_sales",
        "group_by": "",
        "extra": [],
        "governance_says": "must refuse",
        "prediction": "parser error (credit: no raw-SQL passthrough)",
    },
    {
        "id": "P7a",
        "name": "native_time_granularity_month",
        "metrics": "sales_dollars",
        "group_by": "metric_time__month",
        "extra": [],
        "governance_says": "ordered_month is an allowed dimension",
        "prediction": "works (credit)",
    },
    {
        "id": "P7b",
        "name": "native_time_granularity_quarter",
        "metrics": "sales_dollars",
        "group_by": "metric_time__quarter",
        "extra": [],
        "governance_says": "ordered_quarter is an allowed dimension",
        "prediction": "works (credit)",
    },
    {
        "id": "P9",
        "name": "coverage_window_out_of_range_2023",
        "metrics": "sales_dollars",
        "group_by": "metric_time__month",
        "extra": ["--start-time", "2023-01-01", "--end-time", "2023-12-31"],
        "governance_says": "physical coverage is 2024-only; out-of-coverage must be refused/caveated",
        "prediction": "exit 0 with EMPTY result (silent empty answer, no coverage refusal)",
    },
]


def main():
    results = []
    for p in PROBES:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
            csv_path = Path(tf.name)
        cmd = [MF_BIN, "query", "--metrics", p["metrics"], "--limit", "20", "--csv", str(csv_path)]
        if p["group_by"]:
            cmd.extend(["--group-by", p["group_by"]])
        cmd.extend(p["extra"])
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=DBT_PROJECT, capture_output=True, text=True, timeout=600,
                              env={**os.environ, "DBT_PROFILES_DIR": str(DBT_PROJECT)})
        wall = round(time.time() - t0, 2)
        n_rows = 0
        if proc.returncode == 0 and csv_path.exists():
            try:
                with open(csv_path, newline="") as f:
                    n_rows = max(0, sum(1 for _ in csv.reader(f)) - 1)
            except Exception:
                n_rows = 0
        (HERE / f"{p['id']}_{p['name']}.txt").write_text(
            "COMMAND: " + " ".join(cmd) + f"\nEXIT_CODE: {proc.returncode}\nWALL_SECONDS: {wall}\nDATA_ROWS: {n_rows}\n"
            f"GOVERNANCE_SAYS: {p['governance_says']}\nPRE_REGISTERED_PREDICTION: {p['prediction']}\n"
            "----- STDOUT -----\n" + proc.stdout + "\n----- STDERR -----\n" + proc.stderr + "\n",
            encoding="utf-8",
        )
        csv_path.unlink(missing_ok=True)
        results.append(
            {
                "probe": p["id"],
                "name": p["name"],
                "command": " ".join(cmd[:-2] if False else cmd),
                "governance_says": p["governance_says"],
                "pre_registered_prediction": p["prediction"],
                "exit_code": proc.returncode,
                "data_rows": n_rows,
                "engine_accepted": proc.returncode == 0,
            }
        )
        print(f"{p['id']} exit={proc.returncode} rows={n_rows}")
    (HERE / "probes_results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
