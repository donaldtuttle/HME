# Reproducibility

## Current active-engine pin

```text
qosmos_hme_engine.py
SHA-256 1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11
```

The machine-readable verification record is
[`evidence/bridge_active_engine_validation_2026-08-24.json`](../evidence/bridge_active_engine_validation_2026-08-24.json).

## Commands

```bash
python qosmos_hme_engine.py --self-test
pytest -q
python tests/hme_independent_audit.py \
  --engine ./qosmos_hme_engine.py \
  --output outputs/hme_audit.json
python integrations/sfd_to_hme_bridge.py \
  --output outputs/sfd_hme_bridge.json
```

## Stable bridge invariants

Across the observed CI matrix, the active bridge preserved:

```text
engine_sha256    1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11
signature_hash   7fef693477ffaf55104f12f25be9b91b72a8ab8e4aed8d13c4c3604fa5719ce9
trajectory_hash  e90921fbd2fd990efab3b684249de68a28e7186e8fc226d2f3ca3a4038e8f5db
write_glyph      Σ◯
top_is_artifact  true
retrieval_score  0.9307851800354883 ± 1e-12
```

## Numeric byte-receipt boundary

The artifact identity includes SHA-256 hashes of floating-point payload bytes
and an FFT-derived pattern. Heterogeneous GitHub runners produced two complete,
internally consistent byte receipts while preserving the stable invariants
above.

### `numeric_bytes_7264`

```text
artifact_id   7264c7cc7b27aceb15f1
payload_hash  cae26ced8c2e11a484d0a5abeb7da26959c93633a44b169499957b1da20e2ea8
pattern_hash  3381e092455f79f3e72816fa6e31eba39929264fa7b4986e58faa8227cab2d67
```

### `numeric_bytes_d902`

```text
artifact_id   d902825c52772941b345
payload_hash  d363f67bdd7ac2d963c7884cd1750211872314cac8b198fb8c43681c46d80b4b
pattern_hash  f28f0fa635dd31ad745d096fa948791ab0e5a7bddbe3e142a414c4ed97f754b3
```

The second tuple was first recorded with the earlier v2.2 bridge and its
artifact ID later reappeared under the current engine on a Python 3.12 westus2
runner. A dedicated before/after-pytest diagnostic did not reproduce test-order
contamination.

The most plausible explanation is low-order floating-point or numerical-backend
variation in resampling, normalization, and FFT operations. The exact cause has
not been isolated.

## Current validation rule

The bridge gate now requires:

1. the active engine hash and all stable invariants;
2. one complete recognized `(artifact_id, payload_hash, pattern_hash)` tuple;
3. no mixing of components across tuples; and
4. failure on every unregistered tuple.

This is stricter than accepting any top hit, but more honest than pretending
floating-point byte identity is portable across arbitrary hardware.

## CI observations

```text
run 32800839685  numeric_bytes_7264 across Python 3.10 / 3.12 / 3.13
run 32801899956  d902 artifact ID on Python 3.12 westus2; 7264 on 3.10 / 3.13
run 32802184979  numeric_bytes_7264 before and after pytest on all three lanes
```

## Future refinement

A declared rounding or quantization layer before numeric hashing could create a
portable canonical representation. That would change artifact identity and
requires a separate design, migration, and compatibility decision. It was not
introduced here.

## Evidence discipline

A passing bridge check establishes conformance for the pinned implementation and
recognized numerical receipt family. It does not establish bit-identical arrays
across arbitrary numerical backends, scientific validity, calibrated
confidence, canonical weight, consciousness, or physical memory dynamics.
