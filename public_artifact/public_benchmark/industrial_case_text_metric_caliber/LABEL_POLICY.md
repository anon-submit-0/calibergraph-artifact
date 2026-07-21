# IndustrialCaseText Label Policy

This document defines the public labeling policy used for IndustrialCaseText-MetricCaliber. It is released with the benchmark so reviewers can inspect why a query is answerable, refused, or mapped to a finest-grain dimension.

## Released Inputs

- `source_candidates_public_desensitized.jsonl`: pre-build desensitized source candidates without labels; labels are separated into `source_candidate_labels_public_desensitized.jsonl`.
- `blind_cases.jsonl`: prediction input without `expected_*` labels.
- `cases.jsonl`: labeled inspection/rebuild convenience file, not a legal prediction input.
- `gold_labels.jsonl`: scorer-only labels.
- `withheld_label_conflicts.jsonl`: duplicate public queries removed from scoring because their labels conflict.

## Action Labels

`answer` is used when the query can be mapped to a governed metric in `metric_catalog.jsonl` and does not trigger a public policy refusal.

`refuse` is used when at least one of the following holds:

- the request asks for raw SQL, raw rows, raw catalog dumps, DDL, or private identifiers;
- the request is off-domain;
- no governed metric is recognized from the released metric catalog and aliases;
- the public policy catalog marks the query form as ambiguous and unsafe to answer without clarification.

## Metric Labels

The expected metric is the governed metric whose released public aliases match the intended business measure. If multiple governed metrics appear, the first governed metric mentioned in the request is treated as the primary metric unless the query explicitly asks for a supported comparison policy. Unsupported comparisons are refused.

## Dimension Labels

Dimensions are selected from `dimension_catalog.jsonl`. When a hierarchy path contains both parent and child dimensions, the finest mentioned child is the expected governed dimension. Parent dimensions are not duplicated in gold labels when a child dimension already determines the reporting grain.

Example policy pattern: a query mentioning segment level 1, level 2, and level 3 is labeled with only the finest released segment dimension.

## Time And Caliber Labels

Time labels use normalized public anchors such as `last_month`, `this_year`, or `unspecified`. Caliber labels use released anonymized caliber ids. Raw private event names and routing metadata are not released.

## Duplicate Conflict Policy

If two desensitized public queries normalize to the same text but have incompatible action, metric, dimension, time, or caliber labels, all cases in that conflicting group are withheld from the scored split. The withheld group remains disclosed in `withheld_label_conflicts.jsonl`.

## What Is Not Claimed

This release does not claim row-level enterprise disclosure or independent multi-annotator agreement. Instead, this release provides a public desensitized source-candidate file, executable conflict withholding, blind/gold separation, and a deterministic label policy that reviewers can audit and rerun.
