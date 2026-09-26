# Field-only consolidation (DEVELOP)

Step 0 is an opt-in adapter, `hme_consolidation.ConsolidatingMemory`. It does not
modify the pinned v3.1 storage, runtime or dynamics modules or any release tag.
This is software/invariant validation, not a compression-quality, salience,
damage-tolerance or semantic-continuity result. The study sequence is in
[the consolidation plan](../experiments/consolidation_plan/README.md).

## Contract and use

```python
import numpy as np
from hme_consolidation import ConsolidatingMemory

memory = ConsolidatingMemory(dimension=16, use_hann_window=False, decay=0.0)
memory.write(np.arange(1., 17.), gain=1.0)
memory.write(np.arange(2., 18.), gain=3.0)
before = memory.storage_report()
memory.consolidate()  # Explicit, irreversible, idempotent.
after = memory.storage_report()

# Future writes do not rebuild records, payload caches or lineage.
memory.write(np.arange(3., 19.), gain=1.0)
visible = np.arange(16) % 2 == 0
query = np.arange(2., 18.)
query[~visible] = np.nan
reconstruction = memory.reconstruct(query, visible)
memory.save('memory.hme')  # Creates a new file; refuses to overwrite.
restored = ConsolidatingMemory.load('memory.hme')
```

Before consolidation, the adapter privately owns an ordinary HMEEngine.
`consolidate()` copies the active d-by-d patch into an owning contiguous array,
clears its records, payloads, patterns and lineage, and releases the old engine
and full grid. The active complex pattern bytes remain unchanged, including FFT
roundoff residues. Only the zero exterior is omitted. Afterward the adapter owns
the complex patch and a 48-byte fixed-width control array, with no saved engine,
codec, per-write list, or array view keeping the larger allocation alive.
`patch_copy()` returns a caller-owned active patch. For compatibility,
`field_copy()` materializes an independent full-grid inspection copy with a zero
exterior. That requested allocation is temporary/caller-owned, not retained memory.
Post-consolidation write, moment, reconstruction, save and load paths operate on
the patch without reconstituting the old grid.

This is a new managed stream, not an automatic conversion of arbitrary existing
HMEEngine histories. Importing an old field whose gains, decay, clipping, merges
or site layout are unknown cannot establish its moment normalizer. An import
adapter would require a separate explicit provenance contract.

All writes are numeric and co-located at one central, unclipped patch. They use
the unchanged core's resampling, optional Hann window, unit normalization and
FFT pattern code. The NEW adapter defaults to `use_hann_window=False`; the pinned
v3.1 core still defaults to True and is untouched. Hann can be explicitly enabled
for encoding/moment experiments, but `reconstruct()` raises in that mode. Tapering
zeros the endpoints and changes the stored coordinate scales, so neither silently
windowing a raw query nor inverse-windowing can recover the discarded endpoints.
Existing Hann-on checkpoints remain Hann-on; loading does not invent lost data.
Zero/degenerate processed vectors, nonfinite data, invalid
gains and accumulator overflow are rejected before mutation. Positive and zero
gains are allowed; negative weights are not. This intentionally narrows the
unrestricted core API to a PSD-compatible moment stream.

`gain` is supplied by the caller. It is not an inferred salience or truth label,
and there is no new automatic salience policy. For each accepted write:

```text
F <- (1-decay) F + gain P(x)
W <- (1-decay) W + gain
Q <- (1-decay)^2 Q + gain^2
C <- aligned_column_unflip(F_patch) / W
weight_effective_sample_size = W^2/Q
```

The readout removes numerical anti-Hermitian residue by symmetrization. No local
covariance claim is made for overlapping sites. Decay is per accepted write, not
elapsed wall-clock time. A zero-gain write still advances decay and the counter.
The effective-sample statistic describes weight concentration, not independent
observations or preserved semantic facts. Fixed-width floats have finite precision;
uint64 count exhaustion and floating overflow are errors, not unbounded storage.

`reconstruct()` implements the experimental moment-based ridge completion used
in the numerical research direction. It ignores hidden query entries, preserves
visible values, and neither reads nor restores records. With Hann disabled,
`moment()` describes unit-normalized, possibly resampled training vectors. The
reader takes a dimension-length partial vector on those coordinate axes; it does
not undo resampling or infer an original norm from stored records. It does not identify
which original item produced a query. `retrieve()` explicitly raises after
consolidation rather than inventing an identity match. The remaining second
moment is invariant under a whole-vector sign reversal, regardless of gain.

## Byte accounting

