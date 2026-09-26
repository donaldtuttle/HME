# HME-REC-1: partial-observation reconstruction results

Registration: `ba20ac053a3c9c3c1571992c41c5c04356ffeac4`.

30 seeds; 128 complete training records; 64 unseen queries per seed; dimension 32.
All 1,080 registered cells completed. Primary: rank 4, 50% random observations, sigma 0.1.
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

The direct second-moment readout is algebraically equivalent in this co-located setup.
Maximum field/direct reconstructed-coordinate difference: 1.11e-14.
A reconstruction improvement over copying/blending is a useful field operation,
not evidence of an FFT-specific advantage over the direct-matrix control.
The low-rank generative design favors learning shared linear structure; isotropic
and block-mask controls, all noise levels and all observation fractions are reported.
No claim about arbitrary images, semantic memory, missing training records, nonlinear
data, field-only identity recovery, or production deployment follows from this study.
The identity guardrail protects the existing separate experimental signed path,
not a new policy that identifies records after field completion. Engine source is unchanged.

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
