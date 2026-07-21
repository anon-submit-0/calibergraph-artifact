# release dbt MetricFlow Validator Control

This is a real dbt/MetricFlow validator control over a minimal public DuckDB semantic-layer project. It validates MetricFlow semantics and demonstrates what metrics-as-code catches; it does not model natural-language caliber selection, refusal/disclosure, or coverage witnesses.

`mf`: mf, version 0.11.0

Return code: `0`

```text
<python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'. See: https://github.com/urllib3/urllib3/issues/3020
  warnings.warn(
‼️ Warning: A new version of the MetricFlow CLI is available.
💡 Please update to version 0.13.0, released 2026-05-12 20:34:12 by running:
	$ pip install --upgrade dbt-metricflow

(To see warnings and future-errors, run again with flag `--show-all`)


⠋ Building manifest from dbt project root

⠙ Building manifest from dbt project root
✔ 🎉 Successfully parsed manifest from dbt project


⠋ Validating semantics of built manifest

⠙ Validating semantics of built manifest
✔ 🎉 Successfully validated the semantics of built manifest (ERRORS: 0, FUTURE_ERRORS: 0, WARNINGS: 0)
```