Default dimension 16, with a 64-by-64 grid only during the recording phase:

| Retained/serialized component | Bytes |
|---|---:|
| Active 16-by-16 complex128 patch | 4,096 |
| Fixed-width control array | 48 |
| Total retained array data after consolidation | 4,144 |
| Complete uncompressed v2 checkpoint | 4,184 |
| Packed real symmetric moment, numerical reference only | 1,088 |
| Dense real 16-by-16 moment, numerical reference only | 2,048 |

The checkpoint adds an 8-byte `HMEFC002` marker and a 32-byte SHA-256 digest.
It contains the exact active FFT-layout patch, source-grid dimensions,
preprocessing/decay flags, weight state and counter. No raw vectors or lineage
are present. Checkpoint byte counts are measured on disk, not compressed sizes.
The packed-real figure is a comparison representation for real moments, NOT the
implemented checkpoint or a universal information-theoretic lower bound. Complex
Hermitian moments have d^2 real degrees of freedom; additional structure such as
a known trace or low rank can change parameter counts. Packing a real symmetric
moment need not preserve the complex FFT roundoff bytes that this patch retains.

Loading always resumes in consolidated mode and explicitly enforces
`dimension <= memory_size` before payload reshape. The earlier loader already
inherited this bound through `HMEConfig`; the direct check and correctly hashed
malformed-header regression now make it explicit. Length, schema, digest and
finiteness checks remain. Legacy `HMEFC001` full-grid checkpoints are read only
if their exterior is zero, cropped to an owning patch, and upgraded in memory
to v2. Nonzero exterior values are rejected rather than silently discarded.
Re-saving writes v2. No old release tag or pinned file is rewritten.
The digest detects damage; it does not repair it or authenticate an author.

`instance_owned_bytes` additionally traverses instance-reachable Python objects,
counting aliases once. Its exact value depends on the Python/NumPy build. It
excludes classes/modules/code, interpreter RSS, allocator slack, temporary write/
read/serialization workspace and caller-owned inputs, results or saved copies.
Those costs must be measured separately in a deployment benchmark. Consolidation
releases owned references; it is not secure deletion of RAM or caller files.
The managed recording phase is not bounded: provenance can grow until explicitly
consolidated. Only consolidated mode has the fixed retained-state contract.

For d=16, packed real symmetric matrix DATA (1,088 bytes) is smaller than nine
raw float64 vectors. That is a hypothetical packed-matrix reference, not a storage
claim about this adapter. Its actual 4,144 retained array bytes first become
smaller than raw 16-float64 vector data at N=33; the 4,184-byte checkpoint also
crosses at N=33. Object/index/RNG/control overhead for competing memories must
be charged consistently in REC-3. The original 65,584-byte retained full-grid
implementation crossed at N=513 and is superseded, not hidden in a view.

REC-3 must freeze the actually implemented representation and budget before
running seeds: complex patch and packed-real direct moments are different arms,
with actual metadata, allocator/object exclusions and checkpoint bytes reported
separately. An array-only parameter count is not an equal-byte comparison.

## Development verification

```bash
python -m pytest tests/test_consolidation.py -q
python scripts/check_consolidation.py --output outputs/consolidation-step0.json
```

Fixtures check exact active-patch and reconstructed full-grid parity across
transition and subsequent writes, real/complex payloads, gains/decay, and no
surviving engine/full-grid/payload/pattern/lineage references. They check constant
retained bytes, explicit identity unavailability, weighted direct-moment parity,
compact and legacy checkpoint continuation/integrity, hidden-coordinate isolation,
and the sign-reversal limitation. A fixed 300-write rank-3/dimension-16 regression
hides coordinates 0, 5 and 15 and verifies default Hann-off reconstruction before
consolidation, after it, and after save/load. Explicit Hann-on reconstruction
raises in every mode. This is a development regression, not the reviewer's
unprovided seed or a preregistered accuracy comparison. Fixtures are deterministic development
checks, not preregistered performance outcomes. Original reports and source pins
remain unchanged. This adapter is not yet a default release behavior.

## Review history

The original full-grid development evidence is retained byte-for-byte as
`evidence/consolidation_step0_full_grid.json` (source `b45a986`).
`evidence/consolidation_step0.json` is regenerated for the compact adapter with
its current source hashes and runtime. The amendment changes this unreleased
adapter's default, retained layout and checkpoint version, not any frozen
REC-1/NN evaluator or the pinned engine. SAL-1, HOLO-1, REC-3 and CONT-1 remain
designs without preregistered efficacy outcomes.
