# Public Reproducibility Boundary

Date: 2026-07-12

This document separates deterministic key-free reconstruction, offline replay
of stored online runs, and intentionally withheld private evidence.

## One-Command Public Rebuild

From the clean package:

```bash
cd public_artifact
bash rebuild_and_verify_public_artifact.sh
```

The command rebuilds all public benchmark splits and deterministic predictions,
reruns the contract compiler, mutation and isolation suites, statistical audits,
and then recomputes every extended-control score from released records. It also
regenerates the public manifest/checksums and runs the privacy and consistency
checks. It requires neither DataHub nor enterprise credentials.

## Deterministic Evidence

The key-free rebuild covers IowaLiquor, Chinook, GovTwin, MultiGov, and
IndustrialCaseText; blind/gold separation; compiler traces; seven family
mutations; five current-metric isolation mutations; policy sensitivity; paired
statistics; external-scope audits; and 17,160 compiler-latency replays.

The IndustrialCaseText builder starts from the released label-free,
desensitized source candidates. Rebuild labels and scorer labels are separate
files and are not legal prediction inputs. MultiGov exposes anonymous catalogs,
typed edges, metric-specific physical bindings, cases, and scorer labels, but
not raw enterprise rows or private-to-public mappings.

## Stored Online and Engine Evidence

`extended_controls/` releases raw responses or sanitized engine logs plus the
scorers needed to recompute:

- 898 complete-contract DeepSeek calls;
- same-split Opus and GPT-5.5 controls with transport canaries;
- the preregistered 391-case validator-feedback experiment, its later
  enterprise-text extension, and exhaustive MultiGov-510 extension;
- 64 real MetricFlow queries and nine capability probes;
- three anonymized practitioner annotation sheets and disagreement sensitivity;
- headline accuracy stratified by active versus inactive physical-coverage checks;
- 159 correctness-only private-domain pairs with no text or identifiers.

Replaying stored responses is deterministic. Reissuing proprietary-model calls
is optional because providers may update deployments. The online scripts use
generic environment variables (`LLM_API_BASE`, `LLM_API_KEY`, and documented
model-specific variants) and contain no credentials or internal endpoints.

## Withheld Boundary

The package deliberately withholds raw enterprise rows, raw private queries,
private table/column names, source identifiers, private mappings, credentials,
and author-side DataHub traces. Private evidence is released only as anonymous
correctness pairs sufficient to recompute the reported aggregate tests.

## Licenses

See `public_artifact/LICENSES.md`. Author-created benchmark data and
documentation use CC BY 4.0; author-created code uses Apache-2.0; third-party
materials retain their original licenses.
