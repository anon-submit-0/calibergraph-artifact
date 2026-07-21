# release External Evidence Summary

release reports executed external evidence for Spider2-DBT, TrustSQL raw, DataBench, and dbt MetricFlow. LightRAG is reported as a runnable preflight only because a fair numeric baseline requires frozen LLM, embedding, and query-policy services.

## Executed Evidence

- Spider2-DBT: 69 projects; 46 parse-pass / 23 parse-fail; 2046 YAML; 10007 SQL; 3589 model entries.
- DataBench subset: 7 public tables; 145 QA cases; 265464 table rows.
- dbt MetricFlow: `mf, version 0.11.0`; return code 0.
- LightRAG preflight: runtime pass; custom KG insert pass.

## TrustSQL Raw Official Scoring

| Dataset | Mode | Return | RS(0) total | RS(10) total |
|---|---|---:|---:|---:|
| atis | gold_oracle | 0 | 100.00 | 100.00 |
| atis | always_abstain | 0 | 50.00 | 50.00 |
| atis | unsafe_always_answer | 0 | 50.00 | -450.00 |
| advising | gold_oracle | 0 | 100.00 | 100.00 |
| advising | always_abstain | 0 | 50.00 | 50.00 |
| advising | unsafe_always_answer | 0 | 50.00 | -450.00 |
| ehrsql | gold_oracle | 0 | 90.36 | -6.00 |
| ehrsql | always_abstain | 0 | 50.00 | 50.00 |
| ehrsql | unsafe_always_answer | 0 | 40.36 | -556.00 |
| spider | gold_oracle | 0 | 95.35 | 48.86 |
| spider | always_abstain | 0 | 50.00 | 50.00 |
| spider | unsafe_always_answer | 0 | 45.35 | -501.14 |
