# HME-NN-1: exact nearest-neighbor comparison

This is the first stage of HME's evaluation plan. The machine-readable
[protocol](protocol.json) is authoritative. It fixes ten new evaluation seeds,
128 items of dimension 16, four noise levels, two query preprocessing modes,
four methods, metrics, budgets, statistical analysis and the stopping rule.

## Decision

Does the existing HME ranker improve top-1 identity retrieval by a practically
useful amount over exact signed-cosine nearest neighbors when the inputs and
available information are matched?

The sole primary condition is native query preprocessing at Gaussian noise
sigma 1.0. The registered benefit is two percentage points. The paired-seed
95% bootstrap interval's **lower** endpoint must exceed +2 percentage points,
and both methods must fit the common storage cap, to support that claim.
An upper endpoint below zero supports a negative accuracy result in this condition.
Anything else fails to establish the registered practical benefit. Secondary
conditions cannot replace the primary after seeing results.

## Fairness and limits

All items occupy the same position, so addresses cannot identify a target.
Nearest neighbors use copies of the exact processed vectors stored by HME,
with the same records and lineage available. Every search receives only the
query and the shared position, never its expected item ID.

HME windows stored vectors but does not window its numeric queries. The native
comparison preserves that behavior for every method; the symmetric variant
windows queries for every method. Signed and absolute cosine are reported
separately. Zeroing only HME's field tests its field contribution while keeping
all candidate information. Erasing the ledger instead is a structural check:
the existing API may return a surface but cannot assign identity without records.

Every method gets the same 4 MiB persistent-storage ceiling and the same 128
candidates. Actual retained arrays, cached patterns, records, provenance and
Python containers are charged. No baseline is padded with unused arrays.
This measures cost at the same task size; it is not a capacity comparison at
exactly equal consumed bytes. The accounting excludes process/interpreter costs
and temporary query buffers, and reports that limitation explicitly.

Latency is for existing public search implementations: single online queries,
one numerical-library thread, identical top-k and a balanced method order.
HME also constructs decoded outputs; exact NN only returns ranked IDs/scores.
Timing therefore measures the current API cost, not an intrinsic lower bound on
HME's ranking algebra. No implementation is optimized after seeing outcomes.

There is no fitting stage or calibrator. Unmatched Gaussian queries test default
acceptance behavior, not out-of-distribution detection. Semantic embeddings,
HRR, approximate indices, other dimensions/loads, and optional runtime/salience
policies remain later evaluation stages.

## Registration and execution

The public registration commit contains this document, protocol.json,
`evaluate.py`, and `tests/test_nn_baseline.py`. Correctness tests use tiny fixtures
and seeds outside the evaluation set. Registered seeds must not run until that
commit is pushed. The evaluator refuses mismatched frozen files and existing
output directories. It records any technical failure, exact sources, dataset
hashes, per-query predictions/ranks and per-seed statistics.

```bash
OPENBLAS_NUM_THREADS=1 python experiments/nn_baseline_v1/evaluate.py \
  --registration-commit REGISTRATION_SHA \
  --output outputs/nn_baseline_v1
```

A negative result is reportable. Preserve the registration in Git history and
publish all registered cells, costs, raw observations, limitations and deviations.
