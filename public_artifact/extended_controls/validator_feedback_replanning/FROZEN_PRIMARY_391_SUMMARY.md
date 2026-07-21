# Results: LLM + Validator-Feedback Replanning Loop (Reviewer R2's Strongest Remaining Alternative)

- Protocol: `protocol.md`, pre-registered **2026-07-11T15:55:12Z**, before any experimental LLM call (one connectivity smoke test only).
- Condition: round 0 = Schema-RAG retrieval-snippet planning (`deepseek-3.2`, temperature 0, mirror of the released `llm_schema_rag` prompt style, NOT the H1 full-contract prompt) -> deterministic gold-free validator (metric-in-catalog / allowed dimensions / finest grain / released refusal-policy triggers, both directions) -> violation type + released rule text fed back -> up to 3 repair rounds.
- Scope: GovTwin 159 (full) + MultiGov 200 (stratified, seed **20260711**, canonical for the multi-model extension, ids in `multigov_subsample_200.json`) + Iowa 32 (full) = **391 cases**.
- Run: **452 LLM calls, 0 API errors, 0 unparseable final outputs**; every prediction traces to a stored raw response with usage metadata (`raw_responses/`, flattened in `per_case_rounds.jsonl`).
- Pre-run audit (`validator_audit.json`, `overall_pass: true`): all 391 gold plans pass the validator (soundness, 0 flagged); released refusal triggers reproduce gold answer/refuse exactly (0/391 mismatches); mirrored scorer reproduces every released baseline row (<1e-9).

## Headline: joint metric+dimension accuracy by round

| Layer | n | Round 0 (Schema-RAG) | Round 1 | Round 2 | Round 3 (final) | Final Wilson 95% |
|---|---:|---:|---:|---:|---:|---|
| GovTwin base | 159 | 0.780 | 0.981 | 0.981 | **0.981** | [0.946, 0.994] |
| MultiGov (200 sub) | 200 | 0.865 | 0.945 | 0.955 | **0.955** | [0.917, 0.976] |
| IowaLiquor | 32 | 0.813 | 1.000 | 1.000 | **1.000** | [0.893, 1.000] |
| **Pooled** | 391 | **0.826** | -- | -- | **0.969** | [0.947, 0.982] |

Paired round-0 -> final: **56 wrong->right, 0 right->wrong**; two-sided exact sign test p = 2.8e-17.

## Final comparison (same case scope, same mirrored scorer)

| Method | GovTwin joint | MultiGov(200) joint | Iowa joint | Pooled joint | Refusal P/R |
|---|---:|---:|---:|---:|---|
| Best released prompt/guard baseline | 0.736 | 0.680 | 0.781 | -- | 1.000/1.000 (SafeNLIDB-E3) |
| LLM Schema-RAG (round 0, this run) | 0.780 | 0.865 | 0.813 | 0.826 | mixed (MultiGov Ref.P 0.866) |
| H1 full-contract instructed execution (re-scored on scope) | 0.736 | 0.815 | 0.969 | 0.795 | GovTwin Ref.P 0.450 |
| **Validator-feedback loop (final, this run)** | **0.981** | **0.955** | **1.000** | **0.969** | **1.000/1.000 on all three layers** |
| CaliberGraph compiler (released) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000/1.000, zero LLM calls |

(Baseline rows: released results files re-scored on the exact scope; H1 rows from `../complete_contract_prompting/predictions_*.jsonl` restricted to the same cases. MultiGov full-510 released numbers are reproduced on the 200 subsample to 3 decimals: e.g. SafeNLIDB-E3 0.680, CaliberGraph 1.000.)

MultiGov query-family joint by round: answerable_direct 1.000->1.000, policy_refusal 0.986->1.000, denominator_caliber 1.000->1.000, temporal_anchor 1.000->1.000, **finest_grain_trap 0.594->0.859** (all 9 residual errors live here).

## Violation census and fix rates (validator-visible errors are fully repaired)

