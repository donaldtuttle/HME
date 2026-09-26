# HME-REC-1: reconstruction from partial, correlated observations

Prospective specification. `protocol.json` fixes all seeds, parameters and gates.
Publish this protocol, evaluator and correctness tests before evaluation. No
registered seed may be used for development. This is a new experimental readout,
not a change to the v3.1 public engine, its Hann default, or existing reports.

## Question and primary outcome

Can a readout of HME's superposed field predict hidden coordinates of **unseen**
correlated signals more accurately than copying a nearest record or blending
nearby records, while preserving the separate identity path at acceptable cost?

For each of 30 independent seeds, store 128 complete unit-length real vectors
of dimension 32, then reconstruct 64 independent held-out vectors. Every seed
has its own random orthogonal basis. Draw `x = U_r z / sqrt(r) + 0.1 e / sqrt(d)`
and normalize each complete synthetic signal once. `z` and `e` are independent
standard Gaussian draws. Train and test draws are disjoint. Rank 4 supplies
shared structure; rank 32 is an isotropic negative control. No hidden target,
latent basis, identity label or missing coordinate is supplied to any reader.
This tests complete training records with incomplete queries, not training on
missing records. Normalization is part of the data-generating definition, not
an inference operation using hidden test coordinates.

Reveal 25%, 50% or 75% of coordinates, selected randomly or as a contiguous
cyclic block. Add independent observation noise `sigma/sqrt(d)` only to revealed
coordinates, for sigma 0, 0.1 and 0.25. The inference API receives the noisy
observations and explicit Boolean mask. Missing coordinates are NaN. Masks and
noise streams are shared across arms, with independent reproducible substreams.
The primary cell is rank 4, random mask, 50% observed, sigma 0.1. All 36 cells
per seed are reported; secondary cells cannot replace the primary.

Score only missing coordinates: per-seed NMSE is total squared reconstruction
error divided by total hidden-target energy. Retain each query's squared error,
target energy, mask and full reconstructed vectors in compressed raw records.
Primary effects are paired seed-level relative reductions `1 - field_NMSE /
baseline_NMSE`, separately against NN copying and weighted blending. Bootstrap
seeds with 20,000 draws and the fixed bootstrap seed. Practical reconstruction
benefit requires the lower endpoint of each paired 95% interval to exceed 10%.
The joint claim requires both comparisons to pass; secondary intervals are
explicitly descriptive. Report absolute NMSE as well as relative effects.

## Readout and exact-matrix control

Keep the production FFT encoding. Use explicit Hann-off, unit write gains,
zero decay, no salience, identical shared position (32,32), 64x64 complex field,
no clipping and no eviction. These are fixed experimental settings.

For a processed unit vector v, inverse-DFT separability gives:

```
P[i,j] = v[i] * conjugate(v[(-j) mod d])
C = field_patch[:, (-arange(d)) mod d] / number_of_writes
  = mean(v v*)
x_hat[M] = C[M,O] solve(C[O,O] + lambda I, y[O])
lambda = 0.01 * trace(C) / d
```

The reader obtains C **only from field bytes**, not cached payloads, patterns or
records. It keeps observations unchanged and does not renormalize predictions.
The field contains an uncentered second moment, not individual identities or a
unique arbitrary original vector. The prior is zero mean by construction.
This linear readout is newly implemented; the old `decoded_surface` is not
relabeled as recovered input. Derivation uses NumPy's documented DFT convention:
https://numpy.org/doc/stable/reference/routines.fft.html

Six arms, all with the same training observations and no fitting on test targets:

1. `nn_copy`: highest signed cosine on observed coordinates; copy its hidden values.
2. `weighted_blend`: top 8 by the same cosine; softmax weights at temperature 0.1.
3. `field_ridge`: the field-only readout above, derived afresh per query.
4. `direct_moment`: build C directly from the same normalized records, without FFT;
   use the identical regularized readout. This is a mandatory algebraic control.
