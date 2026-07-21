# Pre-Registered Protocol Extension: Strongest-Model Controls on the Private 159-Case Set (gpt-5.5 and claude-opus-4-6, Arms C/D)

- Frozen at: 2026-07-12T14:13+0800 (written BEFORE any experimental LLM call for this study; the only prior calls to these two models were in `../h1_multimodel_extension/`, a different study on public layers)
- Location: `new_experiments/private_strongest_controls_multimodel/` (internal author evidence tier; NOT part of the public artifact)
- Parent protocol: `../private_strongest_controls/protocol.md` (frozen 2026-07-12T02:12+0800). This extension inherits EVERY design choice of the parent protocol verbatim — dataset, pairing, Arm C prompt construction, Arm D loop construction, deterministic validator, parsing/normalization, scoring, statistics — and changes ONLY (i) the model/channel, (ii) per-model max_tokens (declared below), (iii) a per-model canary gate (Amendment-1 lesson from `../h1_multimodel_extension/protocol_ext.md`), and (iv) output file names.
- Purpose (fifth internal meta-review): the last surviving alternative explanation for the private-set competitive result is "a strongest frontier model (plus a repair loop) would overtake the compiler; deepseek-3.2 is just not strong enough." This study runs the SAME two strongest prompting-side controls with gpt-5.5 (primary) and claude-opus-4-6 (secondary) on the identical 159 private cases, case-paired against the retained CaliberGraph arm.

## Honesty commitments (binding; identical to parent §"Honesty commitments")

1. No fabrication. Every prediction traces to a stored raw model response under `raw_responses/` (written before scoring).
2. Results are reported whichever way they fall. The three pre-registered endings (section 6) are all valid and publishable, including the ending where gpt-5.5 or claude-opus-4-6 reaches or exceeds 0.925 and the paper's competitive claim must be relinquished and migrated to by-construction properties.
3. Data is read-only. No file outside `new_experiments/private_strongest_controls_multimodel/` is written.
4. Privacy redline: identical to parent §Honesty-4. No private raw query text and no private business rows in `protocol_ext_models.md`, `per_case_pairs_models.jsonl`, `mcnemar_models.json`, or `SUMMARY.md` — case ids, governance identifiers, correctness booleans, SHA-256 hashes, and aggregate statistics only. Prompts are NOT persisted (SHA-256 + char counts only). Raw LLM responses are persisted under `raw_responses/` for auditability; that directory stays in the internal evidence tier and requires the same desensitization mapping before any release.
5. No API keys in any output file. Keys read at runtime from `~/.config/llm_keys.env` (never logged, never persisted).

## 1. Dataset, pairing, reference arms (fixed; inherited)

- Cases: the same 159-case loader (`scripts/run_llm_metric_eval.py::load_cases()` over the read-only StarRocks mirror `gov_semantic_test_case.tsv.gz`); n=159 asserted.
- Arm A (CaliberGraph, deterministic compiler): per-case flags TAKEN AS-IS from `../private_paired_rerun/per_case_pairs.jsonl`; joint = 147/159 = 0.9245283. The scorer asserts this sum before writing any result.
- Deterministic validator + its LLM-free soundness audit: inherited unchanged from the parent study (`../private_strongest_controls/validator_audit.json`); the validator is byte-identical code (imported from the parent runner module, not copied). Pre-registered validator ceiling carries over: 156/159 = 0.981 > 0.925, so a fully compliant model CAN beat the compiler — the loop is not rigged.
- Reference arms for secondary comparison (already run, values fixed): deepseek-3.2 Arm C = 124/159 = 0.780; Arm D round 0 = 124/159 = 0.780; Arm D final = 143/159 = 0.899 (all from `../private_strongest_controls/mcnemar_ext.json`); Arm B Schema-RAG paired rerun = 127/159 = 0.799 (published 0.849).

## 2. Models, channels, decoding (the ONLY experimental change)

| Model | Role | Channel | Endpoint | Key env | max_tokens |
|---|---|---|---|---|---:|
| `gpt-5.5` | primary strongest model | relay group B | `RELAY_ENDPOINT/chat/completions` | `RELAY_KEY_GROUPB` | 16000 |
| `claude-opus-4-6` | secondary strongest model | relay default group | `RELAY_ENDPOINT/chat/completions` | `RELAY_KEY_DEFAULT` | 8000 |

- Channel provenance: exactly the channels validated in `../h1_multimodel_extension/` (gpt-5.5 on the group B per its Amendment 1 — the default group demonstrably drops long system messages; claude-opus-4-6 on the default group, which passed all its canaries there).
- temperature=0 for both. max_tokens raised from the parent's 4000 because gpt-5.5 is a server-side reasoning model (reasoning tokens are billed inside the completion budget; 45–2,000+ observed in the h1 extension) — the standing lab rule is reasoning budget ×4 and ≥8k. Declared deviation, same class as the parent's declared 3500-vs-4000 note: max_tokens only bounds output length; a larger bound can only prevent truncation-induced parse errors, which would be scored AGAINST the model, so this choice favors the baseline, not the compiler.
- timeout 240 s; retry backoff [5, 15, 45] s on transport errors/empty content only, never on content; concurrency ≤ 6 per channel; resumable per case; every call's raw output persisted before scoring.