| Layer | Violation type at round 0 | Cases | Fixed by final | Fix rate |
|---|---|---:|---:|---:|
| GovTwin | finest_grain_violation | 35 | 35 | 1.000 |
| MultiGov | unjustified_refusal (over-refusal) | 11 | 11 | 1.000 |
| MultiGov | dimension_not_allowed | 6 | 6 | 1.000 |
| MultiGov | finest_grain_violation | 6 | 6 | 1.000 |
| MultiGov | missed_refusal | 1 | 1 | 1.000 |
| Iowa | finest_grain_violation | 6 | 6 | 1.000 |

Zero cases still violate at the final round; the final validator verdict is PASS on all 391 cases. Repair chains work across multiple violation types (e.g. `mg_case_0194`: refuse -> answer with grain+allowed violations -> correct plan in round 2). metric_not_in_catalog / dimension_not_in_catalog / unparseable-output violations never occurred.

## The residual gap is exactly the validator-invisible class

All **12 remaining errors (3.1%)** are final-validator-PASS plans whose dimension set is not the *requested* set -- invisible to any gold-free catalog check:

1. **GovTwin, 3 cases** (`govtwin_0011/0131/0152`, flat queries like "current reporting period count metric 16", gold dims `[]`): round 0 dumped all five *allowed* dimensions; feedback removed the grain clash (l1/l2 dropped) but `[issue_type, market_region, segment_l3]` remains -- every dimension allowed, grain-consistent, still not requested. The "allowed-misread-as-required" class survives the loop by construction.
2. **MultiGov, 9 cases** (all `finest_grain_trap`, "compare X by summary scope and fine scope for the current reporting window"): the model bound the reporting window as a grouping dimension `time_anchor` alongside `fine_scope`. `time_anchor` is an allowed dimension in a different hierarchy, so the plan **passed the validator at round 0 and never entered the repair loop** (1 LLM call each). The released label policy treats the window as a time *binding*, not a grouping dimension -- a distinction catalog rules cannot adjudicate.

This is the crisp mechanism boundary: validator feedback repairs 100% of detectable violations; it cannot repair errors that are indistinguishable from valid plans under the released contract's checkable rules.

## Cost accounting (pre-registered secondary endpoint)

| | GovTwin | MultiGov | Iowa | Pooled |
|---|---:|---:|---:|---:|
| LLM calls per case (mean / max) | 1.22 / 2 | 1.10 / 3 | 1.19 / 2 | **1.156 / 3** |
| Cases resolved at round 0 | 124/159 | 182/200 | 26/32 | 332/391 |
| Prompt tokens (total) | 958k | 1,498k | 188k | 2,644k |
| Completion tokens (total) | 140k | 260k | 23k | 422k |
| Mean latency per call | 18.7 s | 29.9 s | 15.9 s | -- |
| Compiler reference | 0 calls | 0 calls | 0 calls | **0 LLM calls, deterministic** |

Per-case prompt cost vs H1 full-contract: MultiGov 7.5k tokens/case (loop, including repair rounds) vs 80.2k tokens/case (H1); GovTwin 6.0k vs 10.4k; Iowa 5.9k vs 7.8k. The loop is both cheaper and more accurate than serializing the whole contract into the prompt.

## Pre-registered branch judgment: **Branch (b) -- significant improvement, not closed**

- Branch (a) test (loop closes the gap): pooled 0.969 < 0.98 and MultiGov 0.955 < 0.98 -> **not met** (Iowa 1.000 and GovTwin 0.981 individually meet the 0.98 bar; the pooled Wilson CI [0.947, 0.982] contains 0.98 but excludes 1.000).
- Branch (b) test: sign test p = 2.8e-17 < 0.05 and micro gain +0.143 >= 0.02 -> **met**.

