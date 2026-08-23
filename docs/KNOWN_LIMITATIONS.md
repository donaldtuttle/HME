# Known Limitations

1. **Retrieval score is not calibrated confidence.** The top score is always returned when candidates exist; an unrelated query scored about `0.733` in the current audit.
2. **No explicit rejection state.** The engine lacks a calibrated `NO_MATCH` / `UNKNOWN` policy.
3. **Artifact identity is ledger-dependent.** Field-only reconstruction does not recover ledger identity.
4. **Partial string queries are unreliable.** Symbol/string matching should not be treated as semantic retrieval without additional tests.
5. **Same internal engine identity across two source hashes.** The active conformance source and preserved pre-conformance source both report `qosmos_hme_v2.2.0`; provenance must use hashes.
6. **Fixed thresholds are realization-local.** Collapse defaults are not universal constants and require calibration under scale or distribution changes.
7. **Optional core bindings may fall back.** Missing QOSMOS modules activate local fallback classes; the runtime should log which binding path is active when used in a larger system.
8. **No cross-realization generalization.** Results apply to the tested source and configuration unless a typed bridge and validation support broader inference.
