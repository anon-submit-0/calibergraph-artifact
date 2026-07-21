# CaliberGraph Anonymous Submission Package

This is the anonymous AAAI submission package for:

`CaliberGraph: Coverage-Caliber Witness Compilation for Multi-Business-Domain Governed Metrics`

## Submit

Use the three PDFs under `submission_pdfs/`: `main.pdf`,
`supplementary.pdf`, and `ReproducibilityChecklist.pdf`. Build provenance is in
`submission_pdfs/PDF_BUILD_RECORD.md`.

## Scientific Organization

The paper follows problem, gap, insight, method, and evidence. Experiments are
organized by research question: overall runnable comparison, post-linking
mechanism, module ablation, robustness/external validity, and cost/auditability.
Public-native, public enterprise-derived, controlled, private aggregate, and
adjacent evidence are explicitly distinguished.

## Reproduce

```bash
cd public_artifact
bash rebuild_and_verify_public_artifact.sh
```

This rebuilds deterministic evidence and recomputes stored online-run scores.
See `PUBLIC_REPRODUCIBLE.md` for the exact public/private and rerun/replay
boundaries.

## Package Boundary

Upload this clean directory or its clean zip, not the author project root. The
clean package uses generic filenames and contains no historical release or
author-workline labels.


## Addendum: Final-Revision Evidence (extended_evidence/)

Three evidence blocks added in the final revision, each fully reproducible:

1. `extended_evidence/external_ecosystem_contract/` — pre-registered external-ecosystem
   experiment on a third-party MetricFlow upstream manifest (dbt Labs).
   Reproduce: `python3 convert_mf_manifest.py` (rebuild the converted contract layer),
   `python3 generate_cases.py` (regenerate the 122 seeded template cases and gold),
   `python3 run_compiler_arm.py` (compiler arm; joint 1.000, 122/122).
   LLM arms (`run_llm_arms.py`) require API access via environment variables
   (see file header); all raw responses, predictions, canaries, the full released
   prompt, and paired statistics are already included under `llm_arms/`.
2. `extended_evidence/binding_annotation/` — practitioner reconstruction of the binding
   layer (60 stratified bindings, position-balanced). Recompute agreement:
   `python3 recompute_binding_agreement_v3.py annotatorA_return_anonymized.csv
   annotatorB_return_anonymized.csv annotatorC_return_anonymized.csv`.
3. `extended_evidence/private_robustness/` — pre-registered multi-pass robustness rerun
   of the private-contract frontier inversion (aggregates and correctness flags only).

The `paper_source/` and `submission_pdfs/` here correspond to the final revision.

## Addendum v28: Alternative-Route Closure and External Policy Anchor (extended_evidence/)

1. `alias_control/` — deterministic RapidFuzz alias-matching control (zero LLM): metric identity resolvable, joint 0.000 on MultiGov; identity-style vs governance-style refusal asymmetry.
2. `entropy_abstention/` — uncertainty-abstention control (k=5 consistency entropy, AAAI-25 recipe, 1,795 calls): all 11 caliber-family errors at entropy exactly 0.000; caliber errors are confident errors.
3. `securesql_anchor/` — pre-registered SecureSQL (EMNLP 2024, CC BY 4.0) policy-compilability boundary: 19.9% of free-text conditions non-mechanizable; compiled agreement 0.609 (n=932), frontier prompting 0.702 (n=300), humans 94%.
All protocols were frozen before any call; raw responses and scorers are included.

## Revision note (figures revision, 2026-07-18)

`paper_source/` and `submission_pdfs/` now carry the current submission: Figure 1
(contract-gap / compile-once / certify / decision panels with the single online-LLM
badge) and Figure 2 (candidate-fate, validator-feedback, and abstention floors), with
figure data provenance in the supplementary. New released evidence:
`public_artifact/extended_controls/candidate_fate_same_denominator/` — the
same-denominator candidate-fate rescore behind Figure 2(a)
(`per_case_candidate_fate.jsonl`, `candidate_fate_results.json`,
`recompute_candidate_fate.py`, `PROTOCOL.md`; deterministic, no new LLM calls).
