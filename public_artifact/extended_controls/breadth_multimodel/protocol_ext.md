# H1 Multi-Model Extension: Pre-Registered Protocol

- Pre-registration timestamp (UTC, written BEFORE any experimental benchmark call): **2026-07-11T15:49:56Z**
- Parent protocol: `../h1_instructed_execution/protocol.md` (pre-registered 2026-07-11T11:01:16Z). Everything not explicitly changed here is inherited unchanged.
- Location: `extended_controls/breadth_multimodel/` (writes restricted to this directory).
- Prior LLM calls before this registration: exactly 4 connectivity probes (a trivial "return this fixed JSON object" request, 200 max tokens, no benchmark content) to `claude-sonnet-4.6`@gateway (FAILED, upstream `INVALID_MODEL_ID`), `gpt-5.5`@relay (OK), `claude-opus-4-6`@relay (OK), `kimi-k2.6`@moonshot (FAILED for this protocol: provider rejects `temperature=0`, only 1 allowed). No benchmark case was sent before registration.

## 1. Question (pre-registered)

Three reviewers ask whether the H1 mechanism findings on `deepseek-3.2` — (M1) the same in-prompt governance rule is executed inconsistently (finest-grain violations persist at 22.3% of GovTwin answer plans even with the rule verbatim in-prompt), and (M2) instructed execution over-refuses on grain traps (MultiGov: 75 of 80 errors are false refusals; refusal precision 0.710/0.450/0.500 on MultiGov/GovTwin/ICT) — are deepseek-specific or reproduce on heterogeneous frontier models.

**Pre-registered judgment rule (choose branch only; never adjust numbers):**
- **Reproduced (per model, per mechanism):**
  - M1 reproduces on a model if `finest_grain_violation_rate` > 0 on GovTwin answer plans OR the model both refuses some grain cases citing grain/hierarchy grounds and answers structurally similar grain cases (inconsistent execution), with joint < 1.000 on that layer.
  - M2 reproduces on a model if refusal precision < 1.000 on GovTwin or MultiGov AND false refusals are a nonzero share of its errors, with concentration on `finest_grain_trap` checked and reported either way.
- **Cross-model claim:** if BOTH models show a nonzero contract-conformance gap (any violation class > 0 or refusal precision < 1.000) with joint < 1.000, the paper's mechanism finding upgrades from model-specific to cross-model. If BOTH models reach joint = 1.000 with zero violations and refusal P/R = 1.000, the finding is reported as deepseek-family-specific and the paper claim is narrowed accordingly. Mixed outcomes are reported per model, as-is.

## 2. Models (fixed after probes, before any benchmark call)

| Slot | Planned first choice | Probe result | Model used |
|---|---|---|---|
| Claude family | `claude-sonnet-4.6` @ enterprise gateway | HTTP 400 upstream `INVALID_MODEL_ID` (gateway Claude line down since 2026-07-04, documented in llmhub channels.json) | **`claude-opus-4-6` @ relay** (probe OK; temperature=0 accepted; clean JSON) |
| GPT family | `gpt-5.5` @ relay | probe OK (no 403; temperature=0 accepted; clean JSON) | **`gpt-5.5` @ relay** |

- Reserve `kimi-k2.6`@moonshot is NOT usable under this protocol: the provider hard-rejects `temperature=0` ("only 1 is allowed"), which would break the inherited decoding condition; recorded honestly rather than silently changing temperature.
- Both models run via the relay OpenAI-compatible relay (`$RELAY_BASE`, default `RELAY_ENDPOINT`, key `$RELAY_KEY_DEFAULT`). Model heterogeneity (Anthropic Claude vs OpenAI GPT vs the original DeepSeek) is what the reviewers asked for; channel is an access path, not the model.
- `temperature=0`, `max_tokens=4000`, timeout 240 s, one case per request, concurrency <= 4 (relay etiquette), up to 3 retries (5/15/45 s backoff), failures recorded as `api_error` and scored as wrong non-refusal answers — all inherited from the parent protocol.
- API keys read at runtime from `~/.config/llm_keys.env` (mode 600); never written to any output.

## 3. Scope (cost-controlled, fixed before run)

| Layer | Cases | Rationale |
|---|---|---|
| GovTwin base | all 159 (`govtwin_metric_caliber/test_cases.jsonl`, gold stripped at load) | the M1 layer: deepseek showed 22.3% finest-grain violations and Ref.P 0.450 here |
| MultiGov | stratified subsample n=200 of the 510 released blind cases | the M2 layer: deepseek showed 75/80 false-refusal errors here; full 510 x ~80k prompt tokens x 2 models is the cost driver |

