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
`consolidate()` transfers its existing field allocation without modifying bytes,
clears its records, payloads, patterns and lineage, and drops the engine reference.
Afterward the adapter's only retained state is the complex field and a 48-byte
fixed-width control array. There is no saved engine, codec or per-write list.
The arrays are owned, with no views retaining a larger hidden allocation.

This is a new managed stream, not an automatic conversion of arbitrary existing
HMEEngine histories. Importing an old field whose gains, decay, clipping, merges
or site layout are unknown cannot establish its moment normalizer. An import
adapter would require a separate explicit provenance contract.

All writes are numeric and co-located at one central, unclipped patch. They use
the unchanged core's resampling, optional Hann window, unit normalization and
FFT pattern code. The adapter's Hann default stays True; numeric study examples
opt out explicitly. Zero/degenerate processed vectors, nonfinite data, invalid
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
visible values, and neither reads nor restores records. It does not identify
which original item produced a query. `retrieve()` explicitly raises after
consolidation rather than inventing an identity match. The remaining second
moment is invariant under a whole-vector sign reversal, regardless of gain.

## Byte accounting

Default 64-by-64 complex128 field, independent of observation count:

| Retained/serialized component | Bytes |
|---|---:|
| Field data | 65,536 |
| Fixed-width control array | 48 |
| Total retained array data | 65,584 |
| Complete uncompressed checkpoint | 65,624 |

The checkpoint adds an 8-byte format marker and a 32-byte SHA-256 digest. It
contains the field, dimensions, preprocessing/decay flags, weight state and count,
not raw vectors or lineage. Loading resumes in consolidated mode. The digest
detects damage, does not repair it and is not an authenticity signature. Checkpoint
sizes are measured on disk; compression and changing ZIP metadata are not involved.

`instance_owned_bytes` additionally traverses instance-reachable Python objects,
counting aliases once. Its exact value depends on the Python/NumPy build. It
excludes classes/modules/code, interpreter RSS, allocator slack, temporary write/
read/serialization workspace and caller-owned inputs, results or saved copies.
Those costs must be measured separately in a deployment benchmark. Consolidation
releases owned references; it is not secure deletion of RAM or caller files.
The managed recording phase is not bounded: provenance can grow until explicitly
consolidated. Only consolidated mode has the fixed retained-state contract.

The ideal packed real symmetric C at d=16 has 136 float64 entries (1,088 bytes),
so it is smaller than nine 16-float64 raw vectors. That break-even does NOT apply
to this full complex grid. Its 65,584 retained array bytes first beat raw float64
vector data at N=513 for d=16, before comparing object or index overhead. A dense
real C uses 2,048 data bytes; a compact complex d-by-d patch uses 4,096. These are
separate possible representations, not invisible savings already implemented.

## Development verification

```bash
python -m pytest tests/test_consolidation.py -q
python scripts/check_consolidation.py --output outputs/consolidation-step0.json
```

Fixtures check exact pinned-engine field parity across transition and subsequent
writes, real/complex payloads, gains/decay, no surviving engine/payload/pattern/
lineage references, constant retained bytes, explicit identity unavailability,
weighted direct-moment parity, checkpoint continuation/integrity, hidden-coordinate
isolation and a sign-reversal limitation. Fixtures are deterministic development
checks, not preregistered performance outcomes. Original reports and source pins
remain unchanged. This adapter is not yet a default release behavior.
