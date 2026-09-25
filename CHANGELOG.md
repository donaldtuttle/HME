# Changelog

## 3.0.0 — standalone HME

- Extract the numerical storage/ranking core into `hme_engine.py`, requiring only NumPy.
- Introduce `HMEEngine`, `LineageGraph`, and default-off `SalienceConfig` with plain API names and `hme-v3` artifact identities.
- Rename uncalibrated `confidence` to `relevance_score`.
- Remove framework adapters, equations, glyph requirements, and framework visualizations from the installed runtime and active documentation.
- Preserve the complete previous repository at `archive/v2.2/` with unchanged historical source/evidence bytes.
- Add numerical equivalence tests, standalone packaging/CLI, a migrated retrieval audit, related literature, and a calibration/baseline evaluation plan.

For prior changes, see the [archived changelog](archive/v2.2/CHANGELOG.md).