**MultiGov stratified subsampling (deterministic, gold-free):** stratify on `query_family`, a field of the released blind file (no gold leak). Proportional allocation with largest-remainder rounding over the released family counts (answerable_direct 115, denominator_caliber 29, finest_grain_trap 163, policy_refusal 184, temporal_anchor 19):

| family | allocated |
|---|---:|
| answerable_direct | 45 |
| denominator_caliber | 11 |
| finest_grain_trap | 64 |
| policy_refusal | 72 |
| temporal_anchor | 8 |
| **total** | **200** |

Sampler: `random.Random(20260711)`; families processed in sorted name order; within each family, case rows sorted by `case_id`, then `rng.sample(rows, k)`. The chosen `case_id` list is written to `multigov_subsample_case_ids.json` before any API call and is identical for both models. The same 200 cases are also used to recompute the deepseek-3.2 comparison row from the parent run's stored predictions (`../h1_instructed_execution/predictions_multigov.jsonl`) so all three models are compared on the identical case set.

## 4. Prompts (inherited verbatim)

System prompts are the parent run's `prompts/govtwin_system.txt` and `prompts/multigov_system.txt`, byte-identical (the runner re-builds them with the parent's `build_system_prompt` and asserts equality with the saved files before any call; on mismatch it aborts). User template identical (`prompts/user_template.txt`). No few-shot, no gold anywhere in any prompt. `prompt_sha256` computed exactly as in the parent run.

## 5. Parsing and scoring (inherited verbatim)

Parsing rules, normalization, scoring formulas, conformance diagnostics (`metric_not_in_catalog`, `dimension_not_in_catalog`, `dimension_not_allowed`, `finest_grain_violation` over answer-predictions), and Wilson 95% CIs are the parent run's code, imported directly from `../h1_instructed_execution/run_h1.py` (the module whose mirrored scorer reproduced every released baseline row to < 1e-9, `../h1_instructed_execution/scorer_crosscheck.json`, `_overall_match: true`). No new scoring code paths.

Additional pre-registered reporting (descriptive, same formulas):
- per-`query_family` joint accuracy on the MultiGov subsample, per model;
- over-refusal composition: refusal FP count, share of total errors that are false refusals, and family concentration — side by side with deepseek-3.2 restricted to the same 200 cases;
- GovTwin `finest_grain_violation` count/rate per model — side by side with deepseek's 31/139 (22.3%);
- qualitative scan of refusal `reason` strings for grain/hierarchy citations (mechanism M1(ii)); examples quoted from stored raw responses only.

## 6. Outputs (all under this directory)

- `protocol_ext.md` (this file), `multigov_subsample_case_ids.json`
- `raw_responses/<model>_<layer>_raw.jsonl` — every request's raw assistant content + usage + latency + prompt_sha256 + timestamps; api errors recorded per line
- `predictions_<model>_<layer>.jsonl` — parsed + normalized + per-case scored
- `scores_ext.json` — per model x layer metrics, CIs, conformance, family breakdown, over-refusal composition, deepseek same-subset comparison rows
- `SUMMARY.md` — tables, mechanism-reproduction judgment per the Section 1 rule, honest limitations

## 7. Honesty rules binding this run

Inherited unchanged: no mocked output; every prediction traces to a stored raw response; failures reported as-is; whatever direction the data supports is what is reported; single run at temperature 0 with provider nondeterminism acknowledged. The gateway model substitution (Section 2) is disclosed rather than hidden.

## Amendment 1 (2026-07-11, during execution; transport fix, no outcome-based change)

**Observation:** the first 69 MultiGov calls of `gpt-5.5` via the relay **default** key returned systematic schema-nonconformant replies claiming the governance contract "was not provided" — including on answerable cases — while the response `usage` billed the full ~68.8k prompt tokens. `claude-opus-4-6` on the same relay/key executed the identical byte-level prompt correctly, and `gpt-5.5` on the same key had executed GovTwin (~10.4k-token prompt) correctly (0 blindness markers in 159 responses).

**Diagnostics (stored decision basis, not benchmark cases):** (a) a lookup question against the same in-system contract on the default key → "I don't have the actual governance contract contents"; (b) the identical system-role prompt + lookup via the relay **group-B** key → correct catalog lookups; (c) contract moved to the user role on the group-B key → also correct. Conclusion: the default-group gpt-5.5 deployment does not deliver long (~69k-token) system content to the model; this is a channel defect, not model behavior. A default-key quota ceiling (per-request cost gate observed as HTTP 403) independently blocks further ~69k-token gpt-5.5 calls on that key.

