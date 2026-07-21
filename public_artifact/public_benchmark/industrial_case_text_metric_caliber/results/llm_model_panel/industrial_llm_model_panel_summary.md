# IndustrialCaseText LLM Model Panel

Predictions use `blind_cases.jsonl`; `gold_labels.jsonl` is used only for scoring.

| Channel | Model | Mode | N | Full Acc. | Action Acc. | Metric Acc. | Dim. Acc. | Ref.P | Ref.R | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| deepseek | deepseek-chat | llm_graph_rag | 60 | 0.933 | 0.983 | 0.967 | 0.967 | 1.000 | 0.875 | ok |
| deepseek | deepseek-reasoner | llm_graph_rag | 60 | 0.917 | 0.917 | 0.917 | 0.983 | 0.636 | 0.875 | ok |
| deepseek | deepseek-v4-pro | llm_graph_rag | 60 | 0.917 | 0.917 | 0.917 | 0.983 | 0.615 | 1.000 | ok |
| gateway | deepseek-3.2 | llm_graph_rag | 60 | 0.933 | 0.933 | 0.933 | 0.983 | 0.700 | 0.875 | ok |
| gateway | glm-5 | llm_graph_rag | 60 | 0.967 | 0.967 | 0.967 | 0.983 | 0.875 | 0.875 | ok |
| gateway | minimax-m2.5 | llm_graph_rag | 60 | 0.933 | 0.950 | 0.933 | 1.000 | 0.778 | 0.875 | ok |
| gateway | qwen3-coder-next | llm_graph_rag | 60 | 0.917 | 0.917 | 0.917 | 0.983 | 0.636 | 0.875 | ok |
| gemini-vertex | gemini-2.5-flash | llm_graph_rag | 60 | 0.850 | 0.850 | 0.850 | 0.983 | 0.467 | 0.875 | ok |
| gemini-vertex | gemini-2.5-pro | llm_graph_rag | 60 | 0.917 | 0.917 | 0.917 | 0.983 | 0.615 | 1.000 | ok |
| moonshot | kimi-k2.6 | llm_graph_rag | 60 | 0.967 | 0.967 | 0.967 | 1.000 | 0.875 | 0.875 | ok |
| relay | claude-opus-4-6 | llm_graph_rag | 60 | 0.950 | 0.967 | 0.967 | 0.967 | 0.875 | 0.875 | ok |
| gpt-provider | gpt-5.5 | llm_graph_rag | 60 | 0.950 | 0.950 | 0.950 | 0.983 | 0.778 | 0.875 | ok |
