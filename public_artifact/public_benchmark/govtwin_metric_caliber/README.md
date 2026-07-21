# GovTwin-MetricCaliber

GovTwin-MetricCaliber is a public anonymized semantic twin of a private enterprise governance graph.
Under the released-artifact threat model, reviewers receive only the synthetic graph and not the private source snapshot or private-to-public mapping. The release preserves task structure for NL2Metric-Caliber evaluation while replacing private names, aliases, raw natural-language requests, physical tables, columns, owner fields, timestamps, and document tokens.

## Files

- `metric_catalog.jsonl`: public synthetic metric catalog.
- `dimension_catalog.jsonl`: public synthetic dimensions and hierarchy.
- `governance_edges.jsonl`: public typed semantic edges.
- `policy_catalog.jsonl`: public refusal and finest-grain policies.
- `test_cases.jsonl`: public synthetic NL2Metric-Caliber test cases.
- `test_cases_perturbed.jsonl`: deterministic perturbation cases derived from the public base cases.
- `test_cases_llm_paraphrased.jsonl`: fixed LLM-paraphrase split generated only from public synthetic queries.
- `results/`: deterministic evaluation outputs.

## Release Boundary

No raw enterprise rows, raw user queries, product/customer/employee identifiers, physical table names, physical column names, or private-to-public mapping are included.

## Census

- Metrics: 18
- Dimensions: 5
- Governance edges: 102
- Base test cases: 159
- Perturbation test cases: 468
- LLM-paraphrase test cases: 159

## Main Results

- Base CaliberGraph joint accuracy: 1.000.
- LLM-paraphrase CaliberGraph joint accuracy: 1.000.
- Perturbation CaliberGraph joint accuracy: 0.987.
- Base AutoLink-derived E3 joint accuracy: 0.679.
- Base SafeNLIDB-derived E3 joint accuracy: 0.736.
- Base oracle-candidate prompt joint accuracy: 0.736.

## Reproduction

```bash
python3 scripts/build_govtwin_llm_paraphrases.py --reuse
python3 scripts/run_govtwin_eval.py
```

The released LLM-paraphrase split is fixed. Regenerating paraphrases requires an LLM route and should be treated as a new robustness split. Evaluation of the released files is deterministic.