5. `diagonal_field`: discard off-diagonal correlations before the same readout.
6. `zero_fill`: keep observations; predict zero for missing coordinates.

Use insertion order to break score ties. Hyperparameters are fixed, not selected
from outcomes. No amplitude fitting or oracle noise variance is given to HME.
A win over NN/blending is **not** an FFT-specific advantage if direct moments
match. Direct moments are expected to agree to numerical tolerance; their costs
are measured too. A later nonlinear or spatial design requires another protocol.

## Structural controls and identity guardrail

Check the field-to-direct matrix error <=1e-12 and reconstructed coordinate
error <=1e-10 in every cell. Ledger erasure must leave field-readout outputs
unchanged; zero field must equal zero-fill; diagonal-field must equal zero-fill.
All reconstruction calls must leave field bytes and public identity ranks intact.
Tests include complex and odd-dimensional FFT algebra, missing-coordinate leakage,
mask validation, linearity, repeatability and remote-registration failures.

Independently per seed, draw 128 raw Gaussian vectors of dimension 16, query each
with additive sigma-1 Gaussian noise, and compare the existing experimental
no-window signed HME path to raw signed cosine. Use fresh substreams unrelated
to the reconstruction data. Compute public-API predictions before and after
reconstruction, requiring exact equality and unchanged field bytes. The accuracy
guardrail requires the lower paired 95% bound (HME minus NN) above -1 percentage
point. This protects the **separate existing identity path**; it does not claim
that field-completed vectors improve identification or that the field itself
can recover artifact IDs. Report that limitation even if the guardrail passes.

## Costs and decision

At the primary cell, measure per-query reconstruction wall time, with one BLAS
thread, 8 warmups per arm, 5 repetitions of every query, and rotated arm order.
Store raw nanosecond samples. Each timed call does its own preprocessing and
returns a full reconstructed vector; no arm gets decoded-output work omitted.
Report median and p95 by seed, then medians across seeds and paired ratios.
Report each model's construction time, and common provenance construction cost.
These are host measurements, not general deployment latency claims.

Account both compact readout state and deployment bundles. NN/blending retain
vectors plus copies of the same artifact records and lineage. HME retains the
actual engine, full field, cached payloads/patterns, records and lineage. Direct
moments retain C, the same identity vectors and provenance. Deduplicate shared
objects within each bundle. Include Python object overhead and owned array data;
exclude interpreter, imported modules and temporary query workspace. Do not
present a compact field-only snapshot as the cost of an identity-capable HME.

The prespecified cost gate requires every HME bundle <=64 MiB, the median across
seeds of primary p95 <=10 ms, and median paired median-latency ratio <=5 times
weighted blending. These are provisional research budgets, not user production
requirements. Overall practical success requires reconstruction, identity and
cost gates together. Publish each gate separately, including negative outcomes.

## Publication, integrity and stopping

`--registration-commit` must be a full immutable SHA and an ancestor of HEAD.
All frozen files must match that commit. Before generating any evaluation data,
fetch the canonical GitHub origin with an explicit pruned heads refspec and
require that a fetched `refs/remotes/origin/*` branch contains the SHA. Reject
local-only commits, stale unmatched refs and another origin. Record origin,
containing refs/tips, frozen hashes and verification time. On GitHub Actions,
also retain the server-returned run ID, head SHA, created/start times and URL.
This enforces remote availability before **this run**; it cannot prove nobody
performed an undisclosed earlier private run. Do not claim otherwise.

The workflow validates correctness tests before execution. Publish registration
and results in separate commits, retaining ancestry. Complete all seeds/cells;
no early stopping, new settings, retries selected for a better result or omitted
failures. A technical failure writes a failure record and exits nonzero without
a success report. Any evaluator repair after evaluation starts must be disclosed
as a deviation; preserve the original registration and failed attempt.

Raw predictions/metrics, dataset hashes, costs, runtime versions and all summaries
are retained with SHA-256 checks. Output directories cannot be reused. Frozen
v3.1 engine/runtime/dynamics/archive bytes and previous experiments stay intact.
