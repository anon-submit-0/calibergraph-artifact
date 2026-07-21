# Strongest-Model Controls (gpt-5.5, claude-opus-4-6) on the Private 159-Case Set — Results Summary

- Protocol: `protocol_ext_models.md`, frozen 2026-07-12T14:13+0800 BEFORE any LLM call of this study; Amendment 1 (gpt-5.5 canary rev-3) registered 14:17+0800, still before any benchmark call.
- Run window: 2026-07-12 14:18–14:26 +0800 (06:18–06:26 UTC). Arm C: 159/159 calls per model, 0 transport errors. Arm D: 159/159 case loops per model, 0 transport errors (gpt-5.5: 177 calls; claude-opus-4-6: 197 calls). All raw responses persisted under `raw_responses/` before scoring.
- Canary gate: claude-opus-4-6 passed the quotation canary 2/2. gpt-5.5 refused quotation under every framing while citing the contract's own policy label "P2" (proof of contract delivery) — the pre-documented h1 failure mode — and passed the pre-registered rev-3 behavioral alias-resolution probe 2/2 (`sale_qty` resolved from its Chinese alias, a binding that exists only inside the 23,290-char system prompt). All canary records isolated in `raw_responses/canary_*.jsonl`, never scored.
- Pairing: per-case against the retained CaliberGraph arm (147/159 = 0.9245; Arm A drift assertion passed at scoring time).

## Headline — pre-registered branch decision: **(a) OVERTAKEN / gap eroded**

Joint = exact metric AND exact dimension set, identical 159 private cases; McNemar exact two-sided vs. CaliberGraph; Δ = acc_A − acc_X with paired-bootstrap 95% CI (B=10,000, seed=20260711):

| Arm | Joint | Wilson 95% | Refusal P / R | LLM calls | vs. CaliberGraph |
|---|---:|---:|---:|---:|---|
| A. CaliberGraph (compiler) | 0.925 (147/159) | [0.873, 0.956] | 1.000 / 0.778 | **0** | — |
| **C-gpt-5.5 instructed-execution** | **0.981 (156/159)** | [0.946, 0.994] | 0.875 / 0.778 | 159 | **p = 0.0039 (Holm 0.0117); Δ −0.057; CI [−0.094, −0.025] — gpt-5.5 significantly BETTER** |
| D-gpt-5.5 round 0 (Schema-RAG) | 0.836 (133/159) | [0.771, 0.886] | 0.538 / 0.778 | 159 | p = 0.0043; Δ +0.088; CI [+0.031, +0.145] |
| **D-gpt-5.5 replan final** | **0.925 (147/159)** | [0.873, 0.956] | 1.000 / 0.778 | 177 (1.11/case) | p = 1.0; Δ 0.000; CI [−0.038, +0.038] — exact tie |
| C-claude-opus-4-6 instructed-execution | 0.723 (115/159) | [0.649, 0.787] | 0.412 / 0.778 | 159 | p = 9.4e-7 (Holm 3.8e-6); Δ +0.201; CI [+0.126, +0.277] — compiler better |
| D-claude-opus-4-6 round 0 | 0.786 (125/159) | [0.716, 0.843] | 0.583 / 0.778 | 159 | p = 1.1e-4; Δ +0.138; CI [+0.076, +0.208] |
| **D-claude-opus-4-6 replan final** | **0.937 (149/159)** | [0.888, 0.965] | 1.000 / 0.778 | 197 (1.24/case) | p = 0.79; Δ −0.013; CI [−0.057, +0.031] — point-above, not significant |
| (ref) deepseek-3.2 C / D₀ / D-final | 0.780 / 0.780 / 0.899 | — | — | 159/159/183 | from `../private_strongest_controls/` |

Pre-registered primary question — does any primary arm reach joint ≥ 0.9245? **Yes, three do**: C-gpt-5.5 (0.981, significantly above), D-gpt-5.5-final (0.925, exact tie), D-claude-opus-4-6-final (0.937, above but not statistically separable). Branch (a) applies. **The last alternative explanation is CONFIRMED, not excluded: the strongest available model, given the complete governance contract verbatim, executes it and overtakes the compiler on this set.**

