# release External Anchor Experiment Audit

This historical release audit upgrades external alignment from prose-only triage to key-free anchor auditing. Counts are computed from released files. release supplements it with executed Spider2-DBT, TrustSQL raw, DataBench, dbt MetricFlow, and LightRAG-preflight evidence summarized in EXTERNAL_EVIDENCE_SUMMARY.md.

## Released Anchor Counts

| Anchor | N | Status | Released path |
|---|---|---|---|
| AutoLink Spider2-Lite records | 547 | present | external_baselines/AutoLink/run/spider2_data.json |
| SafeNLIDB ShieldSQL records | 540 | present | external_baselines/SAFENLIDB/evaluate/ShieldSQL/RS++/test++.json |
| BIRD-MetricCaliber diagnostic cases | 206 | present | public_benchmark/bird_metric_caliber/bird_metric_cases.jsonl |
| Chinook-MetricCaliber scored cases | 40 | present | public_benchmark/data/chinook_metric_cases.jsonl |
| IowaLiquor-MetricCaliber scored cases | 32 | present | public_benchmark/iowa_liquor_metric_caliber/test_cases.jsonl |
| GovTwin-MetricCaliber base cases | 159 | present | public_benchmark/govtwin_metric_caliber/test_cases.jsonl |
| GovTwin-MetricCaliber LLM paraphrase cases | 159 | present | public_benchmark/govtwin_metric_caliber/test_cases_llm_paraphrased.jsonl |
| GovTwin-MetricCaliber perturbation cases | 468 | present | public_benchmark/govtwin_metric_caliber/test_cases_perturbed.jsonl |
| MultiGov-MetricCaliber scored cases | 510 | present | public_benchmark/multigov_metric_caliber/gold_labels.jsonl |
| IndustrialCaseText scored cases | 157 | present | public_benchmark/industrial_case_text_metric_caliber/gold_labels.jsonl |

- Public scored MetricCaliber cases counted here: 1525.
- External diagnostic or official-subtask records counted here: 1293.

## Failure-Family Surface in Released Public Splits

| Dataset | Family/action key | N |
|---|---|---|
| iowa | answer | 25 |
| iowa | refuse | 7 |
| industrial_case_text | flat_metric | 84 |
| industrial_case_text | policy_refusal | 8 |
| industrial_case_text | ranking_topk | 30 |
| industrial_case_text | single_dimension | 35 |
| multigov | answerable_direct | 115 |
| multigov | denominator_caliber | 29 |
| multigov | finest_grain_trap | 163 |
| multigov | policy_refusal | 184 |
| multigov | temporal_anchor | 19 |

## Baseline Capability Matrix

| Baseline | Role | metric identity | aggregate caliber | dimension grain | temporal/coverage | refusal/disclosure | release evidence |
|---|---|---|---|---|---|---|---|
| AutoLink-derived E3 | closest schema/candidate-linking family | mechanism-present candidate recall | N/A-by-design after candidate discovery | N/A-by-design finest-grain policy absent | N/A-by-design coverage witness absent | N/A-by-design policy witness absent | fixed AutoLink snapshot plus 547 Spider2-Lite records; MetricCaliber candidate diagnostics |
| SafeNLIDB-derived E3 guard | closest safety/refusal family | N/A-by-design | N/A-by-design | N/A-by-design | N/A-by-design | mechanism-present but insufficient for metric caliber | fixed SafeNLIDB snapshot plus 540 ShieldSQL records; refusal-transfer diagnostics |
| Oracle-candidate prompting | perfect-linking stress control | oracle supplied | empirical prompt finalization | empirical prompt finalization | empirical prompt finalization | empirical prompt finalization | released MetricCaliberBench scorer outputs |
| LLM Schema-RAG / GraphRAG prompt controls | rules-in-context control | mechanism-present retrieval | mechanism-present but no witness | mechanism-present but no finest-grain resolver | mechanism-present but no coverage proof | partial policy visibility | released public predictions and mechanism audit |
| Semantic-layer validator | metrics-as-code style validation control | mechanism-present | mechanism-present validation only | mechanism-present validation only | partial coverage validation | partial policy validation | fully runnable key-free mechanism audit |
| SQL post-hoc validator | static/execution validation control | N/A-by-design | partial SQL-shape validation | partial SQL-shape validation | partial physical-coverage validation | N/A-by-design unless policy encoded | fully runnable key-free mechanism audit |
| Open SQL end-to-end | executable SQL agent control | empirical SQL planning | empirical SQL planning | empirical SQL planning | empirical SQL planning | implicit/weak refusal | IowaLiquor SQLite execution plus MetricCaliber scoring |
| TrustSQL/SecureSQL-style abstention | public abstention and safety anchor | N/A-by-design | N/A-by-design | N/A-by-design | physical feasibility only | direct refusal/disclosure anchor | TrustSQL mapped in audit; SafeNLIDB ShieldSQL files countable in artifact |
| dbt MetricFlow validator | third-party semantic-layer validator control | mechanism-present in release MetricFlow validator control | direct metric expression validation | limited by dbt semantic manifest | limited time-spine/as-of support | N/A-by-design | release adds dbt MetricFlow validation and Spider2-DBT dbt-parse audit; not a Spider-Agent leaderboard claim |
| LightRAG governed-KG control | graph-in-prompt preflight control | mechanism-present retrieval | rules retrieved, not certified | rules retrieved, not certified | rules retrieved, not certified | rules retrieved, not certified | release adds runnable LightRAG custom-KG preflight; no accuracy table because LLM/embedding/query policy are not frozen |
| CaliberGraph | typed witness compiler | compiled witness | compiled witness | compiled finest-grain witness | compiled coverage/as-of witness | compiled refusal/disclosure witness | released scorer outputs, ablations, certificates, and audits |

## Reviewer-Facing Consequence

- AutoLink and SafeNLIDB are no longer treated as vague named baselines: the artifact exposes their fixed snapshots, included official records, and which failure families are outside their design scope.
- The paper's numerical tables remain limited to released scorer outputs; release reports adjacent executed evidence separately from full NL2Metric-Caliber witness scoring.
- This audit supports the main mechanism claim: after candidate or safety mechanisms are available, aggregate caliber, finest-grain policy, coverage/as-of binding, and governed refusal still require a typed witness.

## release Executed Adjacent Evidence

- Spider2-DBT dbt-parse audit over public projects.
- TrustSQL raw official scorer outputs for answerability/refusal controls.
- DataBench fixed public subset audit.
- dbt MetricFlow validator control.
- LightRAG custom-KG preflight, explicitly excluded from main accuracy tables.
