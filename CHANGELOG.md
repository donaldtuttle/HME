# Changelog

## 3.1.0 — restore optional field dynamics

- Publish HME-NN-3: thirty preregistered seeds separating raw-input NN, processed-vector NN, Hann/query preprocessing, sign and field ablations. Retain all prior reports and unchanged pinned engine/default bytes.
- Fix direct-checkout execution of the independent audit and runtime example without an editable install; add isolated-interpreter regression tests. NumPy remains required.
- Document the explicit no-window numeric configuration and the negative symmetric-taper result. The active suite now has 138 tests; the archived suite remains 11 tests.
- Add guarded v3.1.0 release publication after version, integrity, self-test and active/historical test gates. Existing tags and releases are not replaced.

- Add a fresh current-release evidence bundle with five-seed retrieval results, per-tick runtime observations, explicit source/collector hashes, and separately labelled historical tests. Retain CI results as downloadable artifacts and correct the README version badge.

- Restore state updates, diagnostic projections, thresholded phase locking, magnitude quantization, event lineage and finalized tick telemetry in `hme_runtime.py`.
- Restore automatic field-derived `write_salience` production and connect it to the existing optional gain/ranking/rejection controls.
- Add `AgentRuntime` with explicit history, activity, neighbor-transfer, bias and logger adapters, plus plain host/agent binding.
- Restore seeded spatial diffusion, damping, periodic drive, signature extraction and the memory bridge in `hme_dynamics.py`.
- Restore optional plotting/animation and add an executable example and migration guide.
- Compare the restored numerical paths against the immutable archive, including event timing and all salience/ablation settings.
- Keep the 3.0 memory-core bytes, memory API/schema and full historical snapshot unchanged. This corrects the excessive runtime removal in 3.0; it does not introduce the proposed semantic decoder or discrepancy controller.

## 3.0.0 — standalone HME

- Extract the numerical storage/ranking core into `hme_engine.py`, requiring only NumPy.
- Introduce `HMEEngine`, `LineageGraph`, and default-off `SalienceConfig` with plain API names and `hme-v3` artifact identities.
- Rename uncalibrated `confidence` to `relevance_score`.
- Remove framework adapters, equations, glyph requirements, and framework visualizations from the installed runtime and active documentation.
- Preserve the complete previous repository at `archive/v2.2/` with unchanged historical source/evidence bytes.
- Add numerical equivalence tests, standalone packaging/CLI, a migrated retrieval audit, related literature, and a calibration/baseline evaluation plan.

For prior changes, see the [archived changelog](archive/v2.2/CHANGELOG.md).
