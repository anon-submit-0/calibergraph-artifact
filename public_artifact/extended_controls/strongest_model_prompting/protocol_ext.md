# Strongest-Model Complete-Contract Protocol

Status: frozen before benchmark calls on 2026-07-12. The protocol, transport
canaries, raw responses, usage records, and scorer outputs are released together.

## Question

Can the strongest available instruction-following models execute the complete
release MultiGov governance contract from prompt text alone? This is an adversarial
control, not an attempt to make weaker-model errors look universal.

## Models and llmhub channels

- `gpt-5.5` through `gpt-provider` (`GPT_API_KEY`).
- `claude-opus-4-6` through `opus-provider` (`OPUS_API_KEY`).

Temperature is 0 and `max_tokens=4000`. Keys are read at runtime from the
llmhub environment and never written to any artifact.

## Data and fixed sample

The target is release `MultiGov-MetricCaliber`. The system prompt reproduces, in
order, `contract_profile.json`, domain/metric/dimension catalogs,
`governance_edges.jsonl`, `policy_catalog.jsonl`,
`metric_coverage_bindings.jsonl`, and `physical_coverage.jsonl`. The saved
prompt is approximately 375k characters; its SHA-256 is recorded per response.

We use the immutable 200-case sample generated with seed `20260711` and the
predeclared family allocation 45/11/64/72/8 for direct, denominator, grain,
policy-refusal, and temporal cases. Sampling uses blind cases only.

## Transport canary

No benchmark call may run until two canaries pass for the exact model/channel.
The canary is a policy-valid no-metric request, so the model must return the
normal refusal schema. Its `reason` must also reproduce the `coverage_id` from
the first row of the final contract file, `physical_coverage.jsonl`. This tests
visibility of the end of the long system prompt.

The first GPT-5.5 diagnostic used a quote-only canary that conflicted with the
system's mandatory refusal rule; both raw failures are retained and excluded.
Canary v2 was specified before any benchmark call and resolves only that
diagnostic conflict. It does not change benchmark prompts, cases, parsing, or
scoring.

## Parsing and scoring

Parsing, normalization, joint metric+dimension scoring, refusal metrics,
Wilson intervals, and conformance checks are imported from the release H1 runner.
Missing/API/parse failures score as wrong. Raw responses and usage are stored;
no result is imputed. CaliberGraph's fixed-contract score is a deterministic
reference, not a model output.

## Interpretation rule

If a strongest model reaches or approaches 1.0, the paper must not claim that
prompt execution is intrinsically incapable. The remaining distinction is
by-construction contract conformance, zero online finalization calls, stable
behavior across models/transports, and explicit certificates. If errors remain,
they may support a model- and contract-specific reliability claim only.
