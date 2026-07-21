# BIRD-MetricCaliber Diagnostic Evaluation

Source records: 500
Aggregate cases: 206
Unique metric signatures: 166
Schema dimensions: 782

## NL2Metric-Caliber Planners

| Method | Metric Acc. | Dim. Exact | Joint |
|---|---:|---:|---:|
| direct | 0.199 | 0.917 | 0.189 |
| schema_rag | 0.830 | 0.811 | 0.665 |
| autolink_derived_e3 | 0.830 | 0.811 | 0.665 |
| caliber_graph | 0.830 | 0.811 | 0.665 |

## Strong Text-to-SQL Baselines Diagnosed as Metric-Caliber Outputs

| SQL baseline | Parse | Agg func | Measure col | Dim exact | Table recall | Joint caliber |
|---|---:|---:|---:|---:|---:|---:|
| bird_gpt35_sql | 0.932 | 0.626 | 0.063 | 0.869 | 0.709 | 0.049 |
| bird_gpt4_turbo_sql | 1.000 | 0.694 | 0.083 | 0.903 | 0.830 | 0.078 |
| bird_gpt4o_sql | 0.995 | 0.641 | 0.073 | 0.913 | 0.830 | 0.053 |
| bird_llama3_70b_sql | 0.990 | 0.636 | 0.068 | 0.903 | 0.825 | 0.044 |
