# Full-MultiGov Replan Extension

Frozen on 2026-07-12 before any call on the 310 extension cases.

## Motivation and scope

The source validator-replan protocol preregistered a 200/510 stratified sample.
After that result was known, this extension was added solely to remove the
sample-size mismatch from the overall comparison table. It changes no model,
prompt, parser, validator, repair limit, or scorer.

## Reuse rule

The 200 existing case histories are copied byte-for-byte from
`../validator_feedback_replanning/raw_responses/multigov_loop_raw.jsonl`; their
round-0 prompt hashes and every stored verdict have already passed the release
compatibility audit. The script then calls `deepseek-3.2` through llmhub
`gateway`, temperature 0, only for the remaining 310 blind cases. Duplicate
case IDs are forbidden. All 510 cases are scored together.

## Validator and outcomes

The gold-free validator executes closed vocabulary, refusal, allowed-grain,
finest-grain, caliber dependency, metric-specific physical coverage, temporal,
and policy checks through the released `ContractCompiler`. It may return at
round 0 or issue at most three feedback repairs. Missing/API/parse failures are
wrong; no response is imputed.

Primary outputs are round-0 and final joint accuracy, per-family accuracy,
online calls/tokens, validator-invisible residual errors, paired exact McNemar
against the released compiler reference, and a 10,000-replicate metric-group
cluster bootstrap interval (seed 20260711).
