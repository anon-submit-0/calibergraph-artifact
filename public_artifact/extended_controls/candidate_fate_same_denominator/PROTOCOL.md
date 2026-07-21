# Same-denominator candidate-fate diagnostic

## Question

After the intended metric candidate is available, how many released
IndustrialCaseText answerable requests remain wrong under the paper's primary
action/metric/dimension scorer?

## Frozen inputs

- `../candidate_budget_sensitivity/raw_responses/k_{1,3,5,10}.jsonl`
- `../../public_benchmark/industrial_case_text_metric_caliber/gold_labels.jsonl`

The four raw-response arms contain 157 records each. Gold is used only after
inference to select the 149 cases whose released action is `answer` and to
score the stored final prediction. No model or retrieval call is made.

## Mutually exclusive fates

1. `candidate_missing`: the released expected metric id is absent from the
   stored `retrieved_metric_ids`.
2. `candidate_present_final_wrong`: the candidate is present, but the final
   stored prediction fails exact action/metric/dimension joint scoring.
3. `candidate_present_joint_correct`: the candidate is present and the final
   stored prediction passes that metric+dimension scorer.

Candidate absence takes precedence in the partition. The output additionally
reports the full candidate-presence by joint-correctness cross-tab so this
choice is auditable. The figure-facing partition is stricter: its green segment
also requires the stored final validator verdict to pass. It must be labeled
`M+D correct + validator pass`, not generic `contract correct`, because the LLM
record does not predict every gold caliber or policy slot.

## Reproduce

From `public_artifact`:

```bash
python3 extended_controls/candidate_fate_same_denominator/recompute_candidate_fate.py
```

Outputs include exact counts, all 596 per-case assignments, and SHA-256 hashes
for every frozen input. The diagnostic does not claim that the primary scorer
measures every witness slot; it isolates the post-retrieval error under the
same outcome already used in the paper.
