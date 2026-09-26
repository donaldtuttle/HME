# HME-REC-1: partial-observation reconstruction results

Registration: `ba20ac053a3c9c3c1571992c41c5c04356ffeac4`.

30 seeds; 128 complete training records; 64 unseen queries per seed; dimension 32.
All 1,080 registered cells completed. Primary: rank 4, 50% random observations, sigma 0.1.

**Headline:** At a shared position, HME is an FFT-indexed second-moment
accumulator. Its ridge-regression readout improves on the registered copy/blend
baselines on this structured synthetic task, but ties the direct-moment readout.
Direct moments are the decisive matched-estimator baseline and are faster and
smaller here. This is not evidence of an FFT-specific reconstruction advantage.

This reviewed report adds post-evaluation interpretation only. The original
machine-generated report is preserved byte-for-byte as [REPORT_AS_RUN.md](REPORT_AS_RUN.md).
Registered sources, numerical results and raw predictions are unchanged.
Missing-coordinate normalized squared error (lower is better):

| Arm | Primary mean NMSE | Median query time (microseconds) |
|---|---:|---:|
| nn_copy | 0.170547 | 35.54 |
| weighted_blend | 0.093828 | 39.20 |
| field_ridge | 0.031211 | 60.49 |
| direct_moment | 0.031211 | 41.56 |
| diagonal_field | 1.000000 | 62.02 |
| zero_fill | 1.000000 | 9.90 |

## Prespecified contrasts and gates

Field relative error reduction versus nn_copy: 81.47% (paired 95% interval [80.27, 82.56]%).
Field relative error reduction versus weighted_blend: 66.41% (paired 95% interval [64.34, 68.38]%).

Separate identity path minus raw signed cosine: -0.182 percentage points (95% interval [-0.755, +0.365]).
Public identity predictions and field bytes were unchanged by reconstruction.

| Gate | Passed |
|---|---|
| reconstruction | True |
| identity | True |
| cost | True |
| overall | True |

## Costs

Separate the numerical representation from a full identity-capable bundle:

| Numerical storage, excluding Python object overhead | Bytes | Size |
|---|---:|---:|
| Direct 32 x 32 float64 second-moment matrix | 8192 | 8 KiB |
| Active 32 x 32 complex128 field patch (part of the grid) | 16384 | 16 KiB |
| Allocated 64 x 64 complex128 field grid | 65536 | 64 KiB |

The allocated field is **8x** the size of the real matrix it encodes in this
co-located experiment; the active patch alone is 2x. These are array data sizes,
not independent allocations to add together. The complete HME bundle below is
2,454,767 bytes (about 2.34 MiB). Its **8.48x** ratio to copying/blending includes
payload/pattern caches, records, lineage and object-layout overhead; it is not
the incremental cost of the numerical field alone or a compression result.

| Deployment bundle | Median accounted bytes |
|---|---:|
| nn_copy | 289386 |
| weighted_blend | 289386 |
| field_ridge | 2454767 |
| direct_moment | 297714 |

Median paired field/blend query-time ratio: 1.547.
Median field p95: 0.075 ms.

HME bytes include the actual field, payload/pattern caches, records and lineage.
Other bundles retain the same provenance and identity vectors. Compact-state bytes,
construction times and raw timing samples are in results.json. Transient query
workspace and interpreter/module overhead are not included. These timings are host-specific.

## Interpretation

### What the field and readout compute

At a shared position the field is an FFT-indexed **uncentered second-moment
matrix**, and the readout is ridge regression. With real, unit-norm stored
vectors, equal unit gains, no Hann taper, no decay and unclipped co-located
patches, the exact-arithmetic identities are:

```text
P_i[a,b] = x_i[a] * x_i[(-b) mod d]
C = field_patch[:, (-arange(d)) mod d] / N = sum_i(x_i x_i^T) / N
x_hat[h] = C[h,m] solve(C[m,m] + lambda I, y[m])
lambda = 0.01 * trace(C) / d
```

Here `m` denotes observed coordinates and `h` hidden coordinates. This is a
regularized linear prediction rule. It has the zero-mean Gaussian conditional-
mean form when C is treated as the prior covariance and lambda as independent
observation-noise variance. The generator normalizes Gaussian-derived signals
to unit length, so the evaluated targets are not themselves exactly Gaussian;
the experiment does not establish Bayes optimality for that normalized law.
The population mean is zero by construction; the finite-sample C is uncentered.

Direct moments and the field contain the same second-order information in this
setup. Maximum field/direct reconstructed-coordinate difference: 1.11e-14.
The low-rank design makes a second-order linear estimator a natural competitor;
copying and a fixed top-8 blend are weaker reference methods, not the strongest
linear baselines. Their large error reductions do not show superiority over
ridge, PPCA, shrinkage estimators or an equally informed direct-matrix method.

