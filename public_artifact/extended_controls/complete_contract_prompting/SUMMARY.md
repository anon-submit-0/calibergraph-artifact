# release Verbatim-Contract Results

All 898 cases completed with zero API or parse errors. Prompt provenance and
the mirrored scorer both pass exact audits.

| Layer | N | Joint | Metric | Dimension | Ref.P | Ref.R | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| Iowa | 32 | 0.875 | 0.969 | 0.875 | 0.875 | 1.000 | 4 |
| Chinook | 40 | 0.925 | 0.950 | 0.950 | 0.750 | 1.000 | 3 |
| GovTwin | 159 | 0.736 | 0.994 | 0.736 | 0.900 | 1.000 | 42 |
| MultiGov | 510 | 0.855 | 0.869 | 0.855 | 0.733 | 1.000 | 74 |
| IndustrialCaseText | 157 | 0.822 | 0.943 | 0.866 | 0.500 | 0.875 | 28 |
| **Micro** | **898** | **0.832** | - | - | - | - | **151** |

Mechanism observations:

- GovTwin retains 41 finest-grain violations among 149 answer predictions even
  though the hierarchy rule is mandatory in the prompt.
- MultiGov's complete 132k-provider-token prompt improves slightly over the old
  contract but still yields 74 errors; refusal recall is 1.0 while precision is
  0.733, showing over-refusal rather than missing safety.
- On the same MultiGov-200 sample, DeepSeek reaches 0.865, Opus 0.985 and
  GPT-5.5 1.000. The failure magnitude is therefore model-specific.

The result supports a bounded conclusion: a single prompt is not a stable
cross-model implementation of the contract. It does not support an intrinsic
LLM-impossibility claim.
