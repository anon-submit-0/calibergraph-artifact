# Official Baseline Reproduction Audit

This audit distinguishes official upstream end-to-end reproduction from task-level baseline reproduction in this paper.

## AutoLink

- Repository: https://github.com/wzy416/AutoLink
- Commit: `26c723158445d5c831290315c9a93ba76eb5bd0e`
- Local status: `not_runnable_without_external_dependencies`
- Included upstream linking-result files: 547

Blocking dependencies:

- Spider 2.0-Lite resource directory is not included in the upstream clone.
- BigQuery credentials are required for bq*/ga* instances.
- Snowflake credentials are required for sf* instances.
- OpenAI-compatible API credentials must be inserted into run/main.sh.
- The official script targets Spider2-Lite Text-to-SQL, not NL2Metric-Caliber directly.

Paper action: Use the official repository as the protocol source, preserve the clone, and run a task-level AutoLink-derived E3 iterative schema/metric linking baseline on CaliberGraph benchmarks.

## SafeNLIDB

- Repository: https://github.com/tom68-ll/SAFENLIDB
- Commit: `0ad16d8b1e6cb3e533fc6c5433a3dcd575967b08`
- Local status: `training_not_runnable_without_external_datasets_and_gpu_stack`
- Included ShieldSQL cases: 540

Blocking dependencies:

- The README requires OmniSQL, SecureSQL, Spider, and BIRD database downloads not included in the clone.
- Training requires Python 3.9, PyTorch 2.6, CUDA 12.4, vLLM 0.8.4, and LLaMA-Factory.
- Reasoning warm-up and alternating preference optimization require model checkpoints and GPU training.
- Reliability Score requires the merged benchmark databases and execution lists.

Paper action: Run the included ShieldSQL safety classification set with a SafeNLIDB-derived E3 secure-CoT guard, and run a utility-preserving policy guard on NL2Metric-Caliber benchmarks.

