# release Public Strongest-Control Analysis

Validator-feedback replanning is a complete runnable baseline, not an ablation. Intervals use deterministic cluster bootstrap; p-values use exact paired McNemar tests.

| Layer | N | Round 0 | Replan final | Compiler | Delta | 95% cluster CI | Exact p | Calls/case |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| iowa | 32 | 0.812 | 1.000 | 1.000 | 0.000 | [0.000, 0.000] | 1 | 1.250 |
| govtwin | 159 | 0.780 | 0.981 | 1.000 | 0.019 | [0.000, 0.044] | 0.25 | 1.220 |
| multigov | 200 | 0.865 | 0.955 | 1.000 | 0.045 | [0.019, 0.075] | 0.00391 | 1.100 |
| ict | 157 | 0.771 | 0.879 | 1.000 | 0.121 | [0.070, 0.181] | 3.81e-06 | 1.166 |
