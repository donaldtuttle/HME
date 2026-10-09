# HME-MO-1 implementation map

Status: DESIGN / DEVELOP. Inspected current main `a4d871618e31b8184c2cf5c2e13c9256accd254d` with a clean checkout. No applicable root AGENTS.md or experiment name collision was found. The supplied AGENTS attachment describes a different agent workbench; it is not a repository instruction to build an application here.

| Component | Verified behavior and experiment use |
|---|---|
| `hme_engine.py:HME._generate_pattern` | Length-16 numeric input becomes complex128, receives Hann once, then L2 normalization. FFT spectral outer product and inverse FFT2 produce a 16 × 16 complex128 pattern, normalized by Frobenius norm. Zero inputs remain zero. |
| `HME.encode` | Adds `strength * write_weight * pattern` to the addressed patch. Optional decay multiplies the whole field before a write. HME-MO-1 explicitly sets decay zero and gain 0.10 for every write. |
| `_patch_slices` | Production supports boundary clipping; the experiment rejects it before construction. No interpolation or texture filter is involved. |
| `_trim_records` | Evicts oldest records, payloads and isolated patterns; does not subtract their field contributions. This experiment allocates exactly 128 records for 128 writes and checks no loss. |
| `HMEEngine.encode_memory` | Caller supplies addresses; optional write salience can change gain. All salience switches are explicitly off. The engine does not derive addresses from numeric similarity. |
| Production `HME.retrieve` | Uses query address, spatial distance, absolute payload cosine and correlation of the accumulated patch with its stored isolated pattern. The pattern term is not query-pattern correlation. It can return payload-based decoded vectors. This API is not a retrieval arm here. |
| Frozen NN-2B `retrieval.py` | Imported unchanged. Candidate-local accumulated patches are extracted and normalized. Scores are absolute complex Frobenius correlation with the encoded query. Hybrid adds 0.42 signed vector cosine and 0.20 field score. Common field offsets are cancelled in zero/shared-field controls, preserving rankings. |
| Query processing | Primary symmetric mode applies Hann once then normalizes, then encodes with no second Hann. Native mode only normalizes and is descriptive. This changes the primary mode relative to NN-2B. |
| Search snapshots | Frozen snapshot base retains records, lineage, positions and artifact IDs. Local adapters add opaque external IDs and their artifact map. Signed/absolute NN also retain processed vectors; field only retains field and optional accumulated-patch cache, with `vectors=None`, no isolated patterns or source corpus. Hybrid also retains processed vectors. All are charged. |
| RAW_SIGNED_NN | Normalized raw vectors and raw queries, without Hann. Retains vectors and external IDs. Its representation differs intentionally from matched SIGNED_NN. |
| VECTOR_AGGREGATE | Selected raw or processed vectors, neighbor indices, positive normalized weights, empty-neighbor mask, IDs and rule. No field, family labels, hidden prototypes, targets or isolated pattern cache. |
| Cache lifecycle | Frozen field snapshots copy and make the field read-only. `replace_field` validates shape/finiteness and invalidates accumulated-patch cache. Direct writer mutation does not update a previously built snapshot; rebuilding or explicit field replacement is required. |
| Integrity/statistics | Existing root/source/archive checksum checks remain unchanged. Frozen NN-1 retained-object accounting is imported. New corpus-level statistics live only here. Local source provenance pins imported bytes and historical source commits. |

The current engine is byte-identical to NN-2B's engine source at `4662023b005ea7757cb6af4726961c214634b1b7`. Exact hashes and byte lengths are in `SOURCE_PROVENANCE.json`. These are verified source observations. (ρ̂_conf_HIGH)

No production change is required. The intervention assigns related whole-memory vectors to overlapping addresses. It neither aligns shared features explicitly nor introduces a binding scheme. Whether this encoder produces useful agreement at actual patch offsets is an untested mechanism question, measured here. (ρ̂_conf_UNK)

NN-2B reported signed NN 52.03%, hybrid 50.29%, difference -1.74 percentage points with interval [-2.42, -1.09], for independent Gaussian vectors and content-independent positions. Those historical results are reported, not rerun here. They remain a failed historical advantage gate, with their own 4 MiB cap. (ρ̂_conf_HIGH: report contents)
