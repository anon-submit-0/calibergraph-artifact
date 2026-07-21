# Privacy Release Note

GovTwin-MetricCaliber is designed for public review and reproducibility. It is not a de-identified row-level export of enterprise data. The privacy claim is scoped to the released-artifact threat model: reviewers receive the synthetic files, but not the private source graph, raw data, or private-to-public mapping.

Controls applied:

- No row-level business facts are released.
- No raw enterprise natural-language queries are released.
- No customer, employee, product, channel, table, column, owner, timestamp, or document-token values are released.
- Public identifiers are synthetic and the private-to-public mapping is not released.
- The author-side generator is excluded from the reviewer artifact because it reads the private source snapshot.
- A sensitive-token scan is run before packaging the public artifact.
- The dataset preserves only graph shape, metric-caliber roles, dimension hierarchy, action labels, and failure-mode structure.

Reviewer use: reproduce public GovTwin results and audit the NL2Metric-Caliber task mechanics without accessing private enterprise data.
