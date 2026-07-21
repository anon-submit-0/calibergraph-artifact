# Pre-registered Protocol: dbt MetricFlow as Real Semantic-Layer Engine Baseline

Date pre-registered: 2026-07-11 (written BEFORE any `mf query` evaluation run; see git-less audit note at bottom).
Target reviewer gap: "the semantic-layer validator baseline is an author-built proxy; a real open-source
semantic-layer engine might already solve governed metric answering/refusal."

## 1. Engine under test

- MetricFlow **0.211.0** (PyPI, License-Expression: Apache-2.0; satisfies the pre-registered
  constraint metricflow >= 0.209.0 to stay clear of earlier BSL-licensed releases).
- dbt-metricflow 0.13.0 (provides the `mf` CLI), dbt-core 1.11.12, dbt-duckdb 1.10.1, duckdb 1.5.4,
  dbt-semantic-interfaces 0.9.0. Python 3.12 venv. Full freeze: `env/pip_freeze.txt`.
- **Warehouse caveat (declared up front):** MetricFlow has no SQLite adapter. The benchmark's
  `iowa_liquor_2024_sample.sqlite`/`.csv` (5000 rows, identical content) is loaded into DuckDB.
  Load-time parity checks (row count, SUM(sales_dollars), COUNT(DISTINCT invoice_id)) between the
  SQLite file and the DuckDB copy are recorded in `translation/data_parity.json`. Any mismatch aborts.

## 2. Benchmark inputs (read-only)

`public_artifact/public_benchmark/iowa_liquor_metric_caliber/`:
`metric_catalog.jsonl` (9 metrics, 1 unanswerable), `dimension_catalog.jsonl` (8 dimensions with
`rolls_up_to` hierarchy), `governance_edges.jsonl` (58 measures_of + 4 rolls_up_to + 11 governed_by),
`test_cases.jsonl` (32 cases: 25 answer / 7 refuse), `iowa_liquor_2024_sample.{csv,sqlite}`.

## 3. Translation rules (governance catalog -> MetricFlow YAML)

One semantic model `iowa_liquor_sales` over the single physical table (MetricFlow-idiomatic usage).
Surrogate primary entity `sale_line` (row_number over the table; the table grain is invoice line item
and has no natural single-column key).

| Catalog object | MetricFlow translation |
|---|---|
| sales_dollars = SUM(sales_dollars) | measure agg=sum -> simple metric |
| bottles_sold = SUM(sales_bottles) | measure agg=sum -> simple metric |
| liters_sold = SUM(sales_liters) | measure agg=sum -> simple metric |
| invoice_count = COUNT(DISTINCT invoice_id) | measure agg=count_distinct -> simple metric |
| store_count = COUNT(DISTINCT store_no) | measure agg=count_distinct -> simple metric |
| item_count = COUNT(DISTINCT item_no) | measure agg=count_distinct -> simple metric |
| average_bottle_price = dollars/bottles | ratio metric (numerator sales_dollars, denominator bottles_sold) |
| average_invoice_value = dollars/invoices | ratio metric (numerator sales_dollars, denominator invoice_count) |
| profit_margin (answerable=false, empty formula) | **NOT TRANSLATABLE** — MetricFlow has no "declared but unanswerable/refuse-with-reason" metric construct; the only encoding is omission from the YAML. Goes to the inexpressible list. |
| ordered_month / ordered_quarter | native: time dimension `ordered_on` (defaults.agg_time_dimension) queried as `metric_time__month` / `metric_time__quarter` |
| county_name, store_city, store_name, category_name, vendor_name, item_desc(im_desc) | categorical dimensions |
| allowed_dimensions per metric (measures_of edges) | **NOT TRANSLATABLE** in a single semantic model — every dimension of a semantic model is queryable with every measure; no per-metric allow/deny field exists (verified by exhaustive field inventory of dbt-semantic-interfaces 0.9.0 pydantic spec, `translation/spec_field_inventory.json`). A workaround of duplicating the semantic model per metric with dimension subsets is documented but rejected as non-idiomatic (catalog blow-up: 8 near-identical models over one table) and still yields generic parse errors, not governed refusals. |
| rolls_up_to hierarchy + finest-grain resolution | **NOT TRANSLATABLE** — no categorical dimension hierarchy concept (granularity exists for time only). |
| aggregate_only_policy on invoice_id / store_address | **Encodable only by omission**: we deliberately do NOT declare invoice_id (as entity) or store_address (as dimension). Note this is enforcement-by-absence: no policy object, no audit trail, and a generic "unable to parse / not found" error instead of a structured refusal. Declaring invoice_id as an entity (the idiomatic encoding of a key) would make `group by invoice_id` legal and leak row-level ids; the translation is therefore deliberately bent IN FAVOR of MetricFlow's blocking ability. |
| physical coverage window (2024 sample, 5000 rows) | **NOT TRANSLATABLE** — no coverage/completeness declaration; probed in P9. |
| as-of / valid-time binding | **NOT TRANSLATABLE** — `mf query` exposes only `--start-time/--end-time` transaction-window filters on metric_time; no as-of construct. |

Translation is performed by `translation/translate_catalog.py` reading the jsonl catalogs and emitting
the YAML; the generated YAML is committed verbatim under `dbt_project/models/`.

## 4. Query construction for the 32 test cases (fixed BEFORE running)

MetricFlow is not an NL interface; it consumes structured (metrics, group-bys). Two pre-registered modes:

### Mode A — `metricflow_lexical` (headline row, comparable to `schema_proxy`)
NL -> (metric, dims) via the **verbatim** lexical linker from the released
`public_artifact/scripts/run_iowa_liquor_eval.py` (`rank_metrics` top-1 with the same keyword bonuses,
`explicit_dims`; functions copied byte-identical into the harness). The linker sees the full governance
catalog including profit_margin, exactly as the released baselines do. Then:

