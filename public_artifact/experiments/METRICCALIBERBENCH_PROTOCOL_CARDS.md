# MetricCaliberBench Protocol Cards

These cards state what each public layer is for. They are meant to prevent the benchmark contribution from reading as a pile of datasets.

## IowaLiquor-MetricCaliber

- Evidence type: Real public row-level business data.
- What it tests: Tests whether executable SQL over external public rows is sufficient for governed metric planning.
- Boundary: External State of Iowa rows; authored semantic layer/labels over that schema.
- How another method can use it: Use the SQLite file, blind cases, catalogs, and scorer to compare NL2Metric-to-SQL planners.

## Chinook-MetricCaliber

- Evidence type: Compact public stress benchmark.
- What it tests: Tests hierarchy/refusal/unsupported metric behavior on a familiar public database.
- Boundary: Public sample DB; authored governance layer.
- How another method can use it: Use for fast regression tests and ablations.

## BIRD-MetricCaliber

- Evidence type: Text-to-SQL diagnostic.
- What it tests: Tests whether public SQL outputs recover governed aggregate expressions, measures, and group dimensions.
- Boundary: External NL/SQL/schema records; strict parser may under-credit equivalent SQL.
- How another method can use it: Use as diagnostic connection to Text-to-SQL, not as primary governed-BI benchmark.

## GovTwin-MetricCaliber

- Evidence type: Public structural stress test.
- What it tests: Tests denominator, hierarchy, policy, perturbation, and paraphrase robustness with no private terms.
- Boundary: Synthetic public names preserving private governance structure.
- How another method can use it: Use for controlled witness-compiler ablations.

## MultiGov-MetricCaliber

- Evidence type: Production-derived anonymized governance benchmark.
- What it tests: Tests recurring witness traps across 12 production DataGov domain versions.
- Boundary: Anonymized governance artifacts; no raw enterprise rows or private mappings.
- How another method can use it: Use to test cross-domain governed metric planning and policy refusal.

## IndustrialCaseText-MetricCaliber

- Evidence type: Real desensitized enterprise query surface.
- What it tests: Tests actual NL2Metric case text and anonymized labels after conflict removal.
- Boundary: Real desensitized case text; no raw rows/private ids.
- How another method can use it: Use to compare methods on realistic business utterances with blind/gold split.

## DataHub audit

- Evidence type: Aggregate production recurrence evidence.
- What it tests: Shows the same witness traps recur across seven business areas.
- Boundary: Aggregate only, not a scored public benchmark.
- How another method can use it: Use as motivation and recurrence evidence, not as public leaderboard data.
