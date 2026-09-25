# HME-NN-2A: sign ablation with retained field bias

The [machine-readable protocol](protocol.json) fixes the complete experiment.
This is Stage 1 of the proposed follow-up, with three arms:

- **HME_abs:** the current default engine.
- **HME_signed:** change only absolute to signed item/query similarity; keep the
  existing field bias, weights, clipping, threshold and all API behavior.
- **Signed NN:** exact signed cosine over identical processed vectors, retaining
  the same artifact records and lineage.

The signed engine is an experimental module generated from the pinned source by
one guarded expression replacement. The generated source is hashed. No change
is made to the package's default engine or to HME-NN-1's frozen files.

## Primary question and decision

At native query preprocessing and Gaussian noise sigma 1.0, is the difference
`HME_signed - signed NN` in mean top-1 accuracy practically equivalent to zero?

The equivalence margin is **plus or minus one percentage point**, fixed before
execution. Equivalence requires the paired-seed **90% bootstrap interval** to lie
strictly inside `(-0.01, +0.01)`. Noninferiority within one point is a separate
reported criterion: the lower endpoint must exceed `-0.01`. It does not assert
HME is at least as accurate without that tolerance. An interval overlapping
zero is not sufficient for equivalence; failing equivalence does not by itself
establish inferiority. Report the 95% effect interval and deficits exceeding the
margin separately.

This is an approximate percentile-bootstrap interval procedure. It does not
claim exact type-I error control or guaranteed power. Thirty new seeds are fixed
in advance; an inconclusive result does not authorize adding seeds or widening
the margin. One confirmatory condition is designated; other cells are descriptive.

## Design and controls

Reuse HME-NN-1's 128 Gaussian items, dimension 16, 64-by-64 field, shared position,
write strength 0.1, four noise levels and two preprocessing modes. Noise and
corpora are paired across arms. Salience stays off. No fitting or tuning occurs.
The retained field term is allowed to alter ranks; the earlier arithmetic
breakdown does not imply the same field effect after changing the query score.

Every arm has the same 4 MiB maximum persistent-storage allowance and the same
provenance information. Actual retained bytes and current API latency are
measured again, with their accounting and output-contract limitations reported.
No numerical cost multiplier is imported from HME-NN-1.

Correctness fixtures use small arrays and other seeds. They check the generated
source differs in exactly the registered expression, writes produce identical
states, and scores agree with independent signed/absolute calculations.

## Execution

Publish this protocol, its evaluator, variant and fixtures before running any of
the thirty registered seeds. Preserve that public commit and pass its full SHA:

```bash
python experiments/sign_ablation_v1/evaluate.py \
  --registration-commit REGISTRATION_SHA \
  --output outputs/sign_ablation_v1
```

The output directory must be new. Frozen sources are verified before execution.
Publish all raw observations, intervals, costs, failures and deviations.
Candidate-specific field retrieval and polarity-preserving encoding require
separate protocols; they are not part of this sign-only intervention.