- If the linker yields no metric (empty ranked list): action=refuse, reason `no_metric_candidate`
  (mapping-layer refusal; the engine is never invoked; mirrors the released scorer which counts empty
  pred_metric_id as refusal).
- Else run `mf query --metrics <metric> --group-by <mapped dims>` (no group-by flag if dims empty).
  - `mf` exit code 0 -> action=answer with (metric, dims).
  - `mf` exit code != 0 -> action=refuse; stderr/stdout preserved in `raw_outputs/`; error category recorded.

Group-by name mapping (bidirectional, fixed): ordered_month<->metric_time__month,
ordered_quarter<->metric_time__quarter, other dims d <-> sale_line__d (item_desc <-> sale_line__item_desc).
The benchmark's `expected_time_window: 2024` is not turned into a filter, mirroring the released
scorer (`plan_sql` adds no WHERE clause); all data is 2024.

### Mode B — `metricflow_oracle_metric` (engine ceiling, comparable to `oracle_candidate_prompt`)
Isolates the engine from linker noise on the metric side, mirroring the released
`oracle_candidate_prompt` mode (gold metric, lexical dims):

- Answerable cases: metric = gold `expected_metric_id`; dims = `explicit_dims(nl_query)` (lexical),
  so the engine — not an oracle — is responsible for any granularity/hierarchy fixing.
- Refusal cases: the most literal faithful structured query (fixed now):
  - iowa_026 "Show raw invoice ids" -> `--metrics invoice_count --group-by sale_line__invoice_id`
  - iowa_027 "List store addresses" -> `--metrics store_count --group-by sale_line__store_address`
  - iowa_028 "DROP TABLE iowa_liquor_sales" -> `--metrics "DROP TABLE iowa_liquor_sales"`
  - iowa_029 weather -> `--metrics weather`
  - iowa_030 "Profit margin by category" -> `--metrics profit_margin --group-by sale_line__category_name`
  - iowa_031 "Gross margin by vendor" -> `--metrics profit_margin --group-by sale_line__vendor_name`
  - iowa_032 customer phone numbers -> `--metrics customer_phone_numbers`
  Engine exit code decides answer/refuse as in Mode A. Scoring of pred_metric_id for refusal cases uses
  the post-engine action: refuse -> pred_metric_id="" (mirrors released scorer semantics).

## 5. Scoring

Byte-identical mirror of `score()` in the released `run_iowa_liquor_eval.py`: metric_accuracy,
dimension_exact_accuracy, joint accuracy, refusal precision/recall (refused := action==refuse or empty
pred_metric_id), execution success on answer predictions (here: `mf` exit 0 AND >=1 data row in stdout).
Outputs: `results/per_case_results.jsonl`, `results/scores.json` (with the released baseline numbers
copied alongside for the comparison table), `SUMMARY.md`.

## 6. Engine capability probes (outside the 32-case score; each probe = one `mf` invocation, raw output kept)

- P1 governance-denied combo: invoice_count x item_desc (denied by absent measures_of edge). Prediction: **compiles and runs** (no per-metric dim policy).
- P2 governance-denied combo: store_count x store_name. Prediction: runs.
- P3 hierarchy collapse: sales_dollars x [county_name, store_city]. Prediction: runs with both, no finest-grain resolution.
- P4 undeclared column as dim: sales_dollars x store_address. Prediction: resolver error (blocking-by-omission).
- P5 unknown metric: profit_margin. Prediction: error, generic "not found" text, no policy reason.
- P6 injection string as metric name: `sales_dollars; DROP TABLE iowa_liquor_sales`. Prediction: parser error (credit to the engine: no raw-SQL passthrough).
- P7 native time granularity: sales_dollars x metric_time__month, x metric_time__quarter. Prediction: works (credit).
- P8 as-of: inspect `mf query --help` for any as-of/bitemporal flag. Prediction: none (only --start-time/--end-time).
- P9 coverage window: sales_dollars with --start-time 2023-01-01 --end-time 2023-12-31 (outside the 2024-only snapshot). Prediction: **exit 0 with empty result** — silent empty answer instead of coverage-based refusal/caveat.
- P10 mechanical inexpressibility proof: dump every field of PydanticSemanticModel / PydanticDimension / PydanticMeasure / PydanticEntity / PydanticMetric (+ nested type params) from installed dbt-semantic-interfaces 0.9.0 into `translation/spec_field_inventory.json`; check no field can host allowed_dimensions / categorical hierarchy / disclosure policy / coverage / as-of / refusal reason.

## 7. Pre-registered expectations (results may only select branches, never edit numbers)

MetricFlow is expected to: natively handle time granularity (family ③ partially); block absent names
(unknown metric, undeclared dimension) with generic errors; NOT express per-metric allowed_dimensions
(family ②), categorical finest-grain hierarchy (family ③ categorical part), unanswerable-with-policy,
aggregate-only disclosure policy, coverage windows, or as-of binding (families ④⑤ structurally zero
mechanism). If probes show MetricFlow can in fact express/block any of these, the finding is reported
as-is and the paper narrative is flipped accordingly.

## 8. Honesty rules

No mocking; every reported engine behavior comes from a real `mf` invocation whose raw stdout/stderr
is preserved under `raw_outputs/` and `probes/`. Installation or runtime failures are reported as
findings, not patched over. Only this directory (`new_experiments/metricflow_engine_run/`) is written.

Audit note: this directory is not a git repo; pre-registration ordering is evidenced by file mtimes and
by the run log `raw_outputs/run_log.txt` whose first entry is created after this file exists.
