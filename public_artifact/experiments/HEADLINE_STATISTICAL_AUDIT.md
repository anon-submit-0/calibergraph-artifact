# Headline Statistical Audit

Paired exact McNemar tests compare CaliberGraph with the SafeNLIDB-derived E3 protocol. Confidence intervals use 10,000 deterministic cluster bootstrap replicates.

| Dataset | N | Baseline | CaliberGraph | Difference | 95% cluster CI | Exact p |
|---|---:|---:|---:|---:|---|---:|
| IowaLiquor | 32 | 0.781 | 1.000 | 0.219 | [0.094, 0.375] | 0.0156 |
| MultiGov | 510 | 0.680 | 1.000 | 0.320 | [0.310, 0.329] | 1.71e-49 |
| IndustrialCaseText | 157 | 0.904 | 1.000 | 0.096 | [0.051, 0.147] | 6.1e-05 |