**Action:** `gpt-5.5` MultiGov runs use `RELAY_KEY_GROUPB` (same relay URL, ChatGPT-backed group B). The 69 confounded raw records are quarantined on disk as `raw_responses/CONFOUNDED_relaydefault_gpt-5.5_multigov_raw.jsonl` (excluded from scoring, kept for the record). The MultiGov gpt-5.5 run restarts from zero on the group-B key with the identical prompt, cases, and decoding parameters. The completed GovTwin gpt-5.5 run (default key) is retained: it is demonstrably unconfounded (contract-derived aliases cited throughout; zero blindness markers). Channel heterogeneity within gpt-5.5 (GovTwin=default key, MultiGov=group-B key) is disclosed here and in SUMMARY.md.

## Amendment 2 (registered 2026-07-12T03:58:24Z, BEFORE any new benchmark call; scope completion to the full five-layer matrix)

**Trigger:** the relay default key has been recharged (quota outage of Amendment-1 era resolved). Reviewers ask whether "no model attains contract conformance on every layer" holds on ALL five released layers, not just GovTwin+MultiGov. This amendment extends scope only; no question, judgment rule, prompt, decoding parameter, parser, or scoring formula changes.

### A2.1 Scope extension (fixed before any new call)

1. **claude-opus-4-6 MultiGov completion:** run exactly the missing cases = `multigov_subsample_case_ids.json` minus the case_ids with a stored successful record in `raw_responses/claude-opus-4-6_multigov_raw.jsonl` (98 cases at registration time; the runner's resume logic computes this set). Rescore the merged file at full n=200 as the primary MultiGov row for opus. The interim n=102 numbers (and their paired deepseek-on-102 reference) remain disclosed in a SUMMARY.md history section; the interim `scores_ext.json` is archived in this directory as `scores_ext_interim_n102_20260712.json` before being overwritten.
2. **Three remaining layers, both models, full case sets:** ICT (`industrial_case_text_metric_caliber/blind_cases.jsonl`, n=157), Iowa (`iowa_liquor_metric_caliber/test_cases.jsonl`, n=32), Chinook (`data/chinook_metric_cases.jsonl`, n=40). System prompts are the parent run's saved `prompts/{ict,iowa,chinook}_system.txt`, byte-identity asserted before any call (same rule as Section 4). Total new benchmark calls: 98 + 2x(157+32+40) = 556.
3. **Channels:** `claude-opus-4-6` stays on `RELAY_KEY_DEFAULT` (all its prior scored runs used it; key recharged). `gpt-5.5` uses `RELAY_KEY_GROUPB` for all new layers — same channel as its scored MultiGov run — because Amendment 1 proved the default-group gpt-5.5 deployment can silently drop system content; the new-layer prompts are small (~2-6k tokens, far below the observed ~69k defect regime) but channel consistency plus canaries (A2.2) is the safer, disclosed choice. gpt-5.5 GovTwin remains the only default-group gpt-5.5 run (verified unconfounded, retained).
4. Decoding unchanged: temperature=0, max_tokens=4000, timeout 240 s, one case per request, retries 3 (5/15/45 s backoff), failures recorded as `api_error` and scored as wrong non-refusal answers. Concurrency stays <=4 (within the <=6 cap set by the tasking).

### A2.2 Canary rule (transport verification; lesson of Amendment 1, now mandatory)

Before ANY new benchmark call for a (model, layer) pair — including the opus MultiGov resume — run exactly 2 canary calls on the same channel with:
- system message = the layer's exact benchmark system prompt (so the canary exercises the same transport path and prompt length);
- user message = a fixed non-benchmark instruction (no case_id, no nl_query from any case): quote the first 100 characters of the first line of the layer's first contract file, replying as `{"canary":"..."}`.

**Pre-registered pass criterion:** the whitespace-collapsed first 80 characters of the true first line appear in the reply (checked against the parsed `canary` field, the raw content, and the raw content with `\"` unescaped). Both canaries must pass; on any failure, no benchmark call is made on that channel for that layer — diagnose, switch/disclose, and record, exactly as in Amendment 1. Canary records are stored ISOLATED from benchmark records in `raw_responses/canary_<model>_<layer>.jsonl` and are never scored; the runner refuses to start a benchmark run for a (model, layer) with new calls unless its canary file shows 2 passes on the same channel.

### A2.3 Final reporting (pre-committed)

- `scores_ext.json` becomes the full two-model x five-layer matrix (Metric/Dim/Joint + Wilson 95% CI, Ref.P/Ref.R, conformance incl. `finest_grain_violation`, over-refusal composition, MultiGov per-family), each layer paired with the deepseek-3.2 reference re-scored on the identical case set from the parent run's stored predictions (identity on full-set layers).
- The Section 1 judgment rule is applied verbatim, per model per mechanism, now with the five-layer evidence. Additionally — answering the reviewers' direct question — SUMMARY.md must state whether "no model attains contract conformance on every layer" holds across all five measured layers, reporting per-model per-layer joint error counts in k/n form (e.g. 158/159 correct = 1 error).
- SUMMARY.md is rewritten as the final version (with a history section retaining the interim n=102 opus MultiGov disclosure and the Amendment-1 record), including suggested replacement text for the paper.
- Honesty rules of Section 7 bind unchanged: no mocked output, every prediction traces to a stored raw response, deviations disclosed, results reported whatever their direction, keys never written to any output, writes restricted to this directory.

## Amendment 3 (registered 2026-07-12T05:08:34Z; canary wording revision after a canary-design confound; no benchmark change)

**Observation (execution record):** the A2.2 canaries PASSED 2/2 for claude-opus-4-6 on all four pending layers (multigov/ict/iowa/chinook; opus then completed all its batches with 0 error records). They FAILED 0/2 for gpt-5.5 on ict/iowa/chinook, and the A2.2 gate blocked those three batches as designed.

**Diagnosis (from the six stored records in `raw_responses/canary_gpt-5.5_{ict,iowa,chinook}.jsonl`):** this is NOT the Amendment-1 transport blindness. All six replies are (a) exactly in the contract's mandated output schema, and (b) refusals whose `reason` reproduces policy P2(g) language that exists only inside the system prompt (e.g. "Request contains no recognizable governed metric or scope from the contract"), with plausible billed prompt tokens (2.2k-3.8k). Both facts are unknowable without the system prompt being delivered. The model executed the governance contract literally and classified the canary meta-request ("quote the first line") as an off-domain/no-governed-scope request => refuse — which is arguably contract-CONFORMANT behavior, whereas opus prioritized the newer diagnostic instruction over the contract. Instructive behavioral difference; recorded in SUMMARY.md, never scored.

**Action:** canary user message revision 2, used for the gpt-5.5 reruns on ict/iowa/chinook only: the diagnostic now instructs the model to comply with P2 by replying `action="refuse"` AND to embed the exact first 100 characters of the first line of the layer's first contract file inside its `"reason"` field. The **pass criterion is UNCHANGED** (whitespace-collapsed first 80 chars of the true first line must appear in the reply). 2 passes required before the batch, same as A2.2. Rev-1 failed records remain on disk in the same canary files (isolated, unscored). No benchmark prompt, decoding parameter, parser, or scoring rule changes. Opus results are untouched (its canaries passed under rev-1).

**Rev-2 outcome (recorded 2026-07-12, before rev-3):** rev-2 also failed 0/2 on ict (records on disk): gpt-5.5 again replied schema-conformant refusals ("catalog excerpt/dump requests are not allowed"), i.e. it declines to reproduce contract text under any framing while continuing to cite contract policy language. Quotation-based canaries are unusable for this model; visibility must be tested behaviorally.

**Rev-3 (registered 2026-07-12 before running; final canary design for gpt-5.5 ict/iowa/chinook):** the canary is a benchmark-STYLE alias-resolution probe — a natural-language query, phrased like the layer's answerable cases but colliding with NO released case's `nl_query` (verified programmatically), using a metric alias whose `metric_id` binding exists only in the layer's metric catalog:
- ict: "上个月补发损失" — alias 补发损失 binds to `ict_metric_004` (numeric suffix knowable only from the catalog);
- iowa: "What was the AOV overall?" — alias AOV binds to `average_invoice_value` (a blind guess would produce average_order_value);
- chinook: "What was the ARPC last year?" — alias ARPC binds to `revenue_per_customer` (weakest probe, id semi-guessable; accepted with this disclosure, in combination with the rev-1/rev-2 evidence that the model reproduces P2 policy language from the system prompt).

**Rev-3 pass criterion (pre-registered):** the reply parses as the mandated JSON schema AND the target `metric_id` string appears in the reply. 2/2 passes required per layer before the batch, same gate. All rev-1/rev-2/rev-3 records stay isolated in the same canary files, never scored; canary queries are excluded from every benchmark statistic (they are not in any case file).
