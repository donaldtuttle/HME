# HME-NN-3: raw-vector and Hann-window results

Protocol registration: `8a3f9420d74424d9bd4490292e60d1bc4adeee3c`.
Evaluator registration: `7ef2789f2ce58ab67e2778a9c1fefb26f99b982d`.

Thirty fixed seeds, 128 Gaussian items, dimension 16, one shared position.
Cells are mean top-1 accuracy (%). Original vectors are not normalized before noise.

| Arm | sigma 0 | sigma .25 | sigma .5 | sigma 1 |
|---|---:|---:|---:|---:|
| raw_signed_nn | 100.00 | 100.00 | 99.43 | 74.11 |
| raw_absolute_nn | 100.00 | 100.00 | 99.17 | 66.07 |
| processed_signed_nn | 99.97 | 99.92 | 94.74 | 51.30 |
| processed_symmetric_nn | 100.00 | 99.74 | 87.68 | 39.40 |
| hme_default | 100.00 | 99.84 | 92.14 | 42.21 |
| hme_symmetric | 100.00 | 99.14 | 80.36 | 28.78 |
| hme_no_window | 100.00 | 100.00 | 99.01 | 65.65 |
| hme_no_window_field_erased | 100.00 | 100.00 | 99.17 | 66.07 |
| hme_no_window_signed | 100.00 | 100.00 | 99.32 | 73.93 |

## Primary and prespecified descriptive contrasts

Differences are percentage points, not correct-item counts.

| Contrast at sigma 1 | Mean difference | Paired 95% interval |
|---|---:|---:|
| hme_default - raw_signed_nn | -31.90 | [-33.26, -30.44] |
| hme_no_window - hme_default | +23.44 | [+21.82, +24.97] |
| hme_symmetric - hme_default | -13.44 | [-14.97, -11.93] |
| processed_signed_nn - raw_signed_nn | -22.81 | [-23.91, -21.61] |
| hme_no_window - raw_signed_nn | -8.46 | [-9.32, -7.58] |
| hme_no_window_signed - raw_signed_nn | -0.18 | [-0.57, +0.21] |
| raw_absolute_nn - raw_signed_nn | -8.05 | [-8.72, -7.37] |
| hme_no_window - hme_no_window_field_erased | -0.42 | [-1.12, +0.26] |

No-window gap reduction at sigma 1: 73.5% (descriptive ratio, not causal attribution).

## Interpretation and boundaries

Raw-input NN and matched-processed NN answer different questions. The latter
remains the registered HME-NN-1 baseline; its old report is not overwritten.
The no-window control separates tapering from the sign and field terms.
Symmetric tapering is a separate condition; it does not restore coordinates
discarded or attenuated by the taper. Secondary contrasts are descriptive.
No default-engine change, field retrieval advantage, equivalence, calibrated
confidence, semantic-memory benefit, or speed/storage claim follows from this study.

The evaluator caches query-independent components of the frozen ranker.
All registered cells pass full-API score/order probes for each HME variant
and symmetric queries; development tests compare every score and rank on
small fixtures. The field-erased ranking equals absolute cosine on every
evaluated query. Ledger-erased engines return no identity hits with fields preserved.
All 120 registered seed/noise cells completed. No protocol deviations.

Raw predictions, counts, dataset/source hashes, runtime versions, and all
secondary intervals are in [results.json](results.json).

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 python experiments/raw_vector_baseline_v1/evaluate.py \
  --registration-commit 7ef2789f2ce58ab67e2778a9c1fefb26f99b982d \
  --output outputs/raw_vector_baseline_v1
```

Use a fresh output directory. The evaluator rejects changed frozen sources
and records technical failures rather than publishing a partial success.