### Primary-cell ridge/noise coincidence

Unit-norm inputs give `trace(C) = 1` in exact arithmetic. Therefore the registered
ridge is `0.01/d`. Per-observed-coordinate noise variance is `sigma^2/d`.
At the primary `sigma = 0.1`, **lambda equals that noise variance**, up to floating-
point roundoff. Both settings were fixed before the official evaluation; this
coincidence is not a post-hoc change, but it matters to interpretation.
At sigma 0 and 0.25 the same fixed ridge no longer matches observation noise.
The experiment did not establish optimal regularization across noise levels.

The reviewer supplied a separate, post-hoc ten-seed comparison of noise-aware
ridge and rank-4 PPCA, reporting improvements outside the primary cell. Those
numbers have not been independently rerun here and are not added to the
registered results. They motivate stronger, separately registered readout
baselines. Known true noise variance or latent rank must be disclosed as oracle
information, or made equally available to every compared method.

### Isotropic control: covariance-estimation overfitting

In the matched rank-32, 50%-random-observed, sigma-0.1 control, field NMSE is
1.136437, while zero-fill is exactly 1.0. The explanation is not just a lack of
shared low-rank structure: estimating off-diagonal moments from a finite sample
introduces spurious correlations that the conditional predictor then uses.
This is covariance-estimation overfitting. A 32 x 32 symmetric matrix has 528
distinct entries (with its trace constrained here), estimated from 128 vectors;
that count is context, not a proof of singularity or an independent sample-size
criterion. In particular, 128 exceeds dimension 32.

For the isotropic, sign-symmetric population, the conditional mean of hidden
coordinates given the noisy visible coordinates is zero. For an independently
trained predictor f, the population squared-error decomposition is:

```text
E ||x_h - f(y_m)||^2 = E ||x_h||^2 + E ||f(y_m)||^2
```

Thus a nonzero spurious prediction adds population risk above zero-fill.
Shrinkage toward a diagonal or isotropic target can suppress that excess risk.
It does **not** guarantee held-out NMSE <= 1 for every fitted estimator or test
sample. Fully diagonal C makes this zero-mean reader predict zero on hidden
coordinates, giving the registered 1.0 control exactly. Ledoit-Wolf is a useful
future baseline, not a tested result here; its standard target is a scaled
identity matrix, rather than an arbitrary empirical diagonal.

### Scope

No claim about arbitrary images, semantic memory, missing training records,
nonlinear data, field-only identity recovery or production deployment follows.
The identity guardrail protects the existing separate experimental signed path,
not a new policy that identifies records after field completion. Engine source
is unchanged. Distributed or overlapping writes require a new derivation and
information-matched spatial baselines, not extrapolation from co-location.

Method references: [registered algebra and estimator](PROTOCOL.md),
[NumPy DFT convention](https://numpy.org/doc/stable/reference/routines.fft.html),
[Ledoit-Wolf estimator and target](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html),
and [Tipping and Bishop's PPCA / mixture-of-PPCA papers](https://www.miketipping.com/papers.htm).

## Provenance and reproduction

Fresh canonical-origin fetch and containing refs were checked before data generation.
The registration record includes source hashes and any GitHub server run timestamps.
This establishes public availability before this run, not absence of undisclosed private runs.
No protocol deviations. Retained raw_records.jsonl.gz contains all query predictions,
targets, observations and losses. results.json contains hashes, every cell, costs and guards.

```bash
OPENBLAS_NUM_THREADS=1 python experiments/reconstruction_v1/evaluate.py \
  --registration-commit ba20ac053a3c9c3c1571992c41c5c04356ffeac4 \
  --output outputs/reconstruction_v1_reproduction
```

Use a fresh output directory and a full clone with network access to canonical origin.

### Review amendment and byte-level reproduction

This prose amendment follows the independent review; it does not rerun or
retune HME-REC-1. `REPORT_AS_RUN.md` retains the original evaluator-generated
report from result commit `0265e83533b960076f4d2f97fa48f325edd0d232` (SHA-256
`2a4d65f8f41e9170de09a5ebc7da31ca7a5b5d73ae8319bbde78b1e6bef0d955`).
The frozen evaluator still emits the original report format, not this amendment;
new runs also remeasure host-dependent timings. Compare numerical predictions
and metrics rather than expecting an amended prose file or new timings to be
byte-identical. `RESULTS.sha256` now covers both reports and the three unchanged
result/registration/raw-data files. The original four-file manifest remains in
the original result commit. No registered source, seed, gate or observation changed.
