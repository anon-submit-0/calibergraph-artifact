# P1a Pre-Registered Protocol — Entropy-Based Confidence Abstention Baseline (frozen before any benchmark LLM call)

Registered: 2026-07-14 (Asia/Shanghai). Release: V28CC. Status at registration: **FROZEN**.
Reimplementation target: Somov & Tutubalina, *Confidence Estimation for Error Detection in Text-to-SQL Systems*, AAAI-25, DOI 10.1609/aaai.v39i23.34699 — adapted from text-to-SQL error detection/abstention to the governed NL2Metric interface of this paper.

## 0. Honesty declarations

- **No mock**: every prediction traces to a stored raw gateway response (`raw/*.jsonl`). Failures are recorded verbatim; missing/API/parse failures are never imputed.
- **Calls preceding this registration**: exactly TWO transport canaries, neither containing any benchmark case:
  1. connectivity canary (`Reply with exactly: OK`, temperature 0, max_tokens 20) → HTTP 200, content `OK`, `logprobs` field absent;
  2. logprobs probe (same trivial prompt, request body `"logprobs": true, "top_logprobs": 5`) → HTTP 200, content `OK`, response `choices[0].logprobs = null`.
- **Disclosed degradation**: the gateway does not return token logprobs for `deepseek-3.2` even when explicitly requested (canary 2 above). Token-level entropy (the white-box arm of the AAAI-25 setup) is therefore not implementable through this transport. We use the black-box **sampling-consistency entropy** over k=5 sampled answers (temperature 0.7), i.e. the entropy of the empirical distribution over normalized answer tuples — the standard black-box self-consistency confidence surrogate. This corresponds to the AAAI-25 paper's black-box/closed-model setting rather than its logit-based setting; we state this in the paper wherever the baseline is cited.
- Key read at runtime only from `~/.config/llm_keys.env` (mode 600); never logged, never copied.

## 1. Role of this baseline in the paper (borrowed target)

The contrast matrix seals seven alternative routes; the missing slot is "uncertainty-based abstention". Hypothesis under test (mechanism-level): uncertainty abstention passes through error families ① metric identity, ② caliber, ③ grain, ④ temporal/coverage indiscriminately — **caliber errors are confident errors** and generate no uncertainty signal — while ⑤ refusal may carry partial signal.

## 2. Model and transport (mirror of verified H1 transport layer)

- Model: `deepseek-3.2` via <anon> gateway (`<anon>_GW_BASE`, default `<GATEWAY_BASE>`, endpoint `/chat/completions`), key env `<anon>_GW_KEY`.
- Sampling: `temperature = 0.7`, `max_tokens = 4000`, **k = 5 independent samples per case** (5 separate requests; the gateway `n` parameter is not relied upon).
- Timeout 240 s; retries per sample ≤ 3 with backoff [5, 15, 45] s; concurrency 6.
- Raw record per (case_id, sample_idx): prompt SHA-256, attempts, latency, usage, finish_reason, raw content or verbatim error. Resumable: completed (case_id, sample_idx) pairs are skipped on rerun.

## 3. Prompting condition: Schema-RAG (round-0 mirror)

Prompts are byte-identical mirrors of the released Schema-RAG round-0 prompt (`llm_schema_rag`) as implemented in the frozen validator-feedback protocol:
`<REPO_ROOT>/(release)/anon_repo_calibergraph/public_artifact/extended_controls/validator_feedback_replanning/run_loop.py`
(functions `rank_metrics_govtwin`, `rank_metrics_multigov`, `score_text_multigov`, `text_score_5`, `metric_line`, `dim_line`, `ROUND0_TEMPLATE`, `build_round0_prompt`; retrieval top-5 metrics + all dimensions). The runner in this directory vendors those functions verbatim; per-layer example prompts are saved under `prompts/`.

## 4. Evaluation layers (group-B V24 contract layer, blind protocol)

Benchmark root: `<REPO_ROOT>/releases/v24_group-B_evidence_fusion_submission_20260712/public_artifact/public_benchmark/`

| Layer | Cases | Prediction input | Scoring input |
|---|---|---|---|
| GovTwin-159 | 159 (all) | `govtwin_metric_caliber/blind_cases.jsonl` | `govtwin_metric_caliber/gold_labels.jsonl` |
| MultiGov-200 | 200 seeded subset | `multigov_metric_caliber/blind_cases.jsonl` | `multigov_metric_caliber/gold_labels.jsonl` |

