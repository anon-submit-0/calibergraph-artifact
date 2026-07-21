#!/usr/bin/env python3
"""Audit H1 response/prompt provenance after release contract migration."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("h1_release", HERE / "run_h1.py")
h1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h1)

ORIGIN = {
    "chinook": "frozen predecessor run; prompt unchanged and SHA replayed",
    "ict": "frozen predecessor run; prompt unchanged and SHA replayed",
    "iowa": "new complete-contract run after adding contract_profile and schema_columns",
    "govtwin": "new complete-contract run after adding contract_profile",
    "multigov": "new complete-contract run with metric-specific coverage bindings and physical coverage",
}


def main():
    report = {"experiment_id": h1.EXPERIMENT_ID, "layers": {}}
    complete = True
    for layer in h1.LAYERS:
        cases = h1.load_cases(layer)
        system_prompt = h1.build_system_prompt(layer)
        system_sha = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
        saved_prompt = (HERE / "prompts" / f"{layer}_system.txt").read_text(encoding="utf-8")
        raw_path = HERE / "raw_responses" / f"{layer}_raw.jsonl"
        raws = {}
        if raw_path.exists():
            for row in h1.read_jsonl(raw_path):
                previous = raws.get(row["case_id"])
                if previous is None or (previous.get("error") and not row.get("error")):
                    raws[row["case_id"]] = row
        prompt_mismatches = []
        contract_sha_mismatches = []
        errors = []
        for case in cases:
            row = raws.get(case["case_id"])
            if row is None:
                continue
            user = h1.USER_TEMPLATE.format(case_id=case["case_id"], nl_query=case["nl_query"])
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}]
            expected_prompt_sha = hashlib.sha256(
                json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            if row.get("prompt_sha256") != expected_prompt_sha:
                prompt_mismatches.append(case["case_id"])
            if row.get("contract_prompt_sha256") not in (None, system_sha):
                contract_sha_mismatches.append(case["case_id"])
            if row.get("error"):
                errors.append({"case_id": case["case_id"], "error": row["error"]})
        layer_complete = (
            len(raws) == len(cases)
            and saved_prompt == system_prompt
            and not prompt_mismatches
            and not contract_sha_mismatches
            and not errors
        )
        complete = complete and layer_complete
        report["layers"][layer] = {
            "origin": ORIGIN[layer],
            "n_cases": len(cases),
            "n_response_records_selected": len(raws),
            "system_prompt_sha256": system_sha,
            "system_prompt_bytes": len(system_prompt.encode("utf-8")),
            "saved_prompt_exact_match": saved_prompt == system_prompt,
            "prompt_sha_mismatches": prompt_mismatches,
            "contract_sha_mismatches": contract_sha_mismatches,
            "api_error_records_selected": errors,
            "complete": layer_complete,
        }
    report["overall_complete"] = complete
    report["legacy_boundary"] = (
        "Older incomplete-contract Iowa/GovTwin/MultiGov outputs remain author-side and are "
        "excluded from this public artifact and from current scoring."
    )
    (HERE / "prompt_provenance_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
