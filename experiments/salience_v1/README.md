# SAL-1 implementation status

The bounded surprise-memory prototype is integrated as an opt-in experiment.
It is not enabled by the HME runtime and does not alter the pinned storage engine.

Implemented: field, direct-moment and forgetting-RLS backends; bounded exception
memory; trusted-feedback admission and retirement; FIFO and confirmation-refresh
eviction; base-preservation screening; radius selection from supplied validation
tables; configuration binding and byte-cap checks. Regression tests cover these
contracts. The deterministic smoke script demonstrates operation.

```bash
python -m pytest tests/test_salience_memory.py tests/test_salience_radius_review.py tests/test_salience_routine_gate.py -q
python experiments/salience_v1/smoke.py --output outputs/sal1-development.json
```

## Research boundary

[PROTOCOL_DRAFT.md](PROTOCOL_DRAFT.md) and policy v6 preserve the pre-corpus design.
No registered SAL-1 efficacy evaluation has been completed. Dataset construction,
noise/density settings, validation grids, numerical benefit margins, statistical
evaluator and hybrid checkpoint persistence are outside this integrated prototype.
They are future capabilities, not assertions that this implementation already
provides them. Correctness tests do not establish a memory-performance benefit.

The September pause proposal in PR #17 distinguishes a latent-target oracle from
matched noisy-feedback replay and proposes an additive paired correction gate.
That proposal was not adopted into policy v6; any future study must resolve and
version the complete contract before generating evaluation data. Do not interpret
the older draft correction gate as a completed noisy-feedback registration.
