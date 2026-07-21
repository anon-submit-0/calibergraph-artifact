# MetricFlow Real-Engine Baseline on IowaLiquor-MetricCaliber — Results Summary

Run date: 2026-07-11. Pre-registered protocol: `protocol.md` (written before any evaluation query ran).
Purpose: answer reviewer gap #3 — "the semantic-layer validator baseline is an author-built proxy;
a real open-source semantic-layer engine might already solve governed metric answering/refusal."

## 1. What was run (all real, no mocks)

- Engine: **MetricFlow 0.211.0** (PyPI `License-Expression: Apache-2.0`; satisfies the >=0.209.0
  constraint that avoids earlier BSL-licensed releases) via `mf` CLI from dbt-metricflow 0.13.0,
  dbt-core 1.11.12, dbt-duckdb 1.10.1, DuckDB 1.5.4, Python 3.12 (`env/`).
- Data: the benchmark's public 5000-row Iowa 2024 snapshot, copied SQLite -> DuckDB
  (**MetricFlow has no SQLite adapter** — engine substitution is declared, and 9/9 parity checks
  match: `translation/data_parity.json`).
- Translation: `translation/translate_catalog.py` mechanically compiled the public governance
  catalog into MetricFlow YAML (`dbt_project/models/semantic_iowa.yml`): 8/9 metrics, 6 categorical
  dimensions + native time granularity. `mf validate-configs` passes with **0 errors / 0 warnings**,
  so the translated layer is valid by the engine's own standard.
- Execution: 64 real `mf query` invocations for the 32 test cases x 2 modes (mean 2.71 s, min 2.61,
  max 3.28) + 9 capability probes. Every invocation's full stdout/stderr is preserved under
  `raw_outputs/` and `probes/`. Scores were bit-identical across two full runs (deterministic).

## 2. Headline score table (scoring logic mirrors the released `run_iowa_liquor_eval.py` exactly)

| Method | Metric | Dim. | Joint | Ref.P | Ref.R | Exec.(ans.) |
|---|---:|---:|---:|---:|---:|---:|
| Direct keyword (released) | 0.750 | 0.375 | 0.156 | 0.000 | 0.000 | 1.000 |
| Schema proxy (released, same lexical linker, no engine) | 0.781 | 0.719 | 0.563 | 0.000 | 0.000 | 1.000 |
| Open SQL end-to-end (released) | 0.781 | 0.719 | 0.563 | 0.000 | 0.000 | 1.000 |
| **MetricFlow (real engine, lexical linker)** | **0.844** | **0.781** | **0.625** | **1.000** | **0.286** | **1.000** |
| Oracle-candidate prompt (released) | 1.000 | 0.781 | 0.781 | 1.000 | 1.000 | 1.000 |
| **MetricFlow (real engine, oracle metric)** | **1.000** | **0.781** | **0.781** | **1.000** | **1.000** | **1.000** |
| CaliberGraph (released) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Machine-readable: `results/scores.json`; per-case: `results/per_case_results.jsonl`.

### Reading the two MetricFlow rows

- **Lexical row** (same NL->structured linker as the released `schema_proxy` baseline, copied
  verbatim; the engine is the only added component): the real engine adds exactly one capability —
  rejecting *absent names*. Refusal recall rises 0 -> 2/7 (28.6%): the two profit-margin cases fail
  with "does not exactly match any known metrics". The other 5 refusal cases (raw invoice ids, store
  addresses, DROP TABLE, weather, phone numbers) are lexically linked to *valid* metric names
  (invoice_count, store_count, sales_dollars, store_count, liters_sold) and the engine **executes
  them without complaint** (`raw_outputs/metricflow_lexical/iowa_026...032.txt`).
- **Oracle-metric row** (gold metric, lexical dims, literal-intent structured queries for refusal
  cases — protocol section 4B): lands *exactly* on the released oracle-candidate-prompt row
  (1.000 / 0.781 / 0.781 / 1.0 / 1.0). All 7 refusals are caught, but every one via a generic
  resolver error: 5x "does not exactly match any known metrics", 2x "does not match any of the
  available group-by-items". The remaining 7 failures are all the same defect: **no categorical
  hierarchy / finest-grain resolution** (county+city, category+item asked together; governance gold
  collapses to the finest grain; the engine returns both grains: iowa_003/004/009/011/014/022/024).

### Two honest observations that cut both ways

1. Credit: MetricFlow's structured query surface genuinely refuses raw SQL (P6) and absent names
   (P4/P5), and time granularity (month/quarter) is native and correct (P7a/P7b). It is a real
   improvement over open-SQL baselines on the injection/unknown-name slice.
2. Risk found in the raw logs: the unknown-metric error **actively suggests substitute metrics**
   (e.g. querying `profit_margin` returns `Suggestions: ['average_bottle_price', 'item_count', ...]`).
   For an LLM agent wired to the engine, refusal-by-absence comes with a built-in caliber-substitution
   nudge — the opposite of a governed structured refusal.

## 3. Probe results (all 9 matched the pre-registered predictions; raw output per probe in `probes/`)

