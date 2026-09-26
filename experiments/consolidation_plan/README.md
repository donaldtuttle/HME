# From record store to consolidating memory

Status: DESIGN, not a preregistration. No REC-3, SAL-1, HOLO-1 or CONT-1 evaluation
seeds, outcomes or success claims are published by this change. Step 0 provides
[an opt-in field-only adapter](../../docs/CONSOLIDATION.md) and invariant tests.
It does not alter REC-1/REC-2 evidence, frozen modules, or the v3.1.0 tag.

Goal: preserve useful consequences of experiences at a bounded retained-state
budget, including important exceptions and measured degradation under damage.
A fixed-size moment summary is a lossy statistical compressor, not an injective
encoding of arbitrarily many experiences. Each additional write has constant
retained-state cost, but update time, interference, finite precision and estimation
quality still matter. Repeated writes are not automatically independent evidence.

## Order and publication

Step 0 -> SAL-1 first; HOLO-1 can be developed independently; REC-3 then assesses
quality per actual byte; CONT-1 comes after a concrete task/representation contract.
No background or parallel study has been launched by this design.

For each performance study publish its complete protocol, code and tests before
running evaluation seeds. Use development fixtures and disjoint validation/evaluation
seeds. Freeze the primary cell, budgets, baselines, meaningful benefit margin,
uncertainty estimates, stopping/failure rules and all decoding/repair policies.
Require a fresh canonical-origin fetch and remote containment before generating
evaluation data, retain server provenance and source/runtime hashes, and publish
all registered cells including failures. This design is not that registration.
Software invariant tests in Step 0 are not claims of prospective efficacy testing.

## SAL-1: weighting is not automatically correction

A [SAL-1 development prototype and draft protocol](../salience_v1/PROTOCOL_DRAFT.md)
now implement a bounded surprise-gated exception store with field, direct-moment
and forgetting-RLS backends. It includes matched hybrid controls, scoped revision
rules and measured byte caps. It is NOT a preregistration or an efficacy result.

Current positive-gain updates retain a weighted second moment. The mandatory
matched control is a direct C with the identical gain, decay, normalizer and
readout; they are mathematically equal in the aligned setup. Give every method
the same importance flags and the same budget for interpreting them.

Distinguish three tests before choosing a primary one:

1. Weight survival: retained influence after routine writes. This is a known
   recurrence, not a semantic success. With no decay, one gain-g correction and
   N unit-gain routine writes has mass share g/(N+g). Merely setting g>N must not
   count as a learned-memory breakthrough.
2. Scoped correction: a cue/outcome representation in which an updated association
   is distinguishable from the old one. Assess both correcting the relevant cue
   and preserving unrelated associations. Encode context/outcome or an explicit
   revision relation; do not equate increased vector weight with knowing which
   proposition was superseded. Contradictory repeats before versus after the
   correction, unrelated routine writes, and trusted versus erroneous corrections
   are different conditions.
3. Necessary failure control: x and -x write the same xx* (or x(Jx)*) at any equal
   gain. Weighting cannot protect a sign distinction absent from the statistic.
   A first-moment/anchor or key-value/revision representation would be an explicit,
   charged design extension, not an unreported change to this adapter.

With q=1-decay and N later routine writes of unit gain, the correction's surviving
unnormalized contribution is g*q^N and the later-write mass is (1-q^N)/(1-q) for
q!=1. Existing older mass also decays. Any fixed finite g loses relative influence
under indefinitely repeated conflicting writes for q in (0,1), and also for q=1.
A zero floor on decay or salience gain is not permanent exception protection.
Success should be consequence retention plus bounded interference, not a large
moment norm or a ratio chosen by the gain schedule itself. Salience is not truth.
The released optional salience multiplier has a ceiling; the adapter's explicit
gain is a distinct caller-controlled experimental input, not a silent ceiling change.

## HOLO-1: spread-domain damage is a separate representation

Store a spread-domain state persistently, rather than FFT-transforming only during
query or immediately inverting every write. Freeze exactly what is transformed:
packed symmetric moment coordinates, a full matrix, or the scalar grid. An FFT of
a padded mostly-empty grid, a dense complex matrix and a real orthogonal transform
are not equal-byte representations. Count real scalar bytes, conjugate redundancy,
transform seeds/matrices, masks, headers and any decoding/repair metadata.

Required arms: direct storage, unitary Fourier storage, random orthogonal/unitary
spreading, and the identical direct weighted statistic before spreading. If a dense
random matrix is retained, charge it. A generated structured transform instead
requires its seed and generation/update costs. All arms get the same available
side information, regularization, repair rules and weight schedules.

