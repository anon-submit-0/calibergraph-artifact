# H1 Multi-Model Extension Results: Do the deepseek-3.2 Mechanism Findings Reproduce on Heterogeneous Frontier Models?

- Protocol: `protocol_ext.md` (pre-registered 2026-07-11T15:49:56Z before any benchmark call; Amendment 1 = transport fix, disclosed below). Parent: `../h1_instructed_execution/` (deepseek-3.2, 898 cases).
- Condition: byte-identical verbatim-contract instructed-execution prompts (asserted equal to the parent run's saved `prompts/*_system.txt` before every run), `temperature=0`, `max_tokens=4000`, one call per case.
- Models: **`claude-opus-4-6`** (a commercial relay, default group) and **`gpt-5.5`** (a commercial relay; GovTwin on default group, MultiGov on group B per Amendment 1). Planned `claude-sonnet-4.6`@enterprise gateway was upstream-broken (`INVALID_MODEL_ID`, probed before registration); `kimi-k2.6` rejects `temperature=0` and was ruled out before registration.
- Scope: GovTwin base full 159; MultiGov stratified subsample n=200 (seed 20260711, allocation pre-registered, ids in `multigov_subsample_case_ids.json`, sha256 `010e0b16...`). deepseek-3.2 comparison rows are **re-scored from the parent run's stored predictions on exactly the same case sets** (same scorer code, imported from `../h1_instructed_execution/run_h1.py`, whose mirrored scorer reproduced every released baseline row to <1e-9; see parent `scorer_crosscheck.json`).
- Raw responses: 159+159+102+200 = 620 scored calls, all stored with usage/latency/prompt_sha256; plus 69 quarantined confounded calls and 16 quota-403 error records kept on disk. No mocked output anywhere.

## Execution record and protocol deviations (all disclosed)

1. **Amendment 1 (transport confound, fixed mid-run):** the first 69 MultiGov gpt-5.5 calls via the relay **default** group returned 0/69 schema-conformant outputs, 61/69 explicitly claiming the governance contract "was not provided" — while `usage` billed the full ~68.8k prompt tokens, and while `claude-opus-4-6` executed the byte-identical prompt correctly on the same key. Stored diagnostics (catalog-lookup probes) proved the default-group gpt-5.5 deployment does not deliver long (~69k-token) system content to the model; the group-B deployment reads the identical prompt correctly. The 69 records are quarantined in `raw_responses/CONFOUNDED_relaydefault_gpt-5.5_multigov_raw.jsonl` (excluded from scoring, kept for the record); MultiGov gpt-5.5 was rerun from zero on the group-B key: 200/200, 0 errors, 200/200 schema-conformant.
2. **Partial claude-opus-4-6 MultiGov (quota outage):** after 102 successful responses the relay default key hit a per-request cost gate (HTTP 403 "token quota is not enough", remaining $0.158 < required ~$0.317 per 83k-token call). 16 quota-403 error records are on disk; 82 cases were never attempted. No alternative Claude channel exists (gateway Claude line re-probed and still broken; group B is GPT-only; AWS-group key is user-disabled). **Primary scoring is the completed subset n=102, paired with a deepseek-3.2 reference on the identical 102 cases.** The protocol-literal full-set scoring (missing/api_error scored as wrong; joint 0.505) is reported in `scores_ext.json` as `claude-opus-4-6__protocol_literal_full_set` — its depressed numbers measure the quota outage, not the model, and are not used for any claim. Family composition of the completed 102: answerable_direct 22, policy_refusal 38, finest_grain_trap 33, denominator_caliber 4, temporal_anchor 5 (all five families represented).
3. gpt-5.5 channel heterogeneity: GovTwin ran on the default group (verified unconfounded: contract-derived aliases cited throughout; 0 blindness markers in 159 responses; ~10.4k-token prompt is below the defect threshold), MultiGov on the group B.

## Headline tables (mirrored scorer; deepseek rows re-scored on identical cases; CaliberGraph = released 1.000 rows)

### GovTwin base (n=159, identical cases for all three models)

| Model | Metric | Dim. | Joint [Wilson 95%] | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|
| deepseek-3.2 (parent run) | 0.931 | 0.748 | 0.736 [0.662-0.798] | 0.450 | 1.000 |
| claude-opus-4-6 (new) | 0.943 | 0.956 | 0.899 [0.843-0.937] | 0.000* | 0.000* |
| gpt-5.5 (new) | 0.994 | 1.000 | **0.994** [0.965-0.999] | 1.000 | 1.000 |
| CaliberGraph (released) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

\* Formatting artifact, not refusal behavior: claude-opus-4-6 refused all 9 gold-refusal cases with **semantically correct reasons but a systematically malformed JSON refusal template** (`"time_window":","reason"...` — identical one-character defect in all 9 refusals at temperature 0). Per the pre-registered parse rule these score as wrong non-refusal answers, hence Ref.P/Ref.R = 0.0. Opus produced **zero false refusals** on GovTwin.

claude-opus-4-6 errors (16): 9 refusal-template glitches (above) + 7 flat queries (gold `[]`) where all five `allowed_dimensions` were dumped into the plan, which — because segment_l1/l2/l3 are one hierarchy — are simultaneously **finest-grain violations**. Opus resolved all nine hierarchy cases that deepseek had executed inconsistently (govtwin_0017/0018/0021/0077/0090/0096/0098/0128/0141) correctly.
gpt-5.5 errors (1): govtwin_0069, mid-emission JSON corruption (right metric `event_count_b`, `dimensions` key dropped); scored wrong per parse rule.

### MultiGov stratified subsample (n=200; opus column = completed subset n=102 with paired deepseek reference)

| Model | n | Metric | Dim. | Joint [Wilson 95%] | Ref.P | Ref.R |
|---|---:|---:|---:|---:|---:|---:|
| deepseek-3.2 (same 200) | 200 | 0.820 | 0.815 | 0.815 [0.755-0.863] | 0.673 | 1.000 |
| gpt-5.5 (new, group-B) | 200 | 1.000 | 1.000 | **1.000** [0.981-1.000] | 1.000 | 1.000 |
| deepseek-3.2 (same 102) | 102 | 0.814 | 0.804 | 0.804 [0.717-0.869] | 0.679 | 1.000 |
| claude-opus-4-6 (new, n=102 completed) | 102 | 0.990 | 0.990 | **0.990** [0.947-0.998] | 0.974 | 1.000 |
| CaliberGraph (released) | 510 (full) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Per-family joint accuracy (MultiGov):

| family | deepseek (n=200) | gpt-5.5 (n=200) | deepseek (n=102) | opus (n=102) |
|---|---:|---:|---:|---:|
| answerable_direct | 0.956 | 1.000 | 0.909 | 1.000 |
| denominator_caliber | 0.909 | 1.000 | 1.000 | 1.000 |
| finest_grain_trap | **0.500** | **1.000** | 0.515 | **0.970** |
| policy_refusal | 1.000 | 1.000 | 1.000 | 1.000 |
| temporal_anchor | 0.750 | 1.000 | 0.600 | 1.000 |

## Contract conformance and over-refusal composition (vs the deepseek reference rows)

| Layer / model | Answer preds | Finest-grain violations | Metric-not-in-catalog | Dim-not-allowed | False refusals / total errors |
|---|---:|---:|---:|---:|---:|
| GovTwin deepseek | 139 | **31 (22.3%)** | 0 | 0 | 11 / 42 |
| GovTwin claude-opus-4-6 | 159† | **7 (4.4%; 4.7% of 150 parseable)** | 9† | 0 | 0 / 16 |
| GovTwin gpt-5.5 | 150 | **0** | 1† | 0 | 0 / 1 |
| MultiGov-200 deepseek | 93 | 0 | 1† | 0 | **35 / 37** (31 on finest_grain_trap) |
| MultiGov-200 gpt-5.5 | 128 | 0 | 0 | 0 | **0 / 0** |
| MultiGov-102 deepseek | 46 | 0 | 1† | 0 | **18 / 20** (15 on finest_grain_trap) |
| MultiGov-102 claude-opus-4-6 | 63 | 0 | 0 | 0 | **1 / 1** (1 on finest_grain_trap) |

† `metric_not_in_catalog` counts include the pre-registered `__parse_error__` sentinels (opus GovTwin: the 9 glitched refusals; gpt GovTwin: 1 corrupted emission; deepseek MultiGov: 1 malformed output), which are scored as answer-predictions per protocol.

The single opus MultiGov error is mechanism-relevant: `mg_case_0125` ("compare time anchor 0042 by summary scope and fine scope...", gold = answer at fine scope) was **falsely refused with a fabricated policy ground** ("time anchors are metadata constructs used to bind valid-time semantics, not queryable metrics" — no such rule exists in the contract): the deepseek grain-trap over-refusal signature, at 1/102 instead of 15-18/102.

## Pre-registered mechanism-reproduction judgment (protocol_ext.md section 1 rule applied verbatim)

| Mechanism | claude-opus-4-6 | gpt-5.5 |
|---|---|---|
| **M1: finest-grain violations persist despite verbatim in-prompt rule** | **Reproduced in kind, sharply attenuated**: fgv = 7 > 0 on GovTwin (4.4% vs deepseek 22.3%, a ~5x lower rate), joint < 1.000. Pathway differs: all 7 arise from dumping `allowed_dimensions` into flat queries (deepseek failure class #5), not from the answer/refuse/keep-both inconsistency; opus resolves deepseek's inconsistent hierarchy cases correctly. | **Not reproduced**: fgv = 0 on both layers; its single error is JSON emission corruption, not a policy-execution error. |
| **M2: grain-trap over-refusal collapses refusal precision** | **Reproduced in kind, sharply attenuated** (criterion fires: MultiGov Ref.P 0.974 < 1.000; false refusals = 1/1 of errors, concentrated on finest_grain_trap; fabricated policy ground). Magnitude: 1/102 vs deepseek 18/20 errors on the identical 102 cases. GovTwin: zero false refusals (criterion does not fire there). | **Not reproduced**: Ref.P = Ref.R = 1.000 on both layers; zero false refusals across all 359 scored cases; grain-trap family joint 64/64. |
| **Cross-model claim (both models show nonzero conformance gap with joint < 1.000)** | Gap present on both layers (grain violations; refusal-template glitches; joint 0.899 / 0.990). | Gap present on GovTwin only (joint 0.994 < 1.000, one malformed emission); MultiGov-200 is exactly 1.000 with zero violations and perfect refusal P/R. |

**Verdict (mixed outcome, reported per model as pre-registered):** the deepseek-scale mechanisms — 22.3% grain violations and mass grain-trap over-refusal (75/80 of errors on the full 510; 35/37 on this 200-subset) — **did not replicate at frontier scale and are substantially model-specific**. What does replicate across all three models is a weaker, still-nonzero claim: **no model achieved end-to-end contract conformance on every layer** (deepseek 42+37 errors; opus 16+1 errors incl. 7 grain violations and a deterministic malformed-refusal template; gpt-5.5 exactly 1 malformed emission in 359 cases), whereas the compiler is 1.000 with zero violations by construction. On the MultiGov subsample gpt-5.5 fully closed the gap (1.000, CI lower bound 0.981).

**Required paper edit:** the H1 mechanism paragraph must be narrowed from "instructed execution fails to conform" to a model-conditioned claim, e.g.:

> On the model the public benchmark was built with (deepseek-3.2), instructed execution leaves large mechanism-level gaps (22.3% finest-grain violations on GovTwin; 75/80 MultiGov errors are grain-trap over-refusals). A pre-registered extension on two heterogeneous frontier models (claude-opus-4-6, gpt-5.5; identical verbatim prompts, temperature 0; GovTwin full 159 + MultiGov stratified 200) shows these magnitudes are model-specific: claude-opus-4-6 retains the same failure classes at sharply lower rates (7 grain violations, 4.4%; one grain-trap over-refusal with a fabricated policy ground; plus a deterministic malformed-JSON refusal template on all 9 GovTwin refusals), while gpt-5.5 eliminates both mechanisms (0 violations, refusal P/R = 1.000) and its sole failure in 359 cases is a corrupted JSON emission. No model matched the compiler's by-construction 1.000/zero-violation contract conformance on every layer, but the residual gap for the strongest model is format fragility at the 0.3% level, not policy misexecution.

An honest consequence for the paper's positioning: the compiled-witness argument should lean on (a) by-construction guarantees vs any nonzero residual, (b) model-independence and auditability, and (c) the operational fragility of prompt-carried contracts (see below), rather than on frontier-model incompetence at policy execution.

## Bonus operational finding (transport, not model): prompt-carried contracts silently fail in serving stacks

The quarantined batch is itself evidence relevant to the paper's systems argument: a commercial serving path accepted a ~69k-token system prompt, billed all prompt tokens, returned HTTP 200 — and demonstrably never showed the contract to the model (0/69 schema-conformant; 61/69 "contract not provided"; same-key control model executed the same bytes correctly; same model on a sibling deployment executed them correctly). An instructed-execution governance architecture inherits this silent failure mode end-to-end (the caller cannot distinguish "model saw and violated the contract" from "model never saw it"), whereas a compiled witness executes independently of any model-serving path. All diagnostics are stored under `raw_responses/` and in Amendment 1.

## Cost / runtime record

- Scored calls: 620 (0 unresolved API errors in scored data; 16 quota-403 records on the opus MultiGov file; 82 opus MultiGov cases never attempted).
- Tokens (scored runs): opus GovTwin 1.36M+10.6k; gpt GovTwin 0.97M+7.9k; opus MultiGov 8.47M+9.6k; gpt MultiGov 13.80M+27.5k prompt+completion. Confounded quarantined batch additionally consumed ~4.7M prompt tokens (reported as spent).
- Mean latency: 5.2-9.4 s/call by run. Wall-clock: GovTwin ~35 min (both models, concurrency 4 each); gpt MultiGov ~85 min; opus MultiGov ~50 min to quota stop.

## Honest limitations

1. **Opus MultiGov is a partial run (102/200)** stopped by third-party key quota, not by us and not by outcome; the completed 102 skew toward lower case_ids (completion order) but contain all five families, and every comparison uses a paired deepseek reference on the identical 102. The 98 missing cases can be completed by resuming `run_h1_ext.py run --model claude-opus-4-6 --layer multigov` once the key is recharged (runner is resumable; prompts pinned).
2. **Relay-served models.** Both new models are accessed through a commercial relay; model identity is as labeled by the relay and cannot be independently attested (the parent deepseek run has the analogous caveat via the enterprise gateway). The default-vs-group-B deployment difference we exposed shows serving stacks materially affect results; we verified the scored runs' contract visibility directly (schema conformance + catalog-derived reasoning in outputs).
3. **Single run at temperature 0**, n=1 per case; provider-side nondeterminism acknowledged. The gpt-5.5 MultiGov 1.000 has CI [0.981, 1.000] on n=200 — it bounds, not proves, exact conformance; the full 510 was not run for cost control (pre-registered).
4. **Pre-registered parse rule cuts against opus**: its 9 GovTwin refusals are semantically correct but malformed; scoring them as refusals would move opus GovTwin joint from 0.899 to 0.956 and Ref.P/Ref.R to 1.000. We report the protocol-literal numbers and disclose the counterfactual; either way the conformance gap (7 grain violations) remains.
5. GovTwin gpt-5.5 ran on the deployment later shown defective for ~69k-token prompts; its ~10.4k-token run is verified unconfounded (0 blindness markers, catalog-grounded reasons throughout), but channel heterogeneity within gpt-5.5 is a deviation, disclosed in Amendment 1.
6. The MultiGov subsample (200/510) was drawn deterministically and gold-free (seed and allocation pre-registered before any call); family-level results on the 310 unsampled cases are extrapolation.

## File inventory (all under `new_experiments/h1_multimodel_extension/`)

- `protocol_ext.md` — pre-registered protocol + Amendment 1
- `run_h1_ext.py` — extension runner (imports parent scorer/parser/prompt builder; transport + subsample only)
- `multigov_subsample_case_ids.json` — locked subsample (seed 20260711, sha256 010e0b16...)
- `raw_responses/{claude-opus-4-6,gpt-5.5}_{govtwin,multigov}_raw.jsonl` — 620 scored raw responses (+16 quota-403 records in the opus MultiGov file)
- `raw_responses/CONFOUNDED_relaydefault_gpt-5.5_multigov_raw.jsonl` — 69 quarantined transport-confounded records (excluded from scoring)
- `predictions_{model}_{layer}.jsonl` — parsed, normalized, per-case scored predictions
- `scores_ext.json` — all metrics incl. per-family, conformance, over-refusal composition, deepseek same-case references, protocol-literal variant
- `SUMMARY.md` — this file

---
# 终版补记（2026-07-12 13:54，全五层完成后由主线终评）

opus MultiGov 已补齐至 n=200 完整（含此前 102 中期披露）；两模型 × 全五层矩阵（scores_ext.json ts 2026-07-12T05:54Z 后由 `run_h1_ext.py score` 重新生成）：

| 层 | opus joint(errs) | gpt-5.5 joint(errs) | deepseek 参照 |
|---|---|---|---|
| Iowa 32 | 0.938 (2) | **1.000 (0)** | 0.969 (1) |
| Chinook 40 | 0.925 (3) | 0.925 (3) | 0.925 (3) |
| GovTwin 159 | 0.899 (16) | **0.994 (1)** | 0.736 (42) |
| MultiGov 200 | 0.990 (2) | **1.000 (0)** | 0.815 (37) |
| ICT 157 | 0.764 (37) | 0.860 (22)* | 0.822 (28) |
| **总计 588** | **528/588（60 错）** | **562/588（26 错）** | — |

\* gpt-5.5 ICT 协议字面全集 n=157；完成子集 n=153 为 0.882（4 例传输缺失已披露，两口径均报告）。

**跨模型终版判定（全五层实测，不再是部分外推）**：
1. "no model attains contract conformance on every layer" **成立**——gpt-5.5 虽在 Iowa/MultiGov 精确闭合、GovTwin 近闭合，但 Chinook 3 错、ICT 22 错；编译器按构造全层 exact。
2. M1 粒度违规：模型特异确认（gpt-5.5 全五层 fgv=0；opus 共 8；deepseek 32）。
3. M2 过度拒答：**在最强模型上于真实企业文本层重现**——gpt-5.5 ICT refusal precision 0.348（与 opus 0.348 相同），即最强模型的残差集中在 ICT 的过度拒答上；语言最真实的层恰是 prompting 最不稳的层。