- **MultiGov-200 subset**: the task allowed sampling with seed=20260712 only if no existing seeded definition was found. An existing **canonical** definition WAS found and is reused verbatim (it is declared canonical and mandatory for extensions in its own frozen protocol): `_20260712/.../validator_feedback_replanning/multigov_subsample_200.json`, seed **20260711**, stratified by `query_family` with largest-remainder proportional allocation → {policy_refusal 72, finest_grain_trap 64, answerable_direct 45, denominator_caliber 11, temporal_anchor 8}. SHA-256 `3b01f8e6668943b63a5df942a94b0741c518a8bcc6837b65d505de2494a2f5cc`. This also makes results directly comparable to the paper's existing "same MultiGov-200 cases" rows.
- Blind guard: every case sent to the LLM is asserted to contain no `expected_*` or `*_hash` field.
- Total: 359 cases × 5 samples = 1795 calls.

Input file SHA-256 (frozen):
- govtwin blind_cases `06a9802e451142be846a4158f5b289eb22b9279b315628790517879908c1f394`, gold_labels `b40751be0615ba72f13ef922585f5af9b0960a650db990d0433c0f4c49951eba`, metric_catalog `d3fa633ff8ec87abd70ecc030f52edc54dea10b99fcd8fbbffa4a8ac4b2b3be3`, dimension_catalog `9defe52af986c1dc20f20bac1fdcc15e638c2a8b45d8a67e2131fb0ceadf05c4`
- multigov blind_cases `41d1fdfb4fc5799a0df3ff58d45b009fbdf2276f5005b8606ab3246c97c01345`, gold_labels `46cc0c4f5b0792d72eae63c485d913a5da691b28ce5e5a3644f400c07c23695b`, metric_catalog `3881401c18b1a90730e098129f7aea0b28dff4db622de5a73d396ceff703b88f`, dimension_catalog `6deea320148b6f88b28eace486368df9ad6b4e882be68d59e678333b60c595c5`

## 5. Parsing and answer normalization (H1 mirror, frozen)

Per sample: strip `<think>` blocks and code fences; parse JSON, else first balanced brace block; on failure → parse status `parse_error`. Normalized answer tuple:
`A = (action, metric_id, sorted(set(dimensions)))` where `action ∈ {answer, refuse}`; if `action = refuse` then `metric_id=""`, `dimensions=[]`; any non-refuse action label is treated as `answer` (H1 convention). A sample with `parse_error` or exhausted API error is a distinct tuple `("__invalid__", "", ())` — it counts as disagreement mass, honestly reflecting that an unparseable answer is not a consistent answer. `time_window` is recorded but excluded from the tuple (the released joint score does not include it; declared here to prevent post-hoc flexibility).

## 6. Confidence signal and abstention thresholds (all three reported; none selected post hoc)

For each case, let counts over the 5 tuples be `c_1 ≥ c_2 ≥ …`; plurality answer = tuple with count `c_1` (tie among modal tuples broken by earliest sample index — deterministic). Sampling-consistency entropy `H = −Σ (c_i/5)·log2(c_i/5)`; reported per case.

Three abstention arms (τ), **all reported, no best-arm selection**:
- **τ = unanimous**: answer (with plurality tuple) only if `c_1 = 5` (H = 0); else abstain.
- **τ = majority**: answer only if `c_1 ≥ 3`; else abstain.
- **τ = any**: never abstain; always emit plurality tuple (the k=5 self-consistency reference arm).

Abstention is a *decision to not emit* — distinct from a predicted `refuse` tuple, which is a governance answer. Both interpretations are scored (see §7.4).

## 7. Scoring (frozen formulas)

Gold: `expected_action`, `expected_metric_id`, `expected_dimensions` from gold_labels. Released-scorer mirror predicates per case (on the emitted tuple): `metric_ok = (pred_metric_id == expected_metric_id)`; `dim_ok = set(pred_dimensions) == set(expected_dimensions)`; `joint_ok = metric_ok ∧ dim_ok`; `refused = (action=refuse ∨ pred_metric_id="")`. **Full-case correctness (action-aware)**: for `expected_action=refuse` cases, correct iff `refused`; for answer cases, correct iff `¬refused ∧ joint_ok`.

