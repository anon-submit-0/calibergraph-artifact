# Extended Runnable Controls

These controls close the strongest alternative explanations using stored raw
responses, portable scorers, and real engine logs. They are separate from the
deterministic benchmark rebuild because online model calls and MetricFlow have
additional dependencies.

| Directory | Evidence | Offline reproduction |
|---|---|---|
| `complete_contract_prompting/` | DeepSeek, 898 complete-contract calls | scorer, prompt/provenance audit |
| `strongest_model_prompting/` | Opus and GPT-5.5 on the same MultiGov-200 split | scorer and transport-canary audit |
| `validator_feedback_replanning/` | preregistered 391 plus full ICT extension | all rounds, violations, costs, paired tests |
| `validator_feedback_multigov_full/` | exhaustive MultiGov-510 repair loop | full paired and cluster-aware analysis |
| `metricflow_real_engine/` | 64 real `mf query` runs and nine probes | stored logs/results; engine rerun when installed |
| `human_label_validation/` | three anonymous practitioner sheets | Fleiss/Cohen agreement and all-disagreement sensitivity |
| `compiler_latency/` | 17,160 deterministic finalizations | replay and latency benchmark |
| `coverage_activity_analysis/` | headline cases split by active/inactive physical-coverage checks | released-trace stratification |
| `enterprise_aggregate_control/` | 159 correctness-only enterprise pairs | aggregate paired statistics only |

Run every key-free check from the public artifact root:

```bash
python3 extended_controls/complete_contract_prompting/run_h1.py crosscheck
python3 extended_controls/complete_contract_prompting/run_h1.py score
python3 extended_controls/complete_contract_prompting/audit_prompt_provenance.py
python3 extended_controls/strongest_model_prompting/run_h1_ext.py score
python3 extended_controls/validator_feedback_replanning/run_loop.py audit
python3 extended_controls/validator_feedback_replanning/run_loop.py compat
python3 extended_controls/validator_feedback_replanning/run_loop.py score
python3 extended_controls/validator_feedback_multigov_full/run_multigov_full.py audit
python3 extended_controls/validator_feedback_multigov_full/run_multigov_full.py score
python3 extended_controls/human_label_validation/recompute_iaa.py
python3 extended_controls/human_label_validation/run_disagreement_sensitivity.py
python3 extended_controls/compiler_latency/run_compiler_latency.py
python3 extended_controls/coverage_activity_analysis/recompute.py
python3 extended_controls/enterprise_aggregate_control/recompute.py
python3 extended_controls/verify_extended_controls.py
```

Stored online runs are immutable evidence. Re-running a proprietary model may
differ because providers can update deployments; no such rerun is required to
recompute the reported scores. Online scripts accept external endpoint/key
environment variables and contain no credential or internal endpoint.
