# Meaningful overlap experiment

**HME-MO-1 | DESIGN / DEVELOP | no confirmatory result.**

The October 9 recovery and fresh validation replay are documented in
[RECOVERY_REPORT.md](RECOVERY_REPORT.md). Raw replay records are committed under
`recovery_validation/`; the original October 6 report below is preserved.

This experiment asks whether placing related memories in overlapping field patches helps retrieve their siblings while preserving each item's identity. It rearranges existing whole-memory patterns; it does not implement shared-feature binding.

Read [DEVELOPMENT_REPORT.md](DEVELOPMENT_REPORT.md) for executed development/validation observations, [IMPLEMENTATION_MAP.md](IMPLEMENTATION_MAP.md) for the actual writer/readout, and [PROTOCOL.md](PROTOCOL.md) plus [protocol.json](protocol.json) for the complete proposed study. [REGISTRATION_REVIEW.md](REGISTRATION_REVIEW.md) lists the approval and freeze steps still required.

From the repository root, with its normal Python test/visualization dependencies:

```bash
python -m pytest -q tests/test_meaningful_overlap.py
python -m experiments.meaningful_overlap_v1.evaluate development --output outputs/mo-new-development
```

Every output directory must be new. To reproduce the predeclared validation workflow on already exposed validation namespaces:

```bash
python -m experiments.meaningful_overlap_v1.evaluate tune --output outputs/mo-reproduce-tuning
# Compare outputs/mo-reproduce-tuning/FROZEN_BASELINE.json with the committed selection.
python -m experiments.meaningful_overlap_v1.evaluate validation --output outputs/mo-reproduce-validation
python -m experiments.meaningful_overlap_v1.render_report outputs/mo-reproduce-validation --output outputs/mo-reproduce-plots
```

Do not overwrite or reselect the frozen baseline based on check outcomes. Reproducing validation is not new independent evidence. The build does not run reserved namespaces; the `confirmatory` CLI mode refuses execution while the protocol is proposed. Do not change that status merely to try the command.

The new Python modules cover numeric data/stream separation, fixed-slot assignment, frozen writer/readout adapters, vector aggregation, corpus-level statistics, retained-state/latency costs, registration integrity, evaluation and static report rendering. There is no production import of this experiment, service, dashboard or model call.

Historical NN-2B remains unchanged. Its NN means nearest neighbor. This work uses a different synthetic dataset and primary query preprocessing, and neither rescores old data nor reinterprets its failed gate.
