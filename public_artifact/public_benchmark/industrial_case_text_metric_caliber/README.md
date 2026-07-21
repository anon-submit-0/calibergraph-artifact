# IndustrialCaseText-MetricCaliber

A public desensitized release of real industrial NL2Metric-Caliber case text and labels.
It releases natural query text, anonymized labels, blind prediction input, scorer-only labels, catalogs, and privacy/label audits.

It does not release raw enterprise rows, private table/column names, private metric ids, private domain ids, source case ids, or private-to-public mappings.
`source_candidates_public_desensitized.jsonl` and `experiments/enterprise_metric_cases_public_desensitized.jsonl` are label-free source-candidate files for rebuild and inspection.
`source_candidate_labels_public_desensitized.jsonl`, `gold_labels.jsonl`, and `experiments/enterprise_metric_cases_public_desensitized_labels.jsonl` contain labels for rebuild/scoring only and are not legal prediction inputs.
`cases.jsonl` is a labeled inspection/rebuild convenience file, not a legal prediction input.

Run:

```bash
python3 scripts/build_industrial_case_text_metric_caliber.py
python3 scripts/run_industrial_case_text_eval.py
```

Legal prediction input is `blind_cases.jsonl` plus public catalogs/policies. The evaluator uses `gold_labels.jsonl` only for scoring.

See `LABEL_POLICY.md` for the public action, metric, dimension, time, caliber, and duplicate-conflict labeling rules.
