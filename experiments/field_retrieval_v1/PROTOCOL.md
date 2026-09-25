# HME-NN-2B: candidate-specific field retrieval

The [machine-readable protocol](protocol.json) is authoritative. Stage 2 keeps
HME's pinned encoder/writer and introduces a query-dependent, candidate-specific
field-patch readout. It is an experimental retrieval implementation, not a change
to the default engine or to the previous frozen experiments.

## Primary comparison

Thirty new seeds; 128 Gaussian items of dimension 16; 16-by-16 patches in a fixed
256-by-256 field. Content-independent positions form an 8-by-16 grid. Spacings
16, 12, 8, 4 and 0 give adjacent horizontal/vertical pairwise overlap fractions
0%, 25%, 50%, 75% and 100%. The last case puts every item at a shared position.
No patch is clipped. Every query scans all candidates without a target address.

The sole primary condition is **spacing 8, native query preprocessing, noise
sigma 1.0**. The hybrid must beat signed NN by more than **two percentage points**
at the lower endpoint of the paired-seed 95% bootstrap interval. All arms must
fit the same 4 MiB persistent-storage cap and all correctness gates must pass.
An upper interval endpoint below zero supports a negative accuracy result.
Other outcomes do not establish the registered practical gain. Costs are reported
separately; an accuracy gain does not automatically justify its cost.

## Arms and representation

- Signed and absolute exact NN use identical processed stored vectors.
- Field-only compares the encoded query with each normalized field patch using
  magnitude of the complex Frobenius inner product; a position-to-ID map attaches
  identity. It retains no original item-vector or per-item-pattern cache.
- Hybrid uses `0.42 * signed_cosine + 0.20 * field_score`, without clipping,
  distance scores, salience, fitting or rejection. It retains vectors and field.
- Permuted hybrid preserves signed vectors but deranges field-score-to-candidate
  association, checking whether a gain requires the correct association.

All arms retain the same artifact records, lineage and positions. Query and
readout live in the same 2D pattern space. Stored vectors use HME's Hann window;
native queries are normalized raw vectors, while symmetric queries are windowed
once. Pattern construction introduces no second window and no semantic decoder.

These search snapshots discard unused source-writer caches and return only
indices and scores. Retained costs, discarded source-state costs and limitations
are explicit. A full candidate patch cache is optional and charged when present.

## Tests that must hold

At zero overlap, isolated pattern correlation equals absolute cosine squared.
Field-only must reproduce absolute NN. The hybrid score is then
`0.42*c + 0.20*c*c`, whose derivative stays positive on [-1,1]; it must reproduce
signed NN. This is a correctness control, not an opportunity to claim a win.

At a shared position, field scores are identical for every candidate. Cancel the
common offset and positive scaling algebraically so hybrid rankings match signed
NN exactly. Field-only ties yield 1/128 accuracy across balanced target queries.
A zero-field hybrid must also match signed NN. Check cached/uncached agreement.

A separately generated balanced antipodal stress set pairs each query with its
exact negation, so the current encoder produces identical query patterns.
Field-only cannot identify more than one member per pair: a 50% ceiling for this
explicit test, not for arbitrary corpora. Run it at noise 0 and 1 in every layout.

Known isolated contributions provide per-item reconstruction-error diagnostics.
They are not target-only retrieval competitors constructed using the answer.
The absolute-NN arm supplies the equivalent isolated-pattern ranking reference.

## Measurements and stopping

Sweep noise 0, 0.25, 0.5 and 1, both query preprocessing modes and all layouts.
Report top-1, top-5, MRR, unmatched-query acceptance, paired intervals, reconstruction
errors, cached/uncached storage and online latency, cache construction and cache
discard costs. All comparisons beyond the primary are descriptive.

Publish this protocol, scorer, evaluator and correctness tests before evaluation.
Freeze 30 seeds and 20,000 paired bootstrap resamples. Run all conditions once;
retain technical failures and require a public amendment before a full rerun.
No encoder change is included. A failed primary practical-gain claim does not
trigger Stage 3 automatically.

```bash
python experiments/field_retrieval_v1/evaluate.py \
  --registration-commit REGISTRATION_SHA \
  --output outputs/field_retrieval_v1
```

The output directory must be new; frozen source bytes are checked first.
