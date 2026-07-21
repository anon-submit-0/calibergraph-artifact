# release Executable-Guarantee Comparison

This reviewer-facing matrix clarifies the novelty boundary. A check mark means the method class provides an executable guarantee under the NL2Metric-Caliber interface, not merely that it can retrieve or describe relevant text.

| Method class | Metric identity | Denominator/scope | Finest grain | Physical coverage | Disclosure/refusal | Failure certificate |
|---|---|---|---|---|---|---|
| Text-to-SQL execution | partial | no | no | partial | no | SQL error only |
| AutoLink-style schema linking | candidate recall | no | no | partial | no | no |
| SafeNLIDB-style safety guard | partial | no | no | no | safety-focused | safety label |
| Prompt GraphRAG | text context | text context | text context | text context | text context | no executable proof |
| Semantic-layer validator | yes | partial | validates only | partial | yes | rejects invalid candidates |
| SQL post-hoc validator | partial | partial | validates only | SQL-level only | yes | rejects invalid SQL plans |
| CaliberGraph witness compiler | yes | yes | yes | yes | yes | typed missing-witness certificate |

The release mechanism audit tests the two strongest non-witness controls (`semantic_layer_validator` and `posthoc_answerability_validator`) on released public artifacts.
