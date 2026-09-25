# HME API interpretation

- Encode numeric items by resampling, optional Hann windowing, normalization, and a 2D inverse FFT of a spectral outer product. Add each pattern to a bounded spatial patch.
- Retrieve by scoring retained artifacts: 0.38 spatial proximity + 0.42 absolute normalized item/query inner product + 0.20 field/pattern correlation. Query preprocessing does not include the write-time Hann window.
- Separate the inverse-FFT `decoded_surface` from `decoded_vector`, which averages cached payloads. Removing the ledger removes exact identity retrieval.
- Inspect `base_score`, optional normalized `salience`, and `final_score` separately. `relevance_score` reports the selected hit's base score, not a calibrated probability.
- Interpret `NO_MATCH` as no candidate passing the relevance threshold. Interpret `LOW_WRITE_SALIENCE` as a separate optional rejection retaining the hit list.
- Treat artifact IDs as schema-specific insertion identities over selected fields. They include the counter, caller time, tag, operation, position, and processed-vector/pattern hashes, but omit arbitrary metadata and graph edges.
- Expect record eviction at `max_records`; residual field contributions remain. The mutable lineage graph is independent of direct storage clear/merge calls.
- Treat `save_npz()` as a field/metadata inspection export. It does not save all cached vectors, patterns, or lineage needed for a full restart.

Consult repository `docs/ARCHITECTURE.md`, `docs/MIGRATION_V3.md`, and `docs/EVALUATION_PLAN.md` for the full contracts and proposed comparisons.
