# Label Quality Audit

- Candidate cases before conflict withholding: 159
- Released scored cases: 157
- Withheld label-conflict cases: 2
- Metrics: 15
- Dimensions: 4
- Refusal cases: 8
- Duplicate normalized query groups: 23
- Conflicting duplicate groups: 0
- Privacy scan passed: True

Conflict policy: any duplicate public query with incompatible gold action/metric/dimension/time/caliber labels is withheld from the scored public split.
Prediction protocol: `source_candidates_public_desensitized.jsonl` is label-free; labels are separated into `source_candidate_labels_public_desensitized.jsonl` and scorer-only `gold_labels.jsonl`; `blind_cases.jsonl` removes labels and private trace digests.
