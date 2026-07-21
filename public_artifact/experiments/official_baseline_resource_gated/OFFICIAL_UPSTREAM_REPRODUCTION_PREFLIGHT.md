# Official Upstream Baseline Preflight

- Generated: 2026-07-08T00:00:00+00:00
- Host: macOS-15.0-arm64-arm-64bit
- Python: 3.9.6

This audit is intentionally strict: a baseline's official full-chain resource gate is open only when the upstream command chain can execute with its required datasets, credentials, runtime, and training hardware.

## AutoLink

- Repository: https://github.com/wzy416/AutoLink.git
- Commit: `26c723158445d5c831290315c9a93ba76eb5bd0e`
- Resource gate open: False
- Gate status: `resource_gated_external_requirements_missing`
- Case count: 547

### Required Resources

| Resource | Status |
|---|---:|
| `repo_exists` | OK |
| `requirements_txt` | OK |
| `main_sh` | OK |
| `sql_gen_sh` | OK |
| `spider2_data_json` | OK |
| `spider2_lite_resource_dir` | MISSING |
| `bigquery_credentials_dir` | MISSING |
| `snowflake_credential_dir` | MISSING |
| `api_key_configured_in_main_sh` | MISSING |
| `api_base_url_configured_in_main_sh` | MISSING |

### Missing Gate Requirements

- `spider2_lite_resource_dir`
- `bigquery_credentials_dir`
- `snowflake_credential_dir`
- `api_key_configured_in_main_sh`
- `api_base_url_configured_in_main_sh`

### Official Command Chain

```bash
cd external_baselines/AutoLink
python3 -m venv .venv-autolink
source .venv-autolink/bin/activate
pip install -r requirements.txt
cp -R /path/to/Spider2/spider2-lite/resource run/resource
install BigQuery credentials under run/bigquery_credentials
install Snowflake credentials under run/snowflake_credential
set OPENAI_API_KEY and OPENAI_BASE_URL in run/main.sh and run/sql_gen.sh
cd run && bash main.sh && bash sql_gen.sh
```

Release policy: Use complete official upstream execution only after the resource gate opens; before that, main result tables use released runnable protocols and the official chain is reported as a resource-gated run contract.

## SAFENLIDB

- Repository: https://github.com/tom68-ll/SAFENLIDB.git
- Commit: `0ad16d8b1e6cb3e533fc6c5433a3dcd575967b08`
- Resource gate open: False
- Gate status: `resource_gated_external_requirements_missing`
- Case count: 540

### Required Resources

| Resource | Status |
|---|---:|
| `repo_exists` | OK |
| `requirements_txt` | OK |
| `shieldsql_test_present` | OK |
| `omnisql_database_present` | MISSING |
| `securesql_dataset_present` | MISSING |
| `spider_database_present` | MISSING |
| `bird_database_present` | MISSING |
| `cuda_gpu_visible` | MISSING |
| `llamafactory_cli_visible` | MISSING |
| `python_package_torch` | MISSING |
| `python_package_transformers` | MISSING |
| `python_package_vllm` | MISSING |

### Missing Gate Requirements

- `omnisql_database_present`
- `securesql_dataset_present`
- `spider_database_present`
- `bird_database_present`
- `cuda_gpu_visible`
- `llamafactory_cli_visible`
- `python_package_torch`
- `python_package_transformers`
- `python_package_vllm`

### Official Command Chain

```bash
cd external_baselines/SAFENLIDB
python3.9 -m venv .venv-safenlidb
source .venv-safenlidb/bin/activate
pip install -r requirements.txt
mount/download OmniSQL, SecureSQL, Spider, and BIRD under the paths expected by DB_prepare scripts
python DB_prepare/extract_db_ids_json.py
python DB_prepare/omni.py
bash data_synthesis/A_safe_condition/A_safe_condition.sh
bash data_synthesis/B_sql_construction/B_sql.sh
bash data_synthesis/C_NL_question_syn/C_question.sh
bash data_synthesis/D_Gen_COT/D_sql_cot.sh
bash data_synthesis/E_secure_COT/E_secure_cot.sh
bash train/SFT/sft.sh
bash train/Inference/beam_infer.sh
bash train/APO/APO.sh
bash evaluate/scrpit/infer.sh
python evaluate/SecureSQL/ex/exa.py
python evaluate/ShieldSQL/ex/exa.py
bash evaluate/scrpit/prepare.sh
python evaluate/SecureSQL/RS/RS_.py
python evaluate/ShieldSQL/RS++/RS_++.py
```

Release policy: Report included ShieldSQL diagnostics as self-contained official-subtask evidence; report full SFT/APO retraining only after the resource gate opens and the official training/evaluation chain completes.
