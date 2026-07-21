# release Strongest-Model Complete-Contract Results

The end-of-contract transport canary passes 2/2 for each model before any
benchmark request. GPT-5.5's two earlier quote-only diagnostics are excluded
because that diagnostic conflicted with the mandatory refusal policy; raw
responses and the amendment are retained.

All model rows use the identical MultiGov-200 sample and complete release contract.

| Model | Joint | Ref.P | Ref.R | Prompt tokens/case | Mean latency | Errors |
|---|---:|---:|---:|---:|---:|---:|
| deepseek-3.2 | 0.865 | 0.758 | 1.000 | 132,336 | 38.05 s | 27 |
| claude-opus-4-6 | 0.985 | 0.960 | 1.000 | 141,016 | 9.10 s | 3 |
| gpt-5.5 | 1.000 | 1.000 | 1.000 | 115,363 | 7.24 s | 0 |
| CaliberGraph reference | 1.000 | 1.000 | 1.000 | 0 | 0.058 ms | 0 |

Opus's three failures are false refusals. Two interpret
`coverage_required=false` and zero bindings as evidence that a metric is
unanswerable, although release defines this state as an inactive coverage check;
one claims a present metric is absent. This is a typed-state interpretation
failure, not candidate retrieval.

The strongest model closes the accuracy gap on this sample. The surviving
contribution is therefore not a universal accuracy claim: it is deterministic
contract enforcement, zero plan-time calls, explicit witness/certificate
output, and stability independent of model and long-context transport.