## Anatomy of the decisive result

### C-gpt-5.5: strict paired dominance, at exactly the released-policy ceiling

- Contingency vs. compiler: both_correct 147, **A_only 0, X_only 9**, both_wrong 3 — gpt-5.5 is correct on every case the compiler gets right AND on 9 of the compiler's 12 error cases. Its 3 errors are a strict subset of the compiler's own errors: case_143 and case_144 (gold refusals with no released refusal trigger — unreachable for any agent that follows the released policy, including the compiler) and case_138 (an over-refusal the compiler also gets wrong).
- 156/159 = 0.981 equals the pre-registered gold-free released-policy ceiling computed in `../private_strongest_controls/validator_audit.json`. Interpretation: at n=159, gpt-5.5 executed the released governance policy essentially perfectly from a verbatim contract-in-context — including caliber/metric disambiguations (sku vs. category complaint rate, problem_cnt vs. rma_order_count) that defeat deepseek-3.2 and claude-opus-4-6. Zero parse failures; 159/159 clean JSON.
- Cost: 159 calls, 1.25 M prompt + 25 K completion tokens (~7.9 K prompt tokens/case, every query, forever), frontier-model access, non-bit-reproducible gateway decoding; compiler: 0 calls, deterministic.

### The two loop arms: validator repair converges every model family to ≥ compiler-level

- gpt-5.5: 0.836 → 0.925 (14 fixed, 0 regressions, sign p = 1.2e-4); all validator-visible violations cleared; refusal precision repaired 0.538 → 1.000; residual 12 errors all validator-invisible (11 wrong-metric, 1 metric+dims).
- claude-opus-4-6: 0.786 → 0.937 (24 fixed, 0 regressions, sign p = 1.2e-7); 4 cases still validator-failing at budget exhaustion (2 hierarchy_conflict, 2 dimension_policy_violation); residual 10 errors (8 validator-invisible).
- Cross-model residual census (D-final wrong-metric confusions, all three models incl. deepseek): concentrated in the same near-synonym caliber pairs — problem_cnt↔rma_order_count, sku_complaint_rate↔category_complaint_rate, return_rate↔return_qty — plus the case_143/144 policy-unreachable refusals. The validator-invisible residue is stable across model families; what changes with model strength is how close the floor is to the ceiling.

### C-claude-opus-4-6: instructed-execution is model-conditioned

