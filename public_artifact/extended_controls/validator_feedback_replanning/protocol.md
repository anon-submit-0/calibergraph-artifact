# Pre-Registered Protocol: LLM + Validator-Feedback Replanning Loop (Reviewer R2's Strongest Remaining Alternative)

- Pre-registration timestamp (UTC, written BEFORE any experimental LLM call): **2026-07-11T15:55:12Z**
- Execution boundary: all experiment writes are restricted to `extended_controls/validator_feedback_replanning/`.
- Exactly one LLM call preceded this registration: a connectivity smoke test (`Reply with exactly: OK`, 20 max tokens, HTTP 200, content `OK`). No benchmark case was sent before registration.
- API credentials are supplied at runtime and never written to any output, script, or log.

## 1. Question being tested (reviewer's alternative explanation)

The paper already contains (i) a deterministic semantic-layer validator (the compiler's witness checks: metric-in-catalog, allowed dimensions, finest grain, refusal policy) and (ii) LLMs that can plan. Reviewer R2's strongest remaining alternative: combine them into a **detect → feed back → replan** loop. If the loop closes the gap to the compiler, the paper's "compilation is necessary for conformance/accuracy" claim must be narrowed to an efficiency/auditability claim. This direction judgment is critical; the result is reported as-is whichever way it falls.

**Pre-registered reporting branches (choose branch only from the data; numbers are never adjusted):**

- **Branch (a) — loop closes the gap:** final joint metric+dimension accuracy ≥ **0.98** on the pooled scope (391 cases) AND ≥ 0.98 on every layer. Consequence: the paper's necessity claim is narrowed to efficiency + auditability; we report honestly the mean LLM calls per case and token cost of the loop vs. the compiler's zero LLM calls.
- **Branch (b) — significant improvement, not closed:** final vs. round-0 improvement is statistically significant (two-sided exact binomial test on discordant pairs, pooled 391 cases, p < 0.05) but Branch (a) is not met. Consequence: concession sentence "validator feedback repairs part of the gap but compilation is still required for conformance", with the per-violation-type fix-rate table.
- **Branch (c) — limited improvement:** improvement not significant at p < 0.05 (or micro joint gain < 0.02). Consequence: mechanism evidence that validator feedback is not a reliable repair channel, with the table of violation/error types that do not get fixed.

Regardless of branch, we report: per-round score evolution, final comparison vs {LLM Schema-RAG round-0, H1 full-contract instructed execution, compiler}, per-case LLM call/token cost, and the census of errors **invisible** to a gold-free validator (validator-pass but wrong).

## 2. Loop definition (fixed before any run)

- **Round 0 — LLM Schema-RAG planning.** Model `deepseek-3.2` (OpenAI-compatible gateway, OpenAI-compatible `POST /chat/completions`), `temperature=0`, `max_tokens=4000`, timeout 240 s, one case per request. Prompt mirrors the paper's released `llm_schema_rag` condition (`public_artifact/scripts/run_public_chinook_eval.py::build_prompt` / `build_context`), i.e. a *retrieval-snippet* prompt, NOT the H1 verbatim-full-contract prompt:
  - retrieved context = top-5 metric snippets ranked by the SAME text scorer as each layer's released evaluator (`run_govtwin_eval.py::rank_metrics`, `run_multigov_metric_caliber_eval.py::rank_metrics`, `run_iowa_liquor_eval.py::rank_metrics`, reimplemented verbatim), rendered in the Chinook `metric_line` style (id, name, aliases, formula/formula_role, allowed_dimensions, description) — matching the released Chinook schema-RAG behaviour, metrics with `answerable=false` are excluded from retrieval;
  - plus ALL dimension snippets in the Chinook `dim_line` style (id, name, aliases, parent, grain_rank);
  - plus the released generic Rules block with only the two Chinook-specific fragments genericized ("unsupported refund metrics" → "unsupported metrics"; "off-domain weather/lunch/random requests" → "off-domain requests");
  - output format: exactly ONE JSON object `{"case_id","action","metric_id","dimensions","time_window","reason"}` (single-case calls instead of the released batch-of-10; this is the only structural deviation and it favours the loop).
  - No policy catalog text, no governance-edge dump, no gold labels, no few-shot examples in round 0.
- **Deterministic validator** (gold-free; sources are ONLY released public artifacts). Given a normalized prediction it returns ALL violations from this closed list:
  1. `answer_without_metric` — action=answer but empty metric_id.
  2. `metric_not_in_catalog` — predicted metric_id not in the layer's released `metric_catalog.jsonl`.
  3. `unanswerable_metric` — predicted metric has `answerable=false` / is `governed_by unsupported_metric_policy` (Iowa `profit_margin`).
  4. `dimension_not_in_catalog` — a predicted dimension is not in `dimension_catalog.jsonl`.
  5. `dimension_not_allowed` — a predicted dimension is outside the metric's allowed set (`allowed_dimensions` ∪ `measures_of` edges).
  6. `finest_grain_violation` — the predicted dimension set contains a dimension together with one of its ancestors (hierarchy = `parent` fields ∪ `rolls_up_to` edges).
  7. `missed_refusal` — action=answer but the query matches a released refusal trigger. Trigger keyword lists are copied verbatim from the released evaluators: `run_govtwin_eval.py::should_refuse`, `run_multigov_metric_caliber_eval.py::should_refuse`, `run_iowa_liquor_eval.py::should_refuse`.
  8. `unjustified_refusal` — action=refuse but the query matches NO released refusal trigger (the policy catalog is a closed list of refusal grounds; the compiler answers whenever no policy fires, so this check is available to any deployment of the paper's validator).
  9. `output_not_parseable` — the reply is not parseable as one JSON object under the pre-registered H1 parsing rules (think-tag strip, fence strip, `json.loads`, first-balanced-brace fallback).
- **Feedback and replanning.** If the validator reports ≥1 violation, we append the assistant's raw reply and a user message "GOVERNANCE VALIDATOR REPORT" that lists, for every violation, the **violation type + the specific released rule text** (policy_catalog lines quoted verbatim where they exist, e.g. GovTwin `policy_finest_grain`; MultiGov disclosure `public_rule`; Iowa `governed_by aggregate_only_policy` / `unsupported_metric_policy` edges; the metric's `allowed_dimensions` list for violation 5; the specific `rolls_up_to`/`parent` pair for violation 6) plus the offending element, then instructs the model to output a corrected single JSON object. Feedback never contains gold labels, never names the correct metric or the correct dimension set, and never dumps the full catalog.
- **Termination.** Up to **3 repair rounds** (rounds 1–3; ≤4 LLM calls per case). Stop early on a validator-pass. The scored prediction for a case is its **last produced output** (whether or not it still violates). If the last output is unparseable, it is scored per the H1 rule as a wrong non-refusal answer (`__parse_error__`), never credited as a refusal.
- Retries on transport errors/HTTP≥400/empty content: up to 3 (backoff 5/15/45 s) per call; a call that still fails is recorded `api_error`; if that happens mid-loop the case keeps its previous round's output and the error is reported.

## 3. Scope (fixed)

| Layer | Cases | Source (read-only) | Gold |
|---|---:|---|---|
| GovTwin base | 159 (full) | `govtwin_metric_caliber/test_cases.jsonl`, gold stripped at load | same file `expected_*` |
| MultiGov | 200 stratified | `multigov_metric_caliber/blind_cases.jsonl` (released blind file) | `gold_labels.jsonl` |
| IowaLiquor | 32 (full) | `iowa_liquor_metric_caliber/test_cases.jsonl`, gold stripped at load | same file `expected_*` |

**MultiGov stratified subsample (canonical, seed hard-coded):** stratified by `query_family`, proportional allocation with largest-remainder rounding over the released family census {policy_refusal 184, finest_grain_trap 163, answerable_direct 115, denominator_caliber 29, temporal_anchor 19} → **{policy_refusal 72, finest_grain_trap 64, answerable_direct 45, denominator_caliber 11, temporal_anchor 8} = 200**; within each family `random.Random(20260711).sample` over case_ids sorted lexicographically, families processed in sorted family-name order with the SAME generator instance. **Seed = 20260711.** This seed and sampling procedure are canonical and MUST be reused verbatim by the planned multi-model extension (no prior multi-model artifact defines a different seed; this registration establishes it). Selected ids written to `multigov_subsample_200.json`.

The runner asserts no prompt-side case object carries any `expected_*` (or `*_hash`) key. No case text, catalog, or validator rule is tuned against gold labels.

## 4. Scoring (mirror of released evaluators; unchanged from H1)

Identical formulas to the released scorers (`refused = action=="refuse" or empty metric`, `metric_ok`, `dim_ok = set equality`, `joint_ok = metric_ok and dim_ok`, refusal P/R), reusing the H1 mirror implementation that was cross-validated against every released results file to <1e-9 (`../complete_contract_prompting/scorer_crosscheck.json`, `_overall_match: true`); the cross-check is re-run by this experiment's script before any new number is trusted and recorded in `validator_audit.json`. `time_window` is collected, not scored (released scorers do not score it).

Score evolution: for round k ∈ {0,1,2,3}, each case contributes its state as of round k (cases that stopped earlier keep their final output). 95% Wilson intervals on per-layer final joint. Pooled final-vs-round-0 comparison: two-sided exact binomial (sign) test on discordant pairs.

Comparison rows:
- **LLM Schema-RAG baseline** = round 0 of this run (model-matched, same input condition as the paper's schema-RAG family).
- **H1 full-contract instructed execution** = re-scored from `../complete_contract_prompting/predictions_*.jsonl` on the SAME case scope (MultiGov restricted to the 200-case subsample).
- **CaliberGraph compiler** = released results (joint 1.000, zero violations, refusal P/R 1.000 on these layers).

Secondary endpoints (pre-registered):
- per-violation-type census at round 0 and at final round; per-type fix rate (violations present at round 0 that are absent at final);
- **validator-invisible errors**: final validator-pass cases with `joint_ok=false`, split into wrong-metric / wrong-dimension-set(allowed) / other;
- cost: LLM calls per case (mean/max), total prompt+completion tokens, vs compiler zero LLM calls;
- MultiGov per-`query_family` joint by round.

## 5. Validator audit (run before any experimental LLM call; recorded in `validator_audit.json`)

1. **Gold soundness:** every gold plan in scope must pass the validator (0 violations). If any gold plan is flagged, the validator is corrected BEFORE the run and the correction documented here. (Pre-run audit already verified: refusal triggers reproduce gold answer/refuse exactly on all three layers — 0/391 mismatches; all gold dimension sets are within allowed maps.)
2. **Scorer identity:** the mirrored scorer reproduces released result rows (<1e-9), as in H1.

Honest note on validator strength: on these released benchmarks the trigger lists adjudicate answer-vs-refuse perfectly, so the loop receives a maximally reliable refusal signal — a deliberate steelman of the reviewer's proposal. What a gold-free validator cannot see: whether an in-catalog metric is the *right* metric, and whether an allowed, grain-consistent dimension set is the *requested* set. Whether the loop closes the gap therefore tests exactly the reviewer's hypothesis.

## 6. Outputs

- `protocol.md` (this file, written before any experimental call)
- `run_loop.py` — sampler, round-0 prompt builder, validator, loop runner, mirrored scorer (no keys embedded)
- `multigov_subsample_200.json`, `validator_audit.json`, `prompts/round0_*.txt`
- `raw_responses/{layer}_loop_raw.jsonl` — one record per case containing every round: prompt_sha256, latency, usage, verbatim raw response, validator verdict, feedback text
- `per_case_rounds.jsonl` — flattened: one line per case per round `{layer, case_id, round, prediction, validator_verdict, feedback_text, raw_response}`
- `scores.json` — per-layer per-round metrics, CIs, violation censuses, fix rates, invisible-error census, cost accounting, branch inputs
- `SUMMARY.md` — tables, pre-registered branch judgment, honest limitations

## 7. Execution order

1. Write this protocol. 2. Validator audit + MultiGov sampling (no LLM). 3. Pilot: Iowa 32 end-to-end. 4. GovTwin 159, MultiGov 200. 5. Score, branch judgment, SUMMARY.

## 8. Honesty rules binding this run

No mocked or simulated output; every prediction traces to a stored raw response with usage metadata. All failures reported as-is. Single run at temperature 0; provider nondeterminism acknowledged, not rerun-shopped. Whichever pre-registered branch the data supports is the branch reported.