Per layer and pooled (359), per arm:
1. **Answered subset**: n_answered, abstention_rate, joint accuracy on answered subset (released mirror), full-case correctness on answered subset, plus overall "selective" accuracy treating abstained as neither right nor wrong (reported as coverage–accuracy pair).
2. **Would-be-error definition**: a case is a *would-be error* iff the plurality tuple (τ=any arm) fails full-case correctness. Five error families by case `query_family` (frozen mapping):
   - MultiGov: `answerable_direct`→① metric identity; `denominator_caliber`→② caliber; `finest_grain_trap`→③ grain; `temporal_anchor`→④ temporal/coverage; `policy_refusal`→⑤ refusal.
   - GovTwin: `single_or_flat_dimension`→① metric identity; `hierarchy`→③ grain; `synthetic_refusal`→⑤ refusal. (GovTwin base split contains no ②/④ family cases and a single caliber; disclosed, not hidden.)
3. **Abstention coverage per family** (the headline mechanism number): for each arm and family F, `coverage(F) = |abstained ∩ would-be-error ∩ F| / |would-be-error ∩ F|`. Random-abstention reference = arm's overall abstention rate among would-be errors; per family we also report **lift** = coverage(F) / overall abstention rate (all cases) and a two-sided Fisher exact test on the 2×2 (abstained × would-be-error) within family and pooled.
4. **Refusal P/R** two readings: (a) plurality-tuple refusal P/R over all 359 (τ=any); (b) abstention-as-refusal: abstained OR refused counts as refusal, per arm.
5. **Cost**: total calls, prompt/completion tokens, mean latency; compared against single-call baselines (k=5 ≈ 5× marginal sampling cost).

## 8. Pre-registered branch judgment

- **Branch (i)** — abstention signal has no discriminative power on caliber errors: coverage(② caliber) is statistically indistinguishable from the random-abstention reference (Fisher p ≥ 0.05) or ② would-be errors are predominantly unanimous-confident (c_1=5 among ② errors ≥ 50%): the mechanism claim "caliber errors are confident errors" stands; write the paper paragraph accordingly.
- **Branch (ii)** — coverage(② caliber) significantly exceeds the random reference (Fisher p < 0.05 with lift > 1): report honestly, and compare its price: k=5 sampling cost and the abstention-rate loss on correct answers (false-abstention rate). No suppression in either branch.
- Small-cell honesty: ② family has 11 MultiGov cases; if ② would-be errors number < 5, we report exact counts and label the branch judgment as underpowered rather than claiming significance either way.

## 9. Deliverables

`protocol.md` (this file, frozen), `run_entropy_abstention.py`, `prompts/`, `raw/{govtwin,multigov}_raw.jsonl`, `predictions_{govtwin,multigov}.jsonl`, `scores.json`, `RESULT.md` (中文).

## 10. Freeze

This protocol is frozen before the first benchmark call. Any later edit must be recorded as a dated AMENDMENT section without altering the sections above.

---

## AMENDMENT 1 (2026-07-14, transport-only; precedent: V24 transport amendments)

**Observed failure**: GovTwin completed 795/795 with 0 error records. The MultiGov run stalled at 191/1000 raw records: last record ts 2026-07-14T04:53:06Z, zero progress for 82 minutes (checked 06:15:22Z), process alive but all 6 workers wedged. Root cause: `urllib` `timeout` bounds each socket operation, not total request wall-clock; a gateway connection that trickles bytes or wedges mid-body holds a worker indefinitely, so the frozen 240 s socket timeout never fired.

**Change (transport layer only; no change to model, prompts, temperature, k, case scope, parsing, scoring, arms, or branch judgment)**:
- socket-level timeout 240 s → 110 s;
- new hard wall-clock deadline of **120 s per attempt** enforced by a daemon-thread join; an expired attempt raises `HardTimeout` and is a retryable failure;
- retries unchanged (≤3 with backoff [5, 15, 45] s); after exhaustion the sample is recorded as an honest `error` row and skipped (per section 5 it enters aggregation as the `__invalid__` tuple);
- the stalled process was killed; the run resumes from the 191 completed (case, sample) pairs via the pre-registered resumability.

All 191 records completed before the stall are retained unchanged (0 error records among them). Frozen-section SHA-256 (sections 0–10 above, unchanged): `01e35be46b462314b2ac68336b2ceb6eee5e2545e6974486611af1997c991f27`.
