#!/usr/bin/env python3
"""Preflight official upstream AutoLink and SAFENLIDB reproduction.

This script does not substitute the official baselines with paper-specific
diagnostics. It records whether the unmodified upstream training/evaluation
pipelines have all official resource gates open, and emits exact commands to
run once externally required resources are mounted. The generated report is a
resource-gated run contract, not a claim that official full-chain numbers were
obtained on this host.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "official_baseline_resource_gated"
AUTOLINK = ROOT / "external_baselines" / "AutoLink"
SAFENLIDB = ROOT / "external_baselines" / "SAFENLIDB"
DEFAULT_GENERATED_AT = "2026-07-08T00:00:00+00:00"


def run(cmd, cwd=None, timeout=30):
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:  # pragma: no cover - defensive audit path
        return {"cmd": cmd, "returncode": -1, "stdout": "", "stderr": repr(exc)}


def rel_display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def git_info(repo):
    commit_file = repo / "UPSTREAM_COMMIT.txt"
    remote_file = repo / "UPSTREAM_REMOTE.txt"
    if not (repo / ".git").exists() and commit_file.exists() and remote_file.exists():
        return {
            "commit": commit_file.read_text(encoding="utf-8").strip(),
            "remote": remote_file.read_text(encoding="utf-8").strip(),
            "status_porcelain": "not_a_git_checkout; commit recorded in UPSTREAM_COMMIT.txt",
        }
    return {
        "commit": run(["git", "rev-parse", "HEAD"], cwd=repo)["stdout"],
        "remote": run(["git", "remote", "get-url", "origin"], cwd=repo)["stdout"],
        "status_porcelain": run(["git", "status", "--porcelain"], cwd=repo)["stdout"],
    }


def exists(path):
    return path.exists()


def nonempty_dir(path):
    return path.is_dir() and any(path.iterdir())


def count_json(path):
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data)


def shell_syntax(paths):
    checks = []
    for path in paths:
        if path.exists():
            result = run(["bash", "-n", str(path)])
            result["cmd"] = ["bash", "-n", rel_display(path)]
            checks.append(result)
        else:
            checks.append({"cmd": ["bash", "-n", rel_display(path)], "returncode": -1, "stdout": "", "stderr": "missing"})
    return checks


def detect_python_packages(names):
    checks = {}
    for name in names:
        code = f"import importlib.util; raise SystemExit(0 if importlib.util.find_spec({name!r}) else 1)"
        result = run(["python3", "-c", code])
        checks[name] = result["returncode"] == 0
    return checks


def deterministic_generated_at():
    """Keep release artifacts byte-stable unless a caller opts into SOURCE_DATE_EPOCH."""
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw:
        try:
            return datetime.fromtimestamp(int(raw), timezone.utc).isoformat()
        except ValueError:
            pass
    return DEFAULT_GENERATED_AT


def autolink_preflight():
    run_dir = AUTOLINK / "run"
    main_sh = run_dir / "main.sh"
    sql_gen_sh = run_dir / "sql_gen.sh"
    main_text = main_sh.read_text(encoding="utf-8") if main_sh.exists() else ""
    api_configured = 'OPENAI_API_KEY=""' not in main_text and "OPENAI_API_KEY" in main_text
    base_url_configured = 'OPENAI_BASE_URL=""' not in main_text and "OPENAI_BASE_URL" in main_text
    required = {
        "repo_exists": AUTOLINK.is_dir(),
        "requirements_txt": exists(AUTOLINK / "requirements.txt"),
        "main_sh": exists(main_sh),
        "sql_gen_sh": exists(sql_gen_sh),
        "spider2_data_json": exists(run_dir / "spider2_data.json"),
        "spider2_lite_resource_dir": nonempty_dir(run_dir / "resource"),
        "bigquery_credentials_dir": nonempty_dir(run_dir / "bigquery_credentials"),
        "snowflake_credential_dir": nonempty_dir(run_dir / "snowflake_credential"),
        "api_key_configured_in_main_sh": api_configured,
        "api_base_url_configured_in_main_sh": base_url_configured,
    }
    missing_gate_requirements = [name for name, ok in required.items() if not ok]
    resource_gate_open = not missing_gate_requirements
    return {
        "name": "AutoLink",
        "upstream": git_info(AUTOLINK),
        "official_case_count": count_json(run_dir / "spider2_data.json"),
        "syntax_checks": shell_syntax([main_sh, sql_gen_sh]),
        "required_resources": required,
        "resource_gate_open": resource_gate_open,
        "gate_status": "ready_for_official_full_chain" if resource_gate_open else "resource_gated_external_requirements_missing",
        "missing_gate_requirements": missing_gate_requirements,
        "official_commands": [
            "cd external_baselines/AutoLink",
            "python3 -m venv .venv-autolink",
            "source .venv-autolink/bin/activate",
            "pip install -r requirements.txt",
            "cp -R /path/to/Spider2/spider2-lite/resource run/resource",
            "install BigQuery credentials under run/bigquery_credentials",
            "install Snowflake credentials under run/snowflake_credential",
            "set OPENAI_API_KEY and OPENAI_BASE_URL in run/main.sh and run/sql_gen.sh",
            "cd run && bash main.sh && bash sql_gen.sh",
        ],
        "paper_release_policy": "Use complete official upstream execution only after the resource gate opens; before that, main result tables use released runnable protocols and the official chain is reported as a resource-gated run contract.",
    }


def safenlidb_preflight():
    scripts = [
        SAFENLIDB / "DB_prepare" / "extract_db_ids_json.py",
        SAFENLIDB / "DB_prepare" / "omni.py",
        SAFENLIDB / "data_synthesis" / "A_safe_condition" / "A_safe_condition.sh",
        SAFENLIDB / "data_synthesis" / "B_sql_construction" / "B_sql.sh",
        SAFENLIDB / "data_synthesis" / "C_NL_question_syn" / "C_question.sh",
        SAFENLIDB / "data_synthesis" / "D_Gen_COT" / "D_sql_cot.sh",
        SAFENLIDB / "data_synthesis" / "E_secure_COT" / "E_secure_cot.sh",
        SAFENLIDB / "train" / "SFT" / "sft.sh",
        SAFENLIDB / "train" / "Inference" / "beam_infer.sh",
        SAFENLIDB / "train" / "APO" / "APO.sh",
        SAFENLIDB / "evaluate" / "scrpit" / "infer.sh",
        SAFENLIDB / "evaluate" / "scrpit" / "prepare.sh",
    ]
    required = {
        "repo_exists": SAFENLIDB.is_dir(),
        "requirements_txt": exists(SAFENLIDB / "requirements.txt"),
        "shieldsql_test_present": exists(SAFENLIDB / "evaluate" / "ShieldSQL" / "RS++" / "test++.json"),
        "omnisql_database_present": nonempty_dir(SAFENLIDB / "OmniSQL") or nonempty_dir(SAFENLIDB / "data" / "OmniSQL"),
        "securesql_dataset_present": nonempty_dir(SAFENLIDB / "SecureSQL") or nonempty_dir(SAFENLIDB / "data" / "SecureSQL"),
        "spider_database_present": nonempty_dir(SAFENLIDB / "Spider") or nonempty_dir(SAFENLIDB / "data" / "Spider"),
        "bird_database_present": nonempty_dir(SAFENLIDB / "BIRD") or nonempty_dir(SAFENLIDB / "data" / "BIRD"),
        "cuda_gpu_visible": shutil.which("nvidia-smi") is not None,
        "llamafactory_cli_visible": shutil.which("llamafactory-cli") is not None,
    }
    py_packages = detect_python_packages(["torch", "transformers", "vllm"])
    required.update({f"python_package_{name}": present for name, present in py_packages.items()})
    missing_gate_requirements = [name for name, ok in required.items() if not ok]
    resource_gate_open = not missing_gate_requirements
    return {
        "name": "SAFENLIDB",
        "upstream": git_info(SAFENLIDB),
        "included_shieldsql_case_count": count_json(SAFENLIDB / "evaluate" / "ShieldSQL" / "RS++" / "test++.json"),
        "syntax_checks": shell_syntax([p for p in scripts if p.suffix == ".sh"]),
        "required_resources": required,
        "resource_gate_open": resource_gate_open,
        "gate_status": "ready_for_official_full_chain" if resource_gate_open else "resource_gated_external_requirements_missing",
        "missing_gate_requirements": missing_gate_requirements,
        "official_commands": [
            "cd external_baselines/SAFENLIDB",
            "python3.9 -m venv .venv-safenlidb",
            "source .venv-safenlidb/bin/activate",
            "pip install -r requirements.txt",
            "mount/download OmniSQL, SecureSQL, Spider, and BIRD under the paths expected by DB_prepare scripts",
            "python DB_prepare/extract_db_ids_json.py",
            "python DB_prepare/omni.py",
            "bash data_synthesis/A_safe_condition/A_safe_condition.sh",
            "bash data_synthesis/B_sql_construction/B_sql.sh",
            "bash data_synthesis/C_NL_question_syn/C_question.sh",
            "bash data_synthesis/D_Gen_COT/D_sql_cot.sh",
            "bash data_synthesis/E_secure_COT/E_secure_cot.sh",
            "bash train/SFT/sft.sh",
            "bash train/Inference/beam_infer.sh",
            "bash train/APO/APO.sh",
            "bash evaluate/scrpit/infer.sh",
            "python evaluate/SecureSQL/ex/exa.py",
            "python evaluate/ShieldSQL/ex/exa.py",
            "bash evaluate/scrpit/prepare.sh",
            "python evaluate/SecureSQL/RS/RS_.py",
            "python evaluate/ShieldSQL/RS++/RS_++.py",
        ],
        "paper_release_policy": "Report included ShieldSQL diagnostics as self-contained official-subtask evidence; report full SFT/APO retraining only after the resource gate opens and the official training/evaluation chain completes.",
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path, payload):
    lines = [
        "# Official Upstream Baseline Preflight",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Host: {payload['environment']['platform']}",
        f"- Python: {payload['environment']['python_version']}",
        "",
        "This audit is intentionally strict: a baseline's official full-chain resource gate is open only when the upstream command chain can execute with its required datasets, credentials, runtime, and training hardware.",
        "",
    ]
    for baseline in payload["baselines"]:
        lines.extend(
            [
                f"## {baseline['name']}",
                "",
                f"- Repository: {baseline['upstream']['remote']}",
                f"- Commit: `{baseline['upstream']['commit']}`",
                f"- Resource gate open: {baseline['resource_gate_open']}",
                f"- Gate status: `{baseline['gate_status']}`",
                f"- Case count: {baseline.get('official_case_count', baseline.get('included_shieldsql_case_count'))}",
                "",
                "### Required Resources",
                "",
                "| Resource | Status |",
                "|---|---:|",
            ]
        )
        for key, ok in baseline["required_resources"].items():
            lines.append(f"| `{key}` | {'OK' if ok else 'MISSING'} |")
        lines.extend(["", "### Missing Gate Requirements", ""])
        if baseline["missing_gate_requirements"]:
            lines.extend([f"- `{b}`" for b in baseline["missing_gate_requirements"]])
        else:
            lines.append("- None; official upstream execution can proceed.")
        lines.extend(["", "### Official Command Chain", "", "```bash"])
        lines.extend(baseline["official_commands"])
        lines.extend(["```", "", f"Release policy: {baseline['paper_release_policy']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    payload = {
        "generated_at": deterministic_generated_at(),
        "environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cwd": "public_artifact",
            "conda_visible": shutil.which("conda") is not None,
            "nvidia_smi_visible": shutil.which("nvidia-smi") is not None,
        },
        "baselines": [autolink_preflight(), safenlidb_preflight()],
    }
    write_json(OUT / "official_upstream_preflight.json", payload)
    write_markdown(OUT / "OFFICIAL_UPSTREAM_REPRODUCTION_PREFLIGHT.md", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