| Probe | Governance says | Engine behavior (measured) |
|---|---|---|
| P1 invoice_count x item_desc | DENIED (reachability) | **compiles & runs, 20 rows** — cannot block |
| P2 store_count x store_name | DENIED (reachability) | **compiles & runs, 20 rows** — cannot block |
| P3 county+city together | collapse to finest grain | runs with both grains, no collapse |
| P4 undeclared store_address | disclosure denied | blocked, but only because we omitted it; generic "no group-by-item" error |
| P5 profit_margin | declared-unanswerable + policy | generic unknown-metric error + substitute suggestions |
| P6 `sales_dollars; DROP TABLE ...` | must refuse | rejected (unknown metric) — credit: no raw-SQL passthrough |
| P7a/b metric_time month/quarter | allowed | native, correct (8 months / 4 quarters present in sample) |
| P8 as-of flag | as-of binding required | **no such flag** — only `--start-time/--end-time/--where` (`P8_mf_query_help.txt`) |
| P9 2023 window (out of coverage) | coverage refusal/caveat | **exit 0, 0 rows** — silent empty answer, no coverage signal |

## 4. Quantified inexpressibility (the gap evidence for the paper)

`translation/inexpressible.json` — **15 dropped-semantics items across 8 families**, each with the
exact catalog payload that had no MetricFlow home. Mechanical proof: an exhaustive recursive field
inventory of all **23 spec classes** in installed dbt-semantic-interfaces 0.9.0
(`translation/spec_field_inventory.json`) contains **zero** fields able to host any of the following
(the only "grain"-like fields are time-granularity params for cumulative metrics):

| Governance family | Catalog volume | MetricFlow status |
|---|---|---|
| (2) metric x dimension reachability | 58 measures_of edges; 6/64 pairs denied | No field. Engine over-permits all 6 denied pairs (9.4% of the pair space); P1/P2 confirm 2 empirically. |
| (3) categorical hierarchy / finest grain | 4 rolls_up_to edges | No construct (time-only granularity). Causes all 7 answer-side failures. |
| (4) disclosure policy (aggregate_only on invoice_id, store_address) | 2 policy edges | Encodable only by omission; no policy object, no audit trail, generic error, and omission removes legitimate uses (invoice_id as join entity). |
| (4) declared-unanswerable metric (profit_margin) | 1 metric + 1 policy edge | Omission only; error indistinguishable from a typo; suggests substitutes. |
| (5) physical coverage window | 2024-only snapshot | No declaration; out-of-coverage = silent empty answer (P9). |
| (5) as-of / bitemporal binding | — | No flag/construct (P8). |
| (5) structured refusal object | — | All rejections are CLI error text; no reason codes. |
| (minor) NULLIF denominator guard | 2 ratio formulas | Ratio metrics emit plain division. |

Pre-registered expectation check (protocol section 7): predictions held on every family — (2)(3)
partially mitigated only where the violation surfaces as an *absent name*; (4)(5) structurally zero
mechanism. No narrative flip is warranted; nothing was over-claimed against the engine either: its
native time granularity and injection resistance are credited above.

## 5. Comparison takeaway

- Versus the author-built proxy (`schema_proxy`): the real engine's *only* delta with the same linker
  is unknown-name rejection (joint 0.563 -> 0.625; refusal recall 0 -> 0.286). The proxy was, if
  anything, generous to the semantic-layer approach.
- Engine ceiling with a gold metric linker equals the released oracle row (joint 0.781, refusal 1.0
  by generic errors) and still loses 7/32 cases to missing hierarchy resolution; CaliberGraph closes
  those to 1.000 with policy-grounded structured refusals.

## 6. Limitations (as-run)

1. Warehouse substitution: SQLite -> DuckDB (no SQLite adapter in MetricFlow); 9/9 aggregate parity
   checks pass, but the executed SQL dialect differs from the released baselines' SQLite.
2. The NL->structured mapping is a deterministic lexical linker (identical to the released baselines)
   plus a fixed literal-intent table for oracle-mode refusal cases; a stronger LLM linker could change
   the lexical row (both directions: better metric linking, but also more valid-name forwarding of
   row-level asks — which the engine cannot catch).
3. Single semantic model translation (the engine-idiomatic reading of a one-table benchmark). A
   split-per-metric multi-model workaround could emulate some reachability denial at the cost of 8
   near-duplicate models and still-generic errors; documented but not run (protocol section 3).
4. `dimension_exact_accuracy`/refusal semantics inherit the released scorer verbatim, including its
   convention that a refusal with empty pred_metric_id counts as metric-correct on refusal-gold cases.
5. Environment: venv lives in the session scratchpad (not in this release tree); exact package pins
   in `env/pip_freeze.txt` allow reconstruction.

## 7. Credibility self-assessment

High for what is claimed: every number traces to a preserved raw `mf` invocation log (64 eval + 9
probe runs); scores reproduced bit-identical across two full runs; the translation passes the
engine's own `validate-configs`; predictions were written down before execution and none required
post-hoc branch selection. Moderate on external generality: one engine (MetricFlow/dbt), one
benchmark layer (Iowa), and refusal behavior conditioned on the pre-registered linker choices —
stated as such above.

## File map

- `protocol.md` — pre-registered protocol (mapping rules, predictions)
- `translation/` — translate_catalog.py, load_duckdb.py + data_parity.json, inexpressible.json,
  spec_field_inventory.{py,json}
- `dbt_project/` — full runnable dbt+MetricFlow project incl. generated `models/semantic_iowa.yml`
- `run_mf_eval.py` — harness (linker functions copied verbatim from the released scorer)
- `raw_outputs/<mode>/<case_id>.txt` — full stdout/stderr of all 64 eval invocations + run_log.txt
- `probes/` — run_probes.py, P1-P9 raw outputs, probes_results.json, P8 help capture
- `results/per_case_results.jsonl`, `results/scores.json`
- `env/` — pip freeze, versions, validate-configs output
