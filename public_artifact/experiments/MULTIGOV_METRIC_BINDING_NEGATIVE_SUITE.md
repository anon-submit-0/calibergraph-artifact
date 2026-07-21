# MultiGov Metric-Specific Binding Negative Suite

Same-domain dependency edges and coverage bindings from other metrics remain present in every negative case.

| Mutation | Expected failure | Observed failure | Passed |
|---|---|---|---|
| valid_metric_specific_witness | none | none | true |
| remove_current_numerator_edge | caliber | caliber | true |
| remove_current_denominator_edge | caliber | caliber | true |
| remove_current_numerator_coverage_binding | coverage | coverage | true |
| remove_current_denominator_coverage_binding | coverage | coverage | true |
