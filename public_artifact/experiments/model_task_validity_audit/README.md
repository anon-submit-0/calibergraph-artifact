# release Independent Label Adjudication Audit

Optional LLM-based adjudication over released public labels. The adjudicator sees catalogs, adjudication rules, queries, and gold labels, then judges whether each label is defensible. It is not a human business-annotator replacement; it is a reproducible sanity check against obviously self-serving labels.

| Model | Parsed cases | Accept | Question | Reject | Accept rate |
|---|---:|---:|---:|---:|---:|
| gpt-provider/gpt-5.5 | 30 | 30 | 0 | 0 | 1.000 |

Raw prompts and model outputs are stored in this folder; no API keys are stored.
