# Prompt Token Audit

Counts use `cl100k_base` over the released serialized input prompts. They exclude completions and hidden reasoning tokens.

| Mode | Single mean | Single p95 | Batch-10 amortized mean | Batch-10 p95 |
|---|---:|---:|---:|---:|
| llm_direct | 907.9 | 914.0 | 791.2 | 792.8 |
| llm_schema_rag | 491.3 | 597.0 | 372.7 | 412.9 |
| llm_graph_rag | 556.3 | 662.0 | 437.7 | 477.9 |