## 3. Canary gate (pre-registered; Amendment-1 lesson; runs BEFORE each model's benchmark calls)

- Per model: 2 canary calls using the EXACT Arm C system prompt (identical bytes to the benchmark's system prompt), user message = a transport diagnostic that (a) tells the model to refuse under the contract's P2 (the diagnostic names no governed metric — refusing is the contract-correct action), and (b) requires the `reason` field to reproduce verbatim the first 100 characters of the first line of the governance contract block. That first line is the serialization header (`----- metric_catalog (18 metrics; ...) -----`) — a code-defined string containing no private business text.
- Pass criterion (same as h1 A2.2): the whitespace-collapsed first 80 characters of the true first line appear anywhere in the reply (parsed field, raw text, or raw with `\"` unescaped). 2/2 passes required; the runner hard-blocks benchmark calls for a model without 2 recorded passes on disk.
- Isolation: canary records carry `is_canary: true` and case_id `__canary_N__`, live in separate files `raw_responses/canary_<model>.jsonl`, and are never scored. Any confounded records (wrong channel/config) would be quarantined in `CONFOUNDED_*`-prefixed files, never mixed.
- Rationale: the h1 study proved a deployment can silently drop a long system message while still billing prompt tokens; without this gate an Arm C failure would be uninterpretable (model failure vs. transport failure).

## 4. Arms (inherited verbatim from parent §3–§4)

- Arm C-⟨model⟩ — instructed-execution: one shared system prompt = complete private governance contract verbatim (18-metric catalog ⋈ nodes ⋈ aliases ⋈ measures_of, 5-dimension catalog, all 129 edges) + released policy text quoted verbatim + policy obligations P1–P6 + execution directive + strict single-JSON-object output format. Built by the parent's `build_system_prompt()` (imported, byte-identical). Per-case user message = parent's `USER_TEMPLATE`. Parsing/normalization = parent's H1 mirror (`parse_single_object` + `normalize_c`; parse failure ⇒ `__parse_error__`, scored as a non-refusal wrong answer).
- Arm D-⟨model⟩ — validator-feedback replanning loop: round 0 = the ORIGINAL private Schema-RAG prompt (`build_prompt("llm_schema_rag", [case], ...)`, single-case batch, retrieval k=6/k=5); ≤3 repair rounds; feedback = parent's `FEEDBACK_TEMPLATE` with quoted released rule text per violation; deterministic validator R1–R8 = parent's `validate()` (imported, byte-identical); loop stops early on validator pass. Parsing/normalization = parent's (`parse_round0`/`parse_single_object` + `normalize_d`; persistent parse failure normalizes to refuse, as Arm B scored).
- Order of execution: canaries (both models) → Arm C-gpt-5.5 ∥ Arm C-claude-opus-4-6 (different channels/keys, ≤6 concurrent each) → Arm D-gpt-5.5 ∥ Arm D-claude-opus-4-6 → scoring. Scoring is a deterministic function of the append-only raw files.

## 5. Scoring and statistics (inherited verbatim from parent §5–§6)

- Per case: `metric_ok` := pred_metric_id == expected_metric_id (refusal = empty string); `dim_exact` := set equality; `joint` := both. Refusal P/R with refused := action=refuse or empty pred metric. Arm D scored at round 0 and at final round (primary endpoint).
- For each arm X in {C-gpt, D-gpt-final, C-opus, D-opus-final} (and descriptively for the two round-0 arms), paired against Arm A on joint over the same 159 cases: (1) contingency + McNemar exact two-sided p; (2) paired bootstrap 95% CI on Δ = acc_A − acc_X, B=10,000, seed=20260711, percentile; (3) Wilson 95% CI per arm; (4) refusal P/R. Arm D loop diagnostics: round-0 vs final sign test, violation census round0/final, validator-invisible errors at final, LLM calls per case, token totals (compiler reference: 0 calls).
- Multiplicity: the branch decision (section 6) is taken on raw point estimates against the fixed 0.9245283 threshold, exactly as in the parent protocol — no p-value gating, so no multiplicity correction affects the branch. McNemar p-values are reported per arm unadjusted AND with Holm–Bonferroni across the 4 primary arms, both disclosed.

## 6. Branch decision rule (pre-registered; the judgment question)

Primary question: does ANY of the four primary arms (C-gpt, D-gpt-final, C-opus, D-opus-final) reach joint ≥ 0.9245283 (= Arm A's 147/159) on the private set?

- (a) OVERTAKEN / ERODED — some arm ≥ 0.925: the "strongest model (+repair loop) overtakes the compiler" explanation is CONFIRMED for that arm. SUMMARY.md must state this plainly and recommend migrating the paper's primary claim entirely to the by-construction properties (deterministic policy conformance, structured refusal precision 1.0 by construction, zero plan-time LLM calls, auditability, cost), reporting the winning arm's full cost profile (calls, tokens, validator engineering that itself instantiates the released policy) as the price of parity/superiority. The competitive table must still ship — with the unfavorable number in it.
- (b) PARITY — all arms < 0.925 but the best arm's McNemar p vs Arm A ≥ 0.05: the point-estimate gap survives but paired superiority over the strongest-model control may NOT be claimed (same posture as the parent study's Arm D verdict). Recommended wording: architectural claim framed jointly with the deepseek replan-loop result — near-parity is obtainable across model families only by importing the compiled governance policy as the repair oracle; residual errors concentrate in validator-invisible metric/caliber selection.
- (c) GAP SURVIVES SIGNIFICANTLY — all arms < 0.925 and every primary arm's McNemar p < 0.05 (Holm-adjusted also reported): the competitive margin survives the strongest models under the strongest controls; the paper may report cross-model-family robustness of the margin.
- Mixed outcomes (e.g., significant vs C-arms, non-significant vs D-arms) are reported arm-by-arm under the same rules; the paper's claim strength is set by the WEAKEST-for-us primary arm (i.e., the arm most favorable to the baseline side).
- Secondary reporting either way: cross-model table including deepseek-3.2 arms; loop gains (round0 → final) per model; refusal P/R movements; validator-invisible residual census per model.

## Amendment 1 (registered 2026-07-12T14:17+0800; canary wording revision for gpt-5.5 ONLY; no benchmark change; no benchmark call has been made yet)

- Observed (records on disk in `raw_responses/canary_gpt-5.5.jsonl`, isolated, never scored): gpt-5.5 failed the quotation canary 0/2 — it replied schema-conformant refusals citing "P2" (a policy label that exists ONLY in the system prompt), i.e. the contract is demonstrably delivered, but the model declines to reproduce contract text under any framing. claude-opus-4-6 passed the quotation canary 2/2; its gate is open and unchanged.
- This is the exact failure mode pre-documented in `../h1_multimodel_extension/protocol_ext.md` Amendment 3 ("quotation-based canaries are unusable for this model; visibility must be tested behaviorally"), where the pre-registered fix was a rev-3 behavioral alias-resolution probe. The same fix is adopted here, adapted to the private layer:
  - Probe construction (deterministic, collision-free): probe metric = `sale_qty`. The probe alias is selected at runtime as the first catalog-order metric alias of `sale_qty` that appears as a substring in NONE of the 159 benchmark `nl_query` texts (verified at selection time; the alias↔metric binding exists only inside the private contract). Probe query = `上个月` + alias + `是多少` — a constructed sentence colliding with no released case, containing no refusal trigger and no grouping token, so the contract-correct behavior is action="answer", metric_id="sale_qty", dimensions=[].
  - Rev-3 pass criterion (pre-registered): the reply parses as the mandated JSON schema AND the target id string `sale_qty` appears in the raw reply. 2/2 passes required; same hard gate.
  - Privacy: the probe record stores the probe's SHA-256 and the target metric id (a governance identifier, explicitly permitted) — not the probe text; rev-3 records carry `canary_rev: 3` in the same isolated canary file, never scored, excluded from every benchmark statistic.
- Rationale for validity: producing `sale_qty` for its Chinese alias is possible only if the metric catalog inside the system prompt is visible to the model; combined with the recorded "P2" citation (policy block visible), a rev-3 pass establishes end-to-end contract delivery at least as strongly as a verbatim quote.

## 7. Outputs (all under this directory only)

- `protocol_ext_models.md` (this file, frozen before the run)
- `run_strongest_controls_models.py` (the runner; imports the parent runner module for byte-identical prompt/validator/scoring code)
- `raw_responses/canary_<model>.jsonl`, `raw_responses/armC_<model>_raw.jsonl`, `raw_responses/armD_<model>_loop_raw.jsonl` (internal tier; prompt SHA-256 only, no prompt text)
- `per_case_pairs_models.jsonl` — one line per case: case_id, query SHA-256, expected ids, Arm A flags, and per model the Arm C prediction+flags and Arm D round-0/final prediction+flags, rounds used, final validator verdict
- `mcnemar_models.json` — per-arm accuracies, contingencies, McNemar p (raw + Holm), bootstrap CIs, branch verdict
- `SUMMARY.md` — human-readable report incl. the three-branch paper-wording recommendation and credibility self-assessment
