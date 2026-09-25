# HME architecture

## Encoding and storage

`HMEEngine` combines `HME`, `LineageGraph`, and an optional `SalienceConfig`.
There are no framework imports or external operator contracts.

For a numeric payload, the storage core:

1. Converts it to a finite complex vector and linearly resamples to the encoding resolution.
2. Applies a Hann window when enabled, then normalizes its Euclidean norm.
3. Computes `spectrum = fft(vector)`.
4. Computes `pattern = ifft2(spectrum[:, None] * conjugate(spectrum[None, :]))` and optionally normalizes it.
5. Adds `strength * write_weight * pattern` to a spatial patch, clipping the patch at field boundaries.

Strings first map to seeded Gaussian vectors. The seed comes from the first eight bytes of their SHA-256 digest. The engine's `seed` identifies a run; it does not change this deterministic string map. Numeric payloads are not hashed positional encodings, and placement does not bind a position vector to an item vector.

Optional write salience multiplies the strength using a bounded gain. Its value is supplied as `metadata["write_salience"]`. The memory core does not derive this value; the optional `FieldRuntime` and `AgentRuntime` calculate it from field state before each tick's memory write. See [Runtime](RUNTIME.md).

## Retrieval

Each retained artifact receives three scores:

```text
distance_score = exp(-0.5 * (distance / distance_sigma)^2)
query_score   = abs(vdot(stored_vector, query_vector)) / norm_product
pattern_score = abs(vdot(field_patch, stored_pattern_patch)) / norm_product
base_score    = clip(0.38*distance_score + 0.42*query_score + 0.20*pattern_score, 0, 1)
```

Zero-norm comparisons produce zero similarity. Without a query, `query_score` is one. Query vectors are normalized but do not receive the write-time Hann window; that asymmetry is retained from v2.2. Absolute similarity treats sign and global phase reversals as equivalent.

Candidates below the relevance threshold are removed first. Optional salience reranking can change the order of the survivors:

```text
salience = max(write_salience, 0) / (1 + max(write_salience, 0))
final_score = base_score + retrieval_weight * salience * (1 - base_score)
```

The selected hit's `base_score` is returned as `relevance_score`. It is never raised by reranking. An optional low-write-salience rejection returns `LOW_WRITE_SALIENCE` with the candidate list retained. No eligible candidates yields `NO_MATCH`.

`decoded_surface` is an inverse FFT of the selected field window. `decoded_vector` is a weighted average of cached payload vectors for the selected hits. It is not a field-only recovery of an original item.

## Identity, records, and lineage

`payload_hash` hashes the processed vector's dtype, shape, and exact array bytes. It does not hash the original input before resampling/windowing. `pattern_hash` hashes the derived pattern similarly.

The artifact ID is a 20-hex-character prefix of SHA-256 over a stable JSON object containing the schema, insertion counter, caller time `t`, tag, operation, position, payload hash, and pattern hash. This is an insertion identity, not simply `sha256(payload)`. Gain, write weight, arbitrary metadata, and graph edges are not authenticated by that ID. `t` defaults to zero and is caller-controlled, not a wall-clock timestamp.

The ledger keeps a maximum of `max_records` entries. Eviction removes cached payloads/patterns but leaves their field contributions. The lineage graph records sequential `next_memory` edges and can outlive evicted records; it is mutable and has no Merkle parent-hash chain. Direct use of `HME.encode` bypasses `HMEEngine` lineage recording. Direct field merge/clear operations do not synchronize the separate graph.

## Storage and serialization

`snapshot()` includes `engine_id`, `schema_id`, configuration, a rounded field hash, and records. `save_npz()` writes the field and this metadata, but omits cached payloads/patterns and the engine-level graph. It is an inspection export, not a full restart checkpoint. Exact numeric hashes can vary across numerical backends.
