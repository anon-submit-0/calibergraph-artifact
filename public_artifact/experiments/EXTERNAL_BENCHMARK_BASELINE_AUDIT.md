# release External Benchmark and Baseline Alignment Audit

This historical release audit maps adjacent BI, reliability, and Text-to-SQL benchmarks to the MetricCaliberBench evidence boundary. release supplements it with executed Spider2-DBT, TrustSQL raw, DataBench, and MetricFlow evidence in EXTERNAL_EVIDENCE_SUMMARY.md.

## Benchmark Triage

| Benchmark | Role | Why relevant | Why not primary evidence yet | release paper action |
|---|---|---|---|---|
| BIS | external BI NL2SQL benchmark alignment | production BI questions rather than generic academic SQL only | does not directly release CaliberGraph-style metric-contract witness labels | discuss as closest external BI benchmark; use release DataBench/Spider2-DBT evidence as executed adjacent anchors |
| BI-Bench | end-to-end BI-system benchmark alignment | descriptive, diagnostic, predictive, and prescriptive BI query coverage | benchmarks BI system insight quality rather than typed metric-caliber witness conformance | use to position the BI system boundary and motivate broader evaluation |
| TrustSQL | answerability/refusal reliability baseline family | scores feasible SQL generation and infeasible-question abstention | refusal is one contract facet; it lacks denominator, grain, coverage, and metric-caliber witnesses | add as refusal/reliability comparison axis; release includes raw official scorer outputs |
| Spider 2.0 / Spider2-Lite | enterprise-scale schema/workflow diagnostic | real-world enterprise workflows over large schemas and warehouses | schema/workflow success does not define governed metric contracts or disclosure policy | retain as Text-to-SQL diagnostic, not the main metric-caliber benchmark |
| BIRD | existing SQL diagnostic already included | public SQL benchmark with aggregate queries and external knowledge | does not provide complete governance graph, refusal policy, or coverage contract | keep BIRD-MetricCaliber as plan-level diagnostic |

## Baseline Triage

| Baseline family | Role | Directness | release action |
|---|---|---|---|
| AutoLink | candidate-availability and schema-linking control | adjacent closest published family, not direct metric-caliber compiler | report evidence-labeled E3 candidate-linking diagnostics and resource-gated upstream audit |
| SafeNLIDB | security/refusal guard control | adjacent safety system, not denominator/grain witness compiler | report ShieldSQL guard transfer and resource-gated upstream audit |
| TrustSQL-style abstention | public answerability/reliability control | direct for refusal policy, partial for metric-caliber | map as refusal baseline family; release includes TrustSQL raw official scorer outputs |
| CHESS / MAC-SQL / DIN-SQL | strong NL2SQL agent baselines | strong SQL baselines, indirect for governed metric contracts | rank as next SQL-planner controls with oracle-candidate finalizer interface |
| Semantic-layer validator / SQL post-hoc validator | fully runnable non-witness controls | direct mechanism controls under released contracts | keep as primary reproducible non-witness comparisons |

## Decision for the Submission Text

- Numerical result tables remain limited to released/rebuildable MetricCaliberBench splits and evidence-labeled controls.
- External benchmarks are cited and mapped to specific evaluation roles, avoiding false SOTA claims.
- release executes adjacent checks for Spider2-DBT, TrustSQL raw, DataBench, and dbt MetricFlow; those checks remain boundary evidence, not full NL2Metric-Caliber witness benchmarks.

## Source URLs

- https://arxiv.org/abs/2410.22925
- https://aclanthology.org/2025.acl-industry.90/
- https://arxiv.org/abs/2403.15879
- https://arxiv.org/abs/2411.07763
- https://bird-bench.github.io/
- https://ojs.aaai.org/index.php/AAAI/article/view/40672
- https://ojs.aaai.org/index.php/AAAI/article/view/40484
