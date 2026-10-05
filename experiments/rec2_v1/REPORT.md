# HME-REC-2: aligned banks and full-shift pooling

Registration: `d88484a7e3564dc7b0e0e1106dcfe1180713bcde`.

30 seeds. Four disjoint length-8 blocks. 32 training vectors and 16 held-out
vectors per block. Primary cell: random 50% observed, sigma 0.1.
Every arm was given the true block number. This is matched routing.

The primary comparison is whether the unchanged engine matches ordinary
per-block matrices. It is not a contest the field can win on accuracy.

| Check | Result |
|---|---|
| Matrices agree within 1e-10 | True |
| Reconstructions agree within 1e-8 | True |
| Shift writer matches biased autocorrelation within 1e-10 | True |
| Old identity path stays within 1 point | True |
| Field bundle under 64 MiB and p95 under 20 ms | True |
| Overall | True |

Worst matrix gap: 1.67e-16.
Worst reconstructed-coordinate gap: 1.07e-14.
Worst biased-autocorrelation gap: 1.11e-15.

Primary missing-coordinate error, lower is better. Field and direct should match.
PPCA uses the true rank and is descriptive only.

| Arm | Primary mean NMSE |
|---|---:|
| field_ridge | 0.145563 |
| direct_moment | 0.145563 |
| oracle_ppca | 0.142131 |

Oracle PPCA minus direct NMSE: -0.003432 (95% interval [-0.010950, 0.004816]). Not a gate.
Signed identity path minus raw cosine: -0.443 percentage points (95% interval [-0.990, +0.078]).
Median field query p95: 0.086 ms.
Field/direct median-time ratio: 1.000 (95% interval [1.000, 1.001]).
Field/direct object-byte ratio: 108.745 (95% interval [108.720, 108.770]).

| Store | Median object bytes |
|---|---:|
| field bundle | 287938 |
| direct matrices | 2648 |

Allocated field grid: 16384 bytes.
Active complex patches: 4096 bytes.
Direct matrix arrays: 2048 bytes.

A pass means the bookkeeping matches and the bundles fit the ceilings.
It does not mean the field is more accurate, smaller, or faster than storing
the matrices, and it does not say anything about unlabeled routing.
The shift writer is experimental code in this study, not a change to the engine.

No protocol deviations. Raw predictions are in raw_records.jsonl.gz.
Fresh canonical-origin visibility was checked before the draws.
That shows this protocol was public before this run, not that no private run existed.

```bash
OPENBLAS_NUM_THREADS=1 python experiments/rec2_v1/evaluate.py \
  --registration-commit d88484a7e3564dc7b0e0e1106dcfe1180713bcde \
  --output outputs/rec2_v1_reproduction
```