For a vectorized statistic f, square unitary U and independently erased coefficients
with erasure probability p, plain zero-filled inverse decoding obeys:

```text
f_hat = U* D U f
E ||f_hat-f||^2 = p ||f||^2
```

This follows by unitary norm preservation and summing the erased coefficient
energies; U=I is included. Thus average total energy loss under iid erasures cannot
by itself distinguish FFT from no spreading or a random rotation. Spreading can
redistribute where errors occur; task-specific error, its tails, masks and coherence
must be measured. Structured/adversarial erasures and anisotropic spectra need not
give uniformly gentle degradation. An invertible square transform is not by itself
an erasure-correcting code. Real FFT conventions are described by NumPy [2].

Specify erasure of physical real/complex cells and paired-conjugate policies before
running masks. Test random, contiguous and targeted masks at 10-90% damage. Retain
zero-damage and total-erasure controls. Record what is known to the decoder about
missing cells. Predeclare any unbiased rescaling, Hermitian/PSD projection, ridge,
low-rank imputation or extra redundancy; give equivalent support and charge bytes
for all arms. Separate damage to data from damage to critical control metadata.

A useful result could be improved worst-case/task error or a cost advantage over
matched random spreading, not just a smooth plot versus unspread coordinates.
No FFT-specific advantage or hologram-fragment guarantee follows beforehand.

## REC-3: quality per actual retained byte

Compare at the same declared real-byte caps and actual used bytes:

- Weighted/decayed direct C, packed symmetric and dense variants where relevant.
- Reservoir of k raw observations, with count/RNG/weight metadata charged.
- k-means or streaming centroid summaries with centers, counts, updates and any
  retained within-cluster moments charged. Tune only on validation data.
- Frequent Directions (FD), a deterministic row-stream matrix sketch with proven
  covariance approximation bounds [1]. The guarantee concerns matrix error, not
  automatic preservation of a rare semantic correction. Weights require sqrt(g)x
  rows; a decayed variant and its applicable error statement must be specified.
- Consolidated HME, with no surviving record/lineage backup in any hidden object.

Match information, stream order, weights, context, embedding space, evaluation
queries and tuning budgets. A fixed embedding model can be common infrastructure,
but per-arm state cannot be hidden in it. Report byte-quality curves, complete query
and update latency, peak workspace and build/fitting cost. Freeze whether each arm stores the implemented complex patch or packed-real
moments. At d=16 the compact adapter retains 4,096 patch bytes plus 48 control
bytes (4,184 bytes serialized), versus 1,088 bytes for packed-real moment DATA.
The latter is a reference representation, not an information-theoretic floor or
an implemented HME checkpoint. Include all baseline metadata: a 64-KiB reservoir
holds fewer than 512 dimension-16 float64 records once RNG/count state is charged.
The adapter defaults to Hann off; Hann-on reconstruction is explicitly refused.
No unreported null grid allocation, caller backup or retained field view is allowed.

## CONT-1: preserved consequences, not record IDs

Use explicit cue-conditioned preferences, corrections, relationships and commitments.
Some old details may be discarded without failure; a scoped reversal or important
exception must change the appropriate future action without rewriting unrelated
contexts. Freeze what counts as correct consequence, missing knowledge, abstention,
false recall and spurious generalization. No semantic-efficacy claim follows from
numerical reconstruction. Full raw records must be unavailable after consolidation,
and caller caches, summaries, exception tables and model prompts all count toward
retained memory. Include matched summary/key-value/exception-memory baselines, not
just numerical covariance estimators. Test budget reduction separately from damage.

## Interpretation and sources

Passing SAL-1 against an unweighted baseline or HOLO-1 against unspread storage
would not alone break a classical tie. Direct weighted moments and the same
spreading/decoder can reproduce the corresponding construction. Claims should
identify a measured task or engineering advantage, not undefinability by classical
statistics. Product readiness remains untested; no novelty or patentability claim.

[1] Ghashami, Liberty, Phillips, Woodruff, Frequent Directions: Simple and
Deterministic Matrix Sketching (2015): https://arxiv.org/abs/1501.01711 .
[2] NumPy DFT and unitary normalization:
https://numpy.org/doc/stable/reference/routines.fft.html .

The sign and gain/decay limitations and the unitary-erasure equality above are
algebraic controls, not empirical outcome claims. Earlier independent reviews and
REC-2 characterization remain in issue #15 without being repurposed as SAL/HOLO data.
