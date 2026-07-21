# Coverage-Activity Stratification

This analysis separates headline base cases according to whether the released
contract exposes an active physical-coverage requirement. An inactive check is
not relabeled as a passed coverage test.

```bash
python3 extended_controls/coverage_activity_analysis/recompute.py
```

The script joins only released case IDs, gold labels, compiler traces, stored
complete-contract predictions, and stored shared-validator repair histories.
It reports Iowa-32, MultiGov-510, IndustrialCaseText-157, and their pooled
headline scope. GovTwin and Chinook are not part of the headline pooled result.
