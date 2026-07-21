# Clean Submission Package Manifest

Date: 2026-07-12

## Submission Files

- `submission_pdfs/main.pdf`
- `submission_pdfs/supplementary.pdf`
- `submission_pdfs/ReproducibilityChecklist.pdf`
- `submission_pdfs/PDF_BUILD_RECORD.md`
- `openreview_metadata.md`

## Reviewer-Facing Sources

The package contains the anonymous AAAI source, bibliography/style files, this
manifest, and the public reproducibility guide. Build products and local paths
are excluded.

## Public Artifact

The key-free artifact includes blind/gold benchmark splits, the contract
compiler, typed certificates, mutation/isolation suites, paired statistical
audits, real MetricFlow logs, complete-contract model responses, validator-
feedback traces, active/inactive coverage stratification, human-label validation, compiler latency, and anonymous
private-domain correctness pairs. `public_artifact/LICENSES.md` defines the
release licenses.

## Clean Boundary

The clean package excludes author-side change records, workline/version labels,
historical releases, raw private data, private mappings, credentials, internal
provider endpoints, local filesystem paths, and build byproducts.

## Verification

```bash
shasum -a 256 -c SHA256SUMS
cd public_artifact
bash verify_public_artifact.sh
python3 extended_controls/verify_extended_controls.py
```
