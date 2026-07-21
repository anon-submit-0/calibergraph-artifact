# Verbatim-Contract Instructed-Execution Protocol

## Question

Does a single LLM call execute the complete released governance contract when
that contract is reproduced verbatim and every policy is stated as mandatory?
This tests prompt emulation, not retrieval failure.

## Fixed setup

- Model/channel: `deepseek-3.2` through llmhub `gateway`.
- Temperature 0, `max_tokens=4000`, one request per blind case.
- Layers: Iowa 32, Chinook 40, GovTwin 159, MultiGov 510, ICT 157
  (898 total).
- Output: one JSON plan; missing/API/parse failures score as wrong.
- Scoring mirrors released evaluators and was cross-checked exactly against
  every released baseline row before interpretation.

The release prompts include all released contract files. In particular, MultiGov
adds `contract_profile.json`, 178 metric-specific coverage bindings and 189
physical coverage rows to the earlier semantic catalogs. Its system prompt is
375,318 bytes (SHA-256
`2ee068724803108443db6c4f754966358fac8548edcbcfbdd5e2b57626b89966`).
Blind cases and scorer-only gold remain separate.

## Migration rule

Frozen predecessor response histories for Chinook and ICT are reused only because the
rebuilt prompt and every per-case prompt SHA are identical. Iowa and GovTwin
are rerun after adding complete profile/schema files. MultiGov is rerun on all
510 cases. Older incomplete-contract outputs remain author-side and are not
included or scored. The executable provenance audit must pass before scores are used.

## Interpretation

Results are model- and contract-specific. Failure does not imply that all LLMs
are incapable; the separate strongest-model protocol tests that objection.
Success does not supply a by-construction witness unless the output is compiled
and checked. The comparison therefore measures accuracy, conformance failure
types, context cost, latency, and transport reliability.
