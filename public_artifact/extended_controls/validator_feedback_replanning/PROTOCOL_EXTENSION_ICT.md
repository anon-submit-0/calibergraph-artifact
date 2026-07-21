# IndustrialCaseText Full-Case Extension

This extension was added after the original 391-case preregistered run to test
transfer to all 157 released real-desensitized IndustrialCaseText cases. It is
therefore reported as a post-primary external-validity extension, not folded
into the original branch decision.

The extension freezes the same model (`deepseek-3.2`), temperature 0,
retrieval-snippet round-0 prompt, closed-list typed validator, maximum three
repair rounds, parser, missing-output policy, and scorer. It uses the full
released ICT split with no sampling. No gold label enters retrieval, prompting,
validation, or feedback; gold is joined only after final predictions are stored.

Required reporting is layer-specific round-0/final accuracy, paired transitions,
calls and tokens, and the complete validator-invisible error census. A combined
548-case statistic may be shown descriptively, but must be labeled as combining
the preregistered primary scope with this later extension.

Observed result: 0.771 round-0 to 0.879 final over 157 cases, with 17
wrong-to-right and zero right-to-wrong transitions. All validator-visible
violations are repaired. The 19 residual errors comprise 12 wrong dimension
sets and seven wrong in-catalog metrics that pass the gold-free validator.
