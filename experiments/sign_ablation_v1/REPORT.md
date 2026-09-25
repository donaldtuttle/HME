# HME-NN-2A: sign ablation with retained field bias

Registration: [`ca25cc3`](https://github.com/donaldtuttle/HME/commit/ca25cc3d89fae7a2f033f46436afe8b6ee183f24). The protocol, variant, evaluator and correctness fixtures were public before evaluation.

Execution: 2026-09-25T03:13:52.106649+00:00 through 2026-09-25T03:16:58.945828+00:00. All 30 registered seeds completed; protocol deviations: 0.

## Primary result

**Equivalence within plus or minus one percentage point: not established.** Noninferiority within one point: **supported**.

The primary condition is native query preprocessing, Gaussian noise sigma 1.0, 128 items of dimension 16 at a shared position. Accuracy is averaged across thirty independent seeds.

| Arm | Top-1 accuracy, percent [95% seed-bootstrap interval] |
|---|---:|
| Current HME (absolute) | 44.01 [42.24, 45.83] |
| Experimental HME (signed) | 53.80 [52.21, 55.44] |
| Signed cosine NN | 52.97 [51.43, 54.61] |

| Paired contrast | Difference, percentage points [95% interval] |
|---|---:|
| Experimental HME (signed) minus Current HME (absolute) | 9.79 [8.85, 10.73] |
| Current HME (absolute) minus Signed cosine NN | -8.96 [-10.26, -7.66] |
| Experimental HME (signed) minus Signed cosine NN | 0.83 [-0.05, 1.69] |

The primary signed-HME-minus-NN **90% interval** is **[0.08, 1.56] percentage points**. Equivalence requires this entire interval to lie strictly inside [-1, +1] points; noninferiority requires its lower endpoint to exceed -1 point. A nonsignificant difference or an interval overlapping zero does not establish equivalence.

A deficit exceeding the one-point margin is not established. Lower mean signed-HME accuracy under the 95% effect interval is not established; higher mean accuracy is not established.

These decisions use the preregistered approximate percentile-bootstrap procedure: 50,000 resamples of thirty paired seed-level metrics. Queries sharing a field are not treated as independent replicates. No guaranteed power or exact finite-sample type-I error control is claimed. The sample size and one-point margin were not changed.

The sign intervention removes the observed primary mean deficit, but the registered equivalence hypothesis remains unresolved: the upper endpoint exceeds the positive margin. The result permits a benefit larger than one point; it does not establish such a benefit. It also does not establish superiority under the separate registered 95% effect-interval criterion.

The secondary symmetric-preprocessing, sigma 1.0 condition favors NN: signed HME minus NN is -1.33 [-2.01, -0.70] percentage points (descriptive 95% interval). The primary outcome should not be generalized to every preprocessing condition.

## What changed

The experimental variant replaces only `abs(vdot(payload, query))` with `real(vdot(payload, query))`. It retains the field bias, 0.38/0.42/0.20 weights, clipping, thresholds, preprocessing, decoded outputs and storage behavior. The generated source is pinned and hashed. The public package still uses the original default engine; this report does not promote the experimental variant.

Signed NN retains copies of the same processed vectors, artifact records and lineage. Every arm has identical queries and side information and a common 4 MiB maximum persistent-storage budget. All arms fit. This tests the sign intervention with the existing prior retained; it does not test a query-dependent field readout.

## All registered conditions

Only native sigma 1.0 has a confirmatory equivalence decision. Other cells and contrasts are descriptive, with no multiplicity correction or substitution for the primary. Zero-width intervals describe these observations, not population certainty.

### Top-1 accuracy (%)

| Query mode | Noise sigma | Current HME | Signed HME | Signed NN |
|---|---:|---:|---:|---:|
| native | 0 | 100.00 [100.00, 100.00] | 100.00 [100.00, 100.00] | 100.00 [100.00, 100.00] |
| symmetric | 0 | 100.00 [100.00, 100.00] | 100.00 [100.00, 100.00] | 100.00 [100.00, 100.00] |
| native | 0.25 | 99.90 [99.77, 100.00] | 99.92 [99.82, 100.00] | 99.90 [99.77, 100.00] |
| symmetric | 0.25 | 99.04 [98.70, 99.35] | 99.43 [99.19, 99.64] | 99.71 [99.53, 99.87] |
| native | 0.5 | 91.69 [90.83, 92.55] | 94.56 [93.93, 95.13] | 94.30 [93.57, 95.00] |
| symmetric | 0.5 | 79.79 [78.67, 80.96] | 85.65 [84.56, 86.74] | 87.66 [86.64, 88.65] |
| native | 1 | 44.01 [42.24, 45.83] | 53.80 [52.21, 55.44] | 52.97 [51.43, 54.61] |
| symmetric | 1 | 30.78 [29.43, 32.16] | 39.69 [38.46, 40.91] | 41.02 [39.79, 42.27] |

### Top-5 accuracy (%)

| Query mode | Noise sigma | Current HME | Signed HME | Signed NN |
|---|---:|---:|---:|---:|
| native | 0 | 100.00 [100.00, 100.00] | 100.00 [100.00, 100.00] | 100.00 [100.00, 100.00] |
| symmetric | 0 | 100.00 [100.00, 100.00] | 100.00 [100.00, 100.00] | 100.00 [100.00, 100.00] |
| native | 0.25 | 100.00 [100.00, 100.00] | 100.00 [100.00, 100.00] | 100.00 [100.00, 100.00] |
| symmetric | 0.25 | 99.97 [99.92, 100.00] | 99.97 [99.92, 100.00] | 99.97 [99.92, 100.00] |
| native | 0.5 | 98.78 [98.54, 99.01] | 99.35 [99.09, 99.58] | 99.40 [99.14, 99.64] |
| symmetric | 0.5 | 95.57 [94.90, 96.22] | 97.66 [97.14, 98.15] | 98.10 [97.73, 98.46] |
| native | 1 | 72.92 [71.59, 74.22] | 81.72 [80.60, 82.86] | 82.06 [80.89, 83.26] |
| symmetric | 1 | 58.88 [57.50, 60.23] | 70.08 [68.65, 71.48] | 71.35 [69.92, 72.79] |

### Mean reciprocal rank

| Query mode | Noise sigma | Current HME | Signed HME | Signed NN |
|---|---:|---:|---:|---:|
| native | 0 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| symmetric | 0 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| native | 0.25 | 0.999 [0.999, 1.000] | 1.000 [0.999, 1.000] | 0.999 [0.999, 1.000] |
| symmetric | 0.25 | 0.995 [0.993, 0.996] | 0.997 [0.995, 0.998] | 0.998 [0.997, 0.999] |
| native | 0.5 | 0.949 [0.944, 0.954] | 0.968 [0.964, 0.971] | 0.967 [0.963, 0.971] |
| symmetric | 0.5 | 0.868 [0.860, 0.876] | 0.909 [0.902, 0.916] | 0.923 [0.916, 0.929] |
| native | 1 | 0.573 [0.560, 0.587] | 0.663 [0.651, 0.674] | 0.659 [0.647, 0.671] |
| symmetric | 1 | 0.442 [0.430, 0.454] | 0.536 [0.525, 0.547] | 0.549 [0.538, 0.561] |

## Primary observations by seed

| Seed | Current HME correct / 128 | Signed HME correct / 128 | Signed NN correct / 128 |
|---:|---:|---:|---:|
| 401001 | 50 | 63 | 58 |
| 401002 | 61 | 71 | 68 |
| 401003 | 57 | 74 | 69 |
| 401004 | 59 | 71 | 72 |
| 401005 | 64 | 81 | 80 |
| 401006 | 47 | 62 | 66 |
| 401007 | 50 | 62 | 59 |
| 401008 | 66 | 76 | 73 |
| 401009 | 48 | 63 | 57 |
| 401010 | 58 | 70 | 68 |
| 401011 | 56 | 67 | 64 |
| 401012 | 54 | 69 | 68 |
| 401013 | 57 | 67 | 61 |
| 401014 | 52 | 63 | 65 |
| 401015 | 62 | 71 | 65 |
| 401016 | 50 | 59 | 65 |
| 401017 | 64 | 69 | 68 |
| 401018 | 45 | 63 | 67 |
| 401019 | 64 | 77 | 79 |
| 401020 | 50 | 63 | 64 |
| 401021 | 52 | 61 | 64 |
| 401022 | 59 | 75 | 73 |
| 401023 | 52 | 70 | 67 |
| 401024 | 54 | 66 | 65 |
| 401025 | 59 | 67 | 66 |
| 401026 | 51 | 67 | 70 |
| 401027 | 62 | 72 | 69 |
| 401028 | 53 | 69 | 69 |
| 401029 | 61 | 77 | 75 |
| 401030 | 73 | 81 | 80 |

## Newly measured costs

| Arm | Median persistent bytes | Maximum persistent bytes | Numeric array bytes | Median API query (ms) | Median seed p95 (ms) | Median paired latency / NN |
|---|---:|---:|---:|---:|---:|---:|
| Current HME (absolute) | 834,148 | 834,572 | 622,592 | 2.4700 | 3.0365 | 69.8 |
| Experimental HME (signed) | 834,232 | 834,580 | 622,592 | 2.4954 | 2.9904 | 70.4 |
| Signed cosine NN | 186,230 | 186,346 | 33,792 | 0.0356 | 0.0541 | 1.0 |

Storage is recursive CPython object/owned-array accounting, including field, cached patterns, records and lineage, with aliases counted once. Interpreter/shared code, allocator overhead and temporary query buffers are excluded. This is a common maximum budget at equal task size, not an equal-consumed-byte capacity frontier.

Latency uses 32 primary-condition queries per seed, four warmups per arm, three repetitions, rotating arm order, top-k 5, and one numerical-library thread. Both HME variants also construct decoded outputs; NN returns rankings/scores. Shared-host timings describe these public implementations, not intrinsic algorithmic lower bounds. The sign variant retains the original execution path, including its per-candidate operations.

## Unmatched-query acceptance

| Arm | Accepted / total, both query modes |
|---|---:|
| Current HME (absolute) | 960 / 960 |
| Experimental HME (signed) | 960 / 960 |
| Signed cosine NN | 960 / 960 |

These are fresh Gaussian vectors with no designated stored target. Acceptance at default policies is not calibrated correctness or out-of-distribution detection. Raw scores are not used as probabilities.

## Scope and reproduction

This is a new, independent sign-ablation experiment on synthetic vectors at one load and dimension. It does not replace the [HME-NN-1 evidence](../nn_baseline_v1/REPORT.md), test candidate-specific field retrieval or change encoding. [Stage 2 requirements](../../docs/FIELD_RETRIEVAL_DESIGN.md) explain the separate addressing, overlap, polarity and cost controls still needed.

Environment: Python 3.12.14, NumPy 2.5.3. Exact source/generated-module hashes, data hashes, platform and numerical-library configuration are in the aggregate report.

- [Frozen protocol](PROTOCOL.md) and [machine-readable specification](protocol.json)
- [Aggregate results and provenance](results/results.json)
- [Per-seed predictions, target ranks, timings and byte accounting](results/)

```bash
python experiments/sign_ablation_v1/evaluate.py \
  --registration-commit ca25cc3d89fae7a2f033f46436afe8b6ee183f24 \
  --output outputs/sign_ablation_v1_replication
```

The output directory must be new. Sources are checked against the registration before execution. Numerical environments can affect floating-point details; timings and object sizes can vary. Run `python experiments/sign_ablation_v1/render_report.py` to regenerate this document from the saved observations without evaluating again.
