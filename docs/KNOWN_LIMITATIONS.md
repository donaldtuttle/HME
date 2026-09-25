# Known limitations

- Retrieval scans retained records and depends on their cached vectors and patterns. Exact identification is not field-only.
- Scores are heuristic and uncalibrated. The default relevance threshold admits any candidate; unrelated queries can receive substantial scores.
- String hashing supplies repeatable vectors, not language semantics.
- The encoder and query path apply different preprocessing, and absolute similarity cannot distinguish sign/global phase reversal.
- Record eviction leaves field residue. Lineage can grow beyond the retained record limit and is not automatically synchronized by direct storage merge/clear calls.
- IDs contain truncated hashes over selected fields. Records are mutable, metadata is not authenticated, and lineage is not a Merkle DAG or tamper-evident log.
- NPZ export is not a complete reloadable checkpoint.
- Floating-point byte hashes are environment-sensitive. Pin Python, NumPy, platform, and source when reproducing results.
- Optional salience channels are experimental and disabled by default. No comparative efficacy or calibrated probability is claimed.
- HRR-style binding/unbinding and production database guarantees are not implemented.
- The optional runtime restores state-derived salience and field events, not semantic context conditioning or prediction-error learning. History/activity/bias diagnostics do not change retrieval queries.
- Runtime metrics describe pre-event state; event flags and returned projections describe the completed tick. Telemetry/frame history grows in memory and exports are not restart checkpoints.
- The diffusion simulator's threshold score is diagnostic; it does not apply phase-lock events or automatically control memory writes. Raster inputs depend on the selected font.
