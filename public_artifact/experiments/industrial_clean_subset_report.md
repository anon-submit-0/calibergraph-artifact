# Industrial Clean-Subset Report

Aggregate-only report. No private query text, private metric id, table name, column name, or row-level value is released.

## Label Audit

| Audit item | Count |
|---|---:|
| Cases audited | 159 |
| Exact duplicate query groups | 22 |
| Answer/refuse conflict groups | 1 |
| Cases inside answer/refuse conflict groups | 2 |
| Conflict-free cases | 157 |
| Deduplicated conflict-free cases | 116 |

## All industrial cases

| Method | N | Metric | Dim. | Joint | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|---:|
| direct_keyword | 159 | 0.818 | 0.403 | 0.333 | 0.000 | 0.000 |
| schema_rag | 159 | 0.881 | 0.403 | 0.352 | 0.000 | 0.000 |
| llm_direct | 159 | 0.874 | 0.918 | 0.799 | 0.438 | 0.778 |
| llm_schema_rag | 159 | 0.925 | 0.925 | 0.849 | 0.636 | 0.778 |
| llm_graph_rag | 159 | 0.899 | 0.925 | 0.824 | 0.467 | 0.778 |
| autolink_iterative_enterprise | 159 | 0.893 | 0.302 | 0.283 | 1.000 | 0.222 |
| safenlidb_guarded_enterprise | 159 | 0.925 | 0.428 | 0.396 | 1.000 | 0.778 |
| caliber_graph | 159 | 0.925 | 0.994 | 0.925 | 1.000 | 0.778 |
| caliber_graph_enterprise | 159 | 0.925 | 0.994 | 0.925 | 1.000 | 0.778 |

## Conflict-free subset

| Method | N | Metric | Dim. | Joint | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|---:|
| direct_keyword | 157 | 0.822 | 0.395 | 0.331 | 0.000 | 0.000 |
| schema_rag | 157 | 0.885 | 0.395 | 0.350 | 0.000 | 0.000 |
| llm_direct | 157 | 0.879 | 0.917 | 0.803 | 0.438 | 0.875 |
| llm_schema_rag | 157 | 0.930 | 0.924 | 0.854 | 0.636 | 0.875 |
| llm_graph_rag | 157 | 0.904 | 0.924 | 0.828 | 0.467 | 0.875 |
| autolink_iterative_enterprise | 157 | 0.898 | 0.293 | 0.280 | 1.000 | 0.250 |
| safenlidb_guarded_enterprise | 157 | 0.930 | 0.420 | 0.395 | 1.000 | 0.875 |
| caliber_graph | 157 | 0.930 | 0.994 | 0.930 | 1.000 | 0.875 |
| caliber_graph_enterprise | 157 | 0.930 | 0.994 | 0.930 | 1.000 | 0.875 |

## Deduplicated conflict-free subset

| Method | N | Metric | Dim. | Joint | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|---:|
| direct_keyword | 116 | 0.793 | 0.397 | 0.310 | 0.000 | 0.000 |
| schema_rag | 116 | 0.862 | 0.397 | 0.336 | 0.000 | 0.000 |
| llm_direct | 116 | 0.845 | 0.888 | 0.741 | 0.467 | 0.875 |
| llm_schema_rag | 116 | 0.914 | 0.897 | 0.810 | 0.636 | 0.875 |
| llm_graph_rag | 116 | 0.879 | 0.897 | 0.776 | 0.467 | 0.875 |
| autolink_iterative_enterprise | 116 | 0.879 | 0.259 | 0.241 | 1.000 | 0.250 |
| safenlidb_guarded_enterprise | 116 | 0.922 | 0.431 | 0.397 | 1.000 | 0.875 |
| caliber_graph | 116 | 0.922 | 0.991 | 0.922 | 1.000 | 0.875 |
| caliber_graph_enterprise | 116 | 0.922 | 0.991 | 0.922 | 1.000 | 0.875 |

Conclusion: removing the disclosed answer/refuse gold conflict does not remove CaliberGraph's advantage; the label-risk audit is now a robustness check rather than an unaddressed attack surface.
