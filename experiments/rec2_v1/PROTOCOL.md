# HME-REC-2: aligned banks and full-shift pooling

Prospective specification. `protocol.json` fixes the seeds, sizes, tolerances and gates.
Publish this protocol, the evaluator and the development tests before generating
evaluation data. Seed 7 is the only development seed. No registered seed may be
used for development. This does not change `hme_engine.py`, its Hann default,
the v3.1 pins, or any earlier report.

This is one registered study with one primary comparison. It is not a claim that
the field is more accurate than a matrix.

## Primary comparison (REC-2A)

Question: when disjoint aligned blocks are written with the unchanged engine,
does a readout of those blocks match the same readout of ordinary per-block
second-moment matrices, to the tolerances below?

For each of 30 seeds, draw 4 separate blocks. Each block gets 32 training
vectors and 16 held-out vectors, all length 8. A block has its own random
orthogonal basis of rank 2. Draw `x = U z / sqrt(2) + 0.1 e / sqrt(d)`, then
normalize each vector once. Training and test draws are disjoint. The rank and
the noise scale are part of the generator. They are not hidden from the
descriptive PPCA arm, and that arm is labeled an oracle for that reason.

Place the blocks on one grid so they touch but do not share a cell. Block k
occupies rows `8k .. 8k+7` and columns `0 .. 7`. The engine is called with its
existing writer: Hann off, unit strength, zero decay, salience off, pattern
normalization left on, no clipping and no eviction. The grid is 32 by 32.
Every arm is told the true block number. That is matched routing, not a test of
discovering which block a vector came from.

Reveal a random 50% of coordinates. Add noise `sigma/sqrt(d)` on the revealed
coordinates only, for sigma 0, 0.1 and 0.25. The primary cell is sigma 0.1.
Missing coordinates are the only ones scored. The reader keeps the revealed
values as they are and does not rescale a prediction by the hidden answer.

Both primary arms use the same ridge, `lambda = 0.01 * trace(C) / d`, and the
same observed values. `field_ridge` builds each block's matrix only from field
bytes. `direct_moment` builds `X^T X / n` from the same normalized training
vectors. No ledger, payload cache or pattern cache is used by the field reader.

The primary effect is the largest absolute gap between those two arms.
The identity gate passes only if, on every seed and every sigma, the matrices
differ by at most 1e-10 and the reconstructed coordinates differ by at most 1e-8.
A larger gap is a failure of bookkeeping, not an accuracy win. There is no
accuracy-superiority claim in the primary comparison.

## Required shift control (REC-2B)

This control uses a new writer that lives only in the evaluator. It does not
call the shipped engine and it does not change the shipped engine. For each
seed, draw 32 fresh length-16 real vectors from a standard normal generator.
Do not normalize them per window. For every shift `a` from -15 to 15, place
the zero-padded shifted vector's outer product into a real 16 by 16 patch.
Divide the sum by `32 * 16`.

The comparison is the ordinary biased autocorrelation matrix of the same
records, using the lag sum `M[m,n] = sum_k x[k] x[k+(n-m)] / (N d)` with x
zero outside the record. The control passes only if every seed agrees to 1e-10.
Also record that the unnormalized sum is Toeplitz and that its eigenvalues are
at least -1e-8. This checks the new writer. It does not replace the primary
comparison.

## Descriptive competitor, not a gate

On the same primary cell, fit a rank-2 PPCA model separately on each block's
training vectors. The rank is the generator's rank and is an oracle. The noise
level is the average of the discarded eigenvalues of the training covariance
divided by the number of training vectors. Score missing coordinates the same
way. Publish the paired difference against `direct_moment` with a 20,000-draw
bootstrap interval. That interval does not pass or fail the study.

## Identity path and cost

Separately on each seed, store 128 raw Gaussian vectors of length 16 with the
existing no-window signed path, query them with fresh sigma-1 noise, and
compare with raw signed cosine. Reconstruction must not change those identity
answers or the field bytes. The guardrail passes if the lower end of the paired
95% interval (signed path minus cosine, in percentage points) is above -1.
This protects the old identity path. It does not say the field can name records.

At the primary cell, time `field_ridge` and `direct_moment` with one BLAS
thread, 8 warmups, 5 repeats, and rotating order. Account the whole engine,
including the grid, cached payloads, records and lineage, against the direct
matrices plus the same provenance. The cost gate passes if every field bundle
is at most 64 MiB and the median across seeds of the field p95 is at most 20 ms.
These are research ceilings, not a claim that the field is the smaller or
faster store. Byte and time ratios are reported with intervals and are not gates.

## What a pass means

Overall success requires the primary identity gate, the shift control, the
identity-path guardrail and the cost ceilings together. Publish each one even
if another fails. A pass means the aligned writer matches ordinary matrices
inside the tolerances, the experimental shift writer matches the biased
autocorrelation, and the measured bundles fit the ceilings. It does not mean
the field beat PPCA, recovered labels, or improved on storing the matrices
directly.

## Publication and stopping

`--registration-commit` must be the full SHA of this protocol's commit and an
ancestor of HEAD. Frozen files must match that commit. Before any evaluation
draw, fetch `https://github.com/donaldtuttle/HME` and require a fetched origin
branch to contain the SHA. Reject a local-only commit. Record the origin, the
containing refs, the file hashes and the time. On GitHub Actions, also keep the
server run id, head SHA, created time and URL. This shows the protocol was
public before this run. It does not prove there was no earlier private run.

Run every seed and every sigma. Do not stop early, retune, retry for a better
number, or drop a failure. A crash writes `FAILURE.json` and does not count as
a success report. A repair after evaluation has started must be labeled a
deviation. Raw predictions, hashes, costs and versions stay with the report.
Use a fresh output directory. Leave the pinned engine bytes alone.
