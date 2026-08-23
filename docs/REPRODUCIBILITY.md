# Reproducibility

## Environment used for the focused ingest

```text
Python 3.13.5
NumPy 2.3.5
```

The supplied July bridge receipt records a separate execution under Python 3.12.3 / NumPy 2.4.4. Exact load-bearing hashes and retrieval values reproduced in the focused ingest.

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

## Expected bridge pins

```text
signature_hash   7fef693477ffaf55104f12f25be9b91b72a8ab8e4aed8d13c4c3604fa5719ce9
trajectory_hash  e90921fbd2fd990efab3b684249de68a28e7186e8fc226d2f3ca3a4038e8f5db
artifact_id      d902825c52772941b345
payload_hash     d363f67bdd7ac2d963c7884cd1750211872314cac8b198fb8c43681c46d80b4b
pattern_hash     f28f0fa635dd31ad745d096fa948791ab0e5a7bddbe3e142a414c4ed97f754b3
write_glyph      Σ◯
retrieval_score  0.9307851800354882
```

## Evidence discipline

A matching hash establishes byte or output identity, not scientific validity. Interpret the run only within the declared typed realization and intervention.