Opus-4-6 with the identical verbatim contract collapses to 0.723 (worse than deepseek's 0.780): 10 spurious refusals (precision 0.412), spurious grouping dimensions, 1 fenced-output parse error. "Contract-as-context" is NOT a uniformly strong baseline — it ranges 0.72–0.98 across three model families on identical prompts. This is honest context for the headline, not a counter to it.

## What the paper must now say (pre-registered branch (a) obligations)

1. **Retire the competitive superiority claim entirely.** The paper may no longer state or imply that CaliberGraph outperforms LLM planning on the private set. Under the strongest pre-registered controls, gpt-5.5 instructed-execution is significantly better (0.981 vs 0.925, p = 0.0039, Holm-adjusted 0.0117), and both replan-loop arms reach or exceed the compiler's point estimate. The competitive table ships with these numbers in it.
2. **Migrate the primary claim to by-construction properties** — this is now the paper's only defensible thesis, and the new data actively supports it:
   - deterministic policy conformance and structured refusal with precision 1.0 by construction (both frontier loops needed the compiled policy as a repair oracle to reach refusal precision 1.0; gpt-5.5 alone reached 0.875);
   - zero plan-time LLM calls / zero marginal cost / offline reproducibility vs. 7.9 K frontier prompt-tokens per query for the overtaking arm, on a non-bit-reproducible gateway;
   - auditability: every compiler decision traces to catalog edges; the LLM arm's 0.981 is an empirical observation at n=159 with no conformance guarantee (its refusal precision was 0.875, i.e. it DID emit one policy-violating answer where the compiler cannot);
   - the ceiling analysis: 0.981 = the released-policy ceiling — the strongest model converges to executing exactly the policy the compiler compiles, which is the by-construction thesis stated behaviorally.
3. **Reframe the loop finding across three model families**: validator-feedback repair (the compiled policy as oracle) lifts every family to compiler-level or above (0.899 / 0.925 / 0.937), with zero regressions in all three loops — governance-as-checker is portable machinery, and the residue it cannot fix (metric-caliber selection) is exactly what the governance graph encodes. This is now a portability claim, not a superiority claim.
4. Suggested main.tex wording (both directions disclosed):
   > Under pre-registered strongest-model controls on the same 159 paired cases, instructed-execution with the complete compiled contract in context is model-conditioned: 0.723 (claude-opus-4-6) and 0.780 (deepseek-3.2) but 0.981 (gpt-5.5), the latter significantly above CaliberGraph's 0.925 (McNemar p = 0.0039) and exactly at the released-policy ceiling — its only residual errors are cases where the gold labels contradict the released policy, cases the compiler also fails. A validator-feedback replanning loop whose oracle is the compiled policy converges all three families to 0.899–0.937 (none statistically separable from the compiler). We therefore do not claim accuracy superiority over strongest-model planning; CaliberGraph's contribution is that the same conformance is obtained by construction — deterministically, at zero plan-time LLM calls and with guaranteed structured refusal — rather than as an empirical property of a particular frontier model reading the contract.
5. If a superiority-flavored statement is wanted anywhere, the only honest version is cost/guarantee superiority, never accuracy superiority.

## Redline compliance

- Data read-only: mirror untouched (`gov_semantic_test_case.tsv.gz` MD5 93b43c4230ecb15d47d99c3a2c02dc76 re-verified after the run).
- Writes confined to `new_experiments/private_strongest_controls_multimodel/` only.
- `per_case_pairs_models.jsonl` and `mcnemar_models.json`: verified zero CJK characters (zero private query text), identifiers/booleans/hashes/statistics only; no key material in any shipped file (checked against every key in the env file).
- Prompts not persisted (SHA-256 + char counts per call; Arm C system prompt identical bytes to the parent study, sha256 3d52922445af007070a49a4a83b0fd9f66dbd250fb531092fb9d111ea606f7cd). Rev-3 canary probe stored as SHA-256 + target metric id only.
- `raw_responses/` stays in the internal-author-evidence tier; apply the public desensitization mapping before any release (same treatment as the parent studies).

## Credibility self-assessment

- **High confidence**: pairing integrity (Arm A sum asserted 147 at scoring); code identity (prompt construction, validator, parsing, scoring all imported from the parent runner module — byte-identical logic, no reimplementation); zero transport errors and zero unresumed cases in all four arms; statistics hand-checked (C-gpt: b=0,c=9 → p = 2·(1/2⁹) = 0.00391; D-opus: b=6,c=8 → p = 0.7905); canary gates passed before every benchmark call; the decisive unfavorable number is reported as the headline.
- **Known limitations**: (1) single fresh pass per arm at temperature=0 on a gateway that is not bit-reproducible; the parent studies' ~0.02 absolute drift caveat applies — but the headline discordance (9−0) is far outside that noise; (2) n=159 with only 12 compiler errors means the overtaking margin rests on 9 discordant cases — the exact-binomial p is valid but the effect estimate is coarse; (3) third-party gateway model labels ("gpt-5.5", "claude-opus-4-6") cannot be independently attested beyond the channel's claim — same standing caveat as all relay runs; (4) private cases have never been published, so training contamination on case text is implausible, but the released policy phrasing is quoted in the prompt by design (that is the treatment, not a leak); (5) the branch verdict is model-conditioned by construction — a stronger future model can only strengthen branch (a), never restore the competitive claim.
- Overall: the fifth-round meta-review question is answered decisively and unfavorably for the competitive framing — the strongest model DOES overtake the compiler when handed the compiled contract, and the pre-registered protocol converts that into a clean, publishable migration: the paper's claim moves fully to by-construction guarantees, with the strongest-model result reported in the open as the reason why.
