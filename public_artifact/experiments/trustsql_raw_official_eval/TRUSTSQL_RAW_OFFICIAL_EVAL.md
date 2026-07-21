# release TrustSQL Raw Official Evaluation

Runs TrustSQL official evaluate.py on the downloaded raw test splits with transparent diagnostic predictions. This anchors refusal/answerability evidence; it is not a full NL2Metric-caliber benchmark because TrustSQL does not encode metric denominator, grain, coverage, or business-caliber witnesses.

Source: https://github.com/glee4810/TrustSQL @ `b7bc643a62545099748d3d18d0651cde51ae87a4`

Note: Spider uses `dataset/spider/database` following the official README.

| dataset | mode | n | feasible | infeasible | return | RS0 total | RS10 total | elapsed |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| atis | gold_oracle | 952 | 476 | 476 | 0 | 100.00 | 100.00 | 21.467 |
| atis | always_abstain | 952 | 476 | 476 | 0 | 50.00 | 50.00 | 11.065 |
| atis | unsafe_always_answer | 952 | 476 | 476 | 0 | 50.00 | -450.00 | 22.175 |
| advising | gold_oracle | 1066 | 533 | 533 | 0 | 100.00 | 100.00 | 18.574 |
| advising | always_abstain | 1066 | 533 | 533 | 0 | 50.00 | 50.00 | 9.684 |
| advising | unsafe_always_answer | 1066 | 533 | 533 | 0 | 50.00 | -450.00 | 18.449 |
| ehrsql | gold_oracle | 1868 | 934 | 934 | 0 | 90.36 | -6.00 | 2.934 |
| ehrsql | always_abstain | 1868 | 934 | 934 | 0 | 50.00 | 50.00 | 1.598 |
| ehrsql | unsafe_always_answer | 1868 | 934 | 934 | 0 | 40.36 | -556.00 | 2.998 |
| spider | gold_oracle | 1054 | 527 | 527 | 0 | 95.35 | 48.86 | 1.717 |
| spider | always_abstain | 1054 | 527 | 527 | 0 | 50.00 | 50.00 | 1.322 |
| spider | unsafe_always_answer | 1054 | 527 | 527 | 0 | 45.35 | -501.14 | 1.559 |
