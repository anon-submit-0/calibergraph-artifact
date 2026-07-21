# Contract Mutation Suite

The suite mutates one released contract input at a time. It is an implementation test, not an accuracy benchmark.

| Case | Expected | Observed | Pass |
|---|---|---|---:|
| contract_valid | witness | witness | true |
| contract_field_failure | field | field | true |
| contract_caliber_failure | caliber | caliber | true |
| contract_grain_failure | grain | grain | true |
| contract_coverage_failure | coverage | coverage | true |
| contract_time_failure | time | time | true |
| contract_policy_failure | policy | policy | true |
