# Reproducibility

## Current active-engine verification

The current engine is pinned by byte hash:

```text
qosmos_hme_engine.py
SHA-256 1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11
```

GitHub Actions run `32800839685` reproduced one identical SFD → HME bridge
receipt in all three CI lanes:

```text
Python 3.10.21 / NumPy 2.2.6
Python 3.12.14 / NumPy 2.5.2
Python 3.13.15 / NumPy 2.5.2
```

The machine-readable record is
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

## Current expected bridge pins

```text
engine_sha256    1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11
signature_hash   7fef693477ffaf55104f12f25be9b91b72a8ab8e4aed8d13c4c3604fa5719ce9
trajectory_hash  e90921fbd2fd990efab3b684249de68a28e7186e8fc226d2f3ca3a4038e8f5db
artifact_id      7264c7cc7b27aceb15f1
payload_hash     cae26ced8c2e11a484d0a5abeb7da26959c93633a44b169499957b1da20e2ea8
pattern_hash     3381e092455f79f3e72816fa6e31eba39929264fa7b4986e58faa8227cab2d67
write_glyph      Σ◯
retrieval_score  0.9307851800354883
```

The bridge script hashes `qosmos_hme_engine.py` during execution and fails its
receipt check when the source no longer matches the active engine pin. The test
imports the same expected-receipt object rather than maintaining a second copy.

## Historical v2.2 baseline

The earlier focused ingest used engine:

```text
SHA-256 f81fb49e265d83f5206220584dfc6cabf28aeee5266aca33654182be1549c080
```

It produced:

```text
artifact_id   d902825c52772941b345
payload_hash  d363f67bdd7ac2d963c7884cd1750211872314cac8b198fb8c43681c46d80b4b
pattern_hash  f28f0fa635dd31ad745d096fa948791ab0e5a7bddbe3e142a414c4ed97f754b3
```

That receipt remains historical evidence for the `v2.2.0-baseline` source. It
must not be used as the pass gate for the current engine.

## Evidence discipline

A matching hash or receipt establishes byte identity or deterministic output
for the pinned implementation and protocol. It does not establish scientific
validity, calibrated confidence, canonical weight, consciousness, or physical
memory dynamics.
