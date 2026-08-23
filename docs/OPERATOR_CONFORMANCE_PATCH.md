# HME Operator-Typing Conformance Patch

**Status:** DEVELOP realization patch — noncanonical  
**Purpose:** Correct a realization-local glyph-slide without changing the HME numerical algorithms.

## Finding

The recovered `qosmos_hme_engine.py` used `Θλ` as the default glyph for memory-write operations and labeled collapse-to-memory edges as `Λψ→Θλ:commit`.

The current typed branch-lifecycle discipline separates the roles:

```text
Λψ           collapse / projection event
Σ◯           consolidation / durable memory write
Θλ           retrieval / ReplayPlan or RecallPacket production
ApplyReplay  explicit state mutation after retrieval
Π↺           recurrence / ordered lineage
```

## Patch applied

The bundled engine changes only the semantic defaults and relationship labels below:

```text
HME.encode default glyph                    Θλ → Σ◯
HME.encode_symbol default glyph             Θλ → Σ◯
QOSMOSHMEEngine.encode_memory default        Θλ → Σ◯
QOSMOSHMEEngine.step memory_glyph default    Θλ → Σ◯
QOSMOSCoreHME.step_core write glyph          Θλ → Σ◯
QMesh memory→collapse relation               Θλ:memory_to_collapse
                                               → Π↺:memory_precedes_collapse
QMesh collapse→memory relation               Λψ→Θλ:commit
                                               → Λψ→Σ◯:consolidate
```

Documentation examples and self-tests were updated to match.

## What did not change

```text
FFT-derived HME pattern construction
complex field superposition
artifact IDs and hashes
retrieval scoring
W(t) diagnostic projection
collapse arithmetic
QMesh node structure
serialization formats
```

## Provenance

The unmodified source is preserved at:

```text
legacy/qosmos_hme_engine_original_2026-07-15.py
```

The external checksum receipt is preserved at:

```text
reports/qosmos_hme_v2_2_SHA256_original.txt
```

The patched and original hashes are recorded in `SOURCE_MANIFEST.json` and the execution manifest.

## Claim boundary

This patch improves semantic typing in this realization. It does not amend QOFT canon, demonstrate consciousness, or establish a physical memory field.