**Consequence for the paper (as pre-registered):** the reviewer's alternative is partially right and must be conceded -- a detect->feedback->replan loop over the paper's own deterministic validator repairs *every detectable* violation (fix rate 1.0 across all violation types, refusal P/R 1.000/1.000 on all three layers) and lifts joint accuracy from 0.826 to 0.969, fully closing Iowa. The "compilation is necessary" claim must therefore be narrowed: what compilation uniquely provides on these benchmarks is (i) the last ~3% -- requested-set errors that are provably invisible to gold-free catalog validation and therefore unreachable by any validator-feedback loop, (ii) exactness and determinism (1.000 joint, zero variance, zero LLM calls at plan time), and (iii) the loop's own dependency: the feedback signal *is* the compiled contract executed as checks, so the loop is an argument for the contract artifacts, not against them.

Suggested concession + contrast sentence:

> A detect-feedback-replan loop that couples the same LLM (deepseek-3.2, temperature 0) with our deterministic validator repairs every validator-visible violation within at most three feedback rounds (fix rate 1.00 over 65 violations; refusal P/R 1.000) and raises pooled joint accuracy from 0.826 to 0.969 at a mean 1.16 LLM calls per case -- but it plateaus exactly at the boundary of gold-free checkability: all 12 residual errors are requested-set mistakes (unrequested-but-allowed dimensions; time bindings emitted as grouping dimensions) that pass every catalog rule, 9 of which never trigger feedback at all, whereas compiling the contract into the planner yields 1.000 with zero LLM calls.

## Credibility self-assessment

- **High confidence:** direction and mechanism. 0 API errors, 452/452 raw responses stored with usage and prompt SHA-256; validator audited sound against gold before the run; scorer identical (to <1e-9) to released evaluators; branch criteria, seed, thresholds, and feedback templates all fixed in `protocol.md` before the first benchmark call; the 56/0 discordant split makes the improvement direction essentially certain.
- **Moderate confidence:** exact magnitudes. Single model, single run at temperature 0 (provider nondeterminism not resampled); Iowa n=32 has a wide CI [0.893, 1.000] -- "Iowa fully closed" rests on 32 cases; MultiGov is a 200-case seeded subsample (released deterministic baselines reproduce their full-510 values on it to 3 decimals, supporting representativeness).
- **Steelman disclosure (favors the loop):** the validator's refusal triggers, taken verbatim from released evaluator code, adjudicate answer-vs-refuse *perfectly* on these benchmarks, so the loop received a maximally reliable refusal signal including an anti-over-refusal check; production validators would be noisier. Despite this, the gap did not close.
- **Boundary caveat:** the 9 MultiGov residual errors sit on a label-policy line (time window = binding, not dimension). We count them against the loop because the identical released contract is all the compiler needs to get them right; a reader could instead read them as label-policy strictness -- either way they are undetectable by catalog rules, which is the point being tested.
- **Deviation log:** single-case calls instead of the released batch-of-10 prompt (favors the loop; disclosed in protocol section 2). No other deviations from the pre-registered protocol.

## File inventory (all under `new_experiments/validator_feedback_replanning/`)

- `protocol.md` -- pre-registered protocol (branches, loop spec, validator spec, feedback templates, seed)
- `run_loop.py` -- sampler + round-0 schema-RAG prompt builder + deterministic validator + loop runner + mirrored scorer (no keys embedded)
- `multigov_subsample_200.json` -- canonical seeded subsample (seed 20260711)
- `validator_audit.json` -- gold-soundness + trigger-completeness + scorer-identity audit (`overall_pass: true`)
- `prompts/round0_template.txt`, `prompts/round0_example_{layer}.txt`
- `raw_responses/{layer}_loop_raw.jsonl` -- 391 case records, every round: prompt_sha256, latency, usage, verbatim raw response, validator verdict, feedback text
- `per_case_rounds.jsonl` -- 452 lines, one per case per round: {prediction, validator_verdict, feedback_text, raw_response}
- `scores.json` -- per-layer per-round metrics, CIs, violation censuses, fix rates, invisible-error census, cost, branch judgment
- `SUMMARY.md` -- this file
