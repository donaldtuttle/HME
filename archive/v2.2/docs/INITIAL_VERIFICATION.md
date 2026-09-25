# Initial Verification Record

**Date:** 2026-08-23  
**Scope:** Initial HME repository assembly performed before public publication  
**Classification:** DEVELOP typed realization

## Environment

```text
Python      3.13.5
NumPy       2.3.5
Pillow      12.3.0
Matplotlib  3.10.8
```

## Commands and results

```text
python qosmos_hme_engine.py --self-test
PASS

python integrations/symbolic_field_dynamics.py --self-test
PASS

python integrations/sfd_to_hme_bridge.py
PASS, all frozen bridge hashes reproduced

pytest -q
6 passed

python tests/hme_independent_audit.py --engine ./qosmos_hme_engine.py
PASS on deterministic, linear-superposition, retrieval, and ablation checks
```

## Frozen bridge values

```text
SFD signature hash   7fef693477ffaf55104f12f25be9b91b72a8ab8e4aed8d13c4c3604fa5719ce9
SFD trajectory hash  e90921fbd2fd990efab3b684249de68a28e7186e8fc226d2f3ca3a4038e8f5db
HME artifact ID      d902825c52772941b345
Payload hash         d363f67bdd7ac2d963c7884cd1750211872314cac8b198fb8c43681c46d80b4b
Pattern hash         f28f0fa635dd31ad745d096fa948791ab0e5a7bddbe3e142a414c4ed97f754b3
Retrieval score      0.9307851800354882
Write glyph          Σ◯
```

## Audit boundary

The unrelated-query probe returned a highest available score near `0.733`. This confirms that the current retrieval score is not a calibrated probability and does not implement open-set rejection.


## Evidence files

```text
evidence/engine_self_test_2026-08-23.json
evidence/sfd_self_test_2026-08-23.json
evidence/pytest_2026-08-23.txt
evidence/audit_repository_validation_2026-08-23.json
evidence/bridge_repository_validation_2026-08-23.json
```
