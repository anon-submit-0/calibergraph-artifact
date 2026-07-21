# release Task Validity and Adjudication Audit

This audit addresses the concern that NL2Metric-Caliber is merely a private scoring game. It gives reviewer-facing adjudication rules, boundary cases, and dispute handling for each label family.

| Label family | Adjudication rule | Boundary example | Dispute rule |
|---|---|---|---|
| Metric identity | Choose the governed metric whose numerator/denominator and scope match the request, not the nearest alias. | Refund amount when only return-rate exists. | If two metrics share aliases, formula role and required fields decide. |
| Dimension grain | If multiple levels on one hierarchy path are requested, keep the governed finest requested level unless the metric policy says otherwise. | country+city -> city; level1+level2 -> level2. | If dimensions are independent rather than hierarchical, keep both. |
| Caliber/coverage | Answer only if required numerator, denominator, filters, time/order fields, and table grain are covered. | Rate metric without denominator coverage. | If related table has the metric but lacks requested grain/filter, refuse or certify missing coverage. |
| Temporal/as-of | Use requested or default valid-time binding only when the source supports it. | Current snapshot asked as historical as-of. | If valid-time anchor absent, refusal is preferred to silently using load time. |
| Disclosure/refusal | Raw identifiers, private mappings, SQL/DDL, off-domain, and unsupported metrics must be refused. | show raw row identifiers behind assertion. | If query asks aggregate plus private ids, refusal dominates. |
| Comparison policy | For multi-metric comparisons, follow released primary-metric or explicit comparison policy. | A vs. B when only A has coverage. | If comparison support is under-specified, refuse or return governed primary metric per policy. |

The released `LABEL_POLICY.md`, protocol cards, and failure certificates make these rules inspectable. They do not make the task externally authored; instead, they make the governed-contract boundary explicit and reproducible.
