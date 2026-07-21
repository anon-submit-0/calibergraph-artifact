# release External Source Manifest

release keeps the submission artifact compact. It includes derived evidence, fixed
commands, and small public subsets, but it does not bundle multi-GB upstream
repositories or raw benchmark database archives.

## Fixed Upstream Sources

| Source | Commit / version | Role |
|---|---|---|
| Spider2 | `01a4c67c1e3f6ab9032716b050a927abbb245f65` | Spider2-DBT dbt project semantic audit |
| TrustSQL | `b7bc643a62545099748d3d18d0651cde51ae87a4` | Raw answerability/refusal official scoring |
| LightRAG | `fedd95ce7db0d69d12923177c7f0604b0b23655b` | Custom-KG preflight only |
| dbt MetricFlow | `metricflow==0.209.0`, `dbt-metricflow==0.11.0` | Metrics-as-code validator control |
| DataBench | HuggingFace `cardiffnlp/databench` subset | Public row-level table QA audit |

## Rebuild Commands

Spider2-DBT audit:

```bash
git clone --depth 1 --filter=blob:none https://github.com/xlang-ai/Spider2.git Spider2
cd Spider2
git checkout 01a4c67c1e3f6ab9032716b050a927abbb245f65
# Run dbt parse over spider2-dbt/examples/*/dbt_project.yml.
```

TrustSQL raw official scoring:

```bash
git clone --depth 1 https://github.com/glee4810/TrustSQL.git TrustSQL
cd TrustSQL
git checkout b7bc643a62545099748d3d18d0651cde51ae87a4
python3 -m pip install gdown func_timeout
python3 -m gdown -O trustsql_dataset.zip --fuzzy \
  "https://drive.google.com/file/d/19IpLSc2QncO2273E8z-lvU2ME9wEHIan/view?usp=sharing"
unzip trustsql_dataset.zip -x "__MACOSX/*"
python3 evaluate.py --data_file dataset/atis/atis_test.json \
  --pred_file <prediction.json> --db_path dataset/atis/atis.sqlite
```

DataBench subset:

```bash
python3 - <<'PY'
import requests
base = "https://huggingface.co/datasets/cardiffnlp/databench/resolve/main"
for ds in ["001_Forbes","002_Titanic","004_Taxi","007_Fifa","008_Tornados","009_Central","010_ECommerce"]:
    for name in ["all.parquet","qa.parquet","sample.parquet","info.yml"]:
        url = f"{base}/data/{ds}/{name}"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
PY
```

MetricFlow validator:

```bash
cd public_artifact/external_sources/metricflow_duckdb_project
dbt parse --profiles-dir . --quiet
mf validate-configs --skip-dw
```

LightRAG preflight:

```bash
git clone --depth 1 https://github.com/HKUDS/LightRAG.git LightRAG
cd LightRAG
git checkout fedd95ce7db0d69d12923177c7f0604b0b23655b
# Use Python >=3.10; release used Python 3.12.13 and dummy embedding/LLM functions
# for import, storage initialization, and custom KG insertion only.
```

## Evidence Boundary

`experiments/EXTERNAL_EVIDENCE_SUMMARY.md` is the reviewer-facing compact
summary. These external runs strengthen external validity, but they are not
renamed as full NL2Metric-Caliber benchmarks because they do not all expose the
governed metric catalog, coverage witness, finest-grain policy, and refusal
labels required by MetricCaliberBench.
