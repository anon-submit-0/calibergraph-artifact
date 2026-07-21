# Enterprise Aggregate Control

This directory contains correctness-only paired evidence for 159 enterprise
cases. Query text, labels, business identifiers, metric identifiers, dimensions,
raw model responses, and private mappings are not released. Case ids are new
anonymous sequence numbers and cannot be joined back to enterprise records.

`python3 recompute.py` deterministically regenerates all accuracies,
contingency tables, exact McNemar tests, and paired bootstrap intervals from the
boolean pairs. CaliberGraph is 0.925 and validator-feedback replanning is 0.899;
their 0.025 difference is not significant (CI [-0.019, 0.069], `p=0.388`). The
paper therefore uses this evidence only as a recurrence check, never as a
predictive-superiority claim.
