# Validator-Feedback Replanning Results

The release separates the original preregistered analysis from later full-case
extensions. `protocol.md` and `FROZEN_PRIMARY_391_SUMMARY.md` preserve the
primary 391-case decision; `PROTOCOL_EXTENSION_ICT.md` records the later
IndustrialCaseText transfer test. The exhaustive MultiGov extension is in the
sibling `validator_feedback_multigov_full/` directory.

## Primary Preregistered Scope

Iowa 32, GovTwin 159, and seeded MultiGov 200 total 391 cases. Replanning raises
joint accuracy from 0.826 to 0.969: 56 cases change wrong-to-right and none
right-to-wrong (two-sided exact sign test `p=2.78e-17`). The preregistered
outcome is Branch B, significant improvement without closing every layer:
Iowa 1.000, GovTwin 0.981, and MultiGov-200 0.955.

## Later Full-Case Extensions

IndustrialCaseText uses all 157 released cases and changes from 0.771 to 0.879.
The descriptive four-layer total is 548 cases, 0.810 to 0.943, with 73
wrong-to-right and zero right-to-wrong transitions (`p=2.12e-22`). This
combined statistic is not labeled preregistered in `scores.json`.

The unchanged protocol was also extended from the MultiGov-200 sample to all
510 cases. It changes from 0.894 to 0.971 using 552 calls (1.082 per case), with
39 wrong-to-right and zero right-to-wrong transitions. Fifteen final errors
remain validator-invisible. CaliberGraph is 1.000; the paired difference is
0.029, 170-group bootstrap CI [0.016, 0.045], exact McNemar `p=6.10e-5`.

## Mechanism Boundary

Across every layer, the feedback loop repairs all violations that its typed
validator can detect. Residual errors instead choose an incorrect but
in-catalog metric or an allowed, hierarchy-consistent but unrequested dimension
set. The control is deliberately strong because it reuses CaliberGraph's typed
checks as its feedback oracle. It is consequently a mechanism upper bound, not
an independent semantic engine.

## Reproduction

Offline scoring and audits use the stored raw responses and require no model
key:

```bash
python3 extended_controls/validator_feedback_replanning/run_loop.py audit
python3 extended_controls/validator_feedback_replanning/run_loop.py compat
python3 extended_controls/validator_feedback_replanning/run_loop.py score
python3 extended_controls/validator_feedback_multigov_full/run_multigov_full.py audit
python3 extended_controls/validator_feedback_multigov_full/run_multigov_full.py score
```

An online rerun requires an OpenAI-compatible endpoint in `LLM_API_BASE` and
its key in `LLM_API_KEY`. Stored response histories, prompt hashes, usage,
verdicts, and feedback text make the reported run independently auditable even
when the proprietary model endpoint is unavailable.
