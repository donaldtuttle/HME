# SAL-1: surprise-gated exceptions alongside consolidated numerical memory

**Status: DEVELOPMENT PROTOTYPE AND DRAFT, not a preregistration.**
No evaluation seeds have been frozen or run. The owner's one-seed pilot is
motivation only; its source/seed was not supplied and its table was not reproduced
here. Correctness tests and the deterministic smoke demonstration below are not
SAL-1 performance evidence. The pinned engine, compact adapter, prior experiments
and v3.1.0 tag remain unchanged.

## Decision and mechanism

Can a bounded consolidated model plus a small explicit exception store retain a
scoped conflicting correction, without degrading still-valid routine associations,
at a measured retained-byte budget competitive with classical alternatives?

A global weighted second moment combines incompatible mappings rather than
representing an explicit "supersedes" operation. An orthogonal new association
and a conflicting update to an existing cue are therefore distinct experimental
conditions. The proposed hybrid is a design hypothesis, not a guaranteed pass.

The claim "no gain can retain a conflicting correction without harming every
routine distribution" is too broad. With a fixed-ridge linear predictor, the
rank-one update's effect on a routine cue r is proportional to
`q_correction^T A^{-1} r`; it can vanish for unrelated directions. Conversely no
single-valued predictor can give both old and new incompatible answers to the
identical cue at the same time without additional context/version information.
Declare the cue, scope, time and authoritative target before scoring; do not count
reproducing a superseded old answer as successful routine retention.

## Implemented prototype (memory.py)

All observations are real vectors `[cue, outcome]`; query-time methods see only
`cue`. The base learns from complete observed feedback using the same joint
unit normalization in every backend. The query does not use a hidden target to
normalize itself. There are no strings, language model, semantic embeddings,
automatic scope inference, or human-identity claims in this prototype.

Three interchangeable backends are implemented:

- `FieldPredictor`: the unchanged Hann-off `ConsolidatingMemory`, consolidated
  before the first write. It retains no historical payloads or lineage.
- `DirectMoment`: the same weighted/decayed joint moment and mass-scaled ridge
  readout. This is the decisive algebraic control; same-statistic accuracy equality
  is expected up to floating point.
- `ForgettingRLS`: multioutput recursive least squares on the same normalized
  training rows, with forgetting factor `1-decay`. Its initial ridge prior decays
  with updates. The field's ridge scales with current moment trace/mass instead;
  these are deliberately distinguished, not mislabeled identical algorithms.
  Tests compare RLS to explicit exponentially weighted normal equations.

`SurpriseMemory` applies the SAME policy to each backend:

1. Receive cue and observed outcome with caller-provided `trusted` and `eligible`
   flags. These are permitted input information, not oracle test labels. Untrusted
   feedback is ignored. During a predeclared warm-up, ineligible observations train
   the base but do not create or revise exceptions. Eligibility must not reveal
   which latent test case is a correction.
2. Before the base update, measure `||base(cue)-outcome||^2 / max(||outcome||^2,1e-12)`.
   Admit above-threshold feedback into a fixed-capacity cue/outcome store. An
   `always_admit` ablation uses the same capacity and routing policy.
3. Every trusted observation updates the base, including admitted exceptions.
   This prototype does NOT secretly shield the base from high-gain corrections.
   A later exception-only-write policy would be a separately declared arm.
4. Exact repeated cues replace their existing entry. If the base already predicts
   newly received eligible feedback adequately, remove that cue's stale exception.
   At capacity, evict the oldest accepted entry. Queries do not refresh ages.
5. At recall, use the nearest stored cue within a fixed absolute Euclidean radius;
   equal-distance ties choose the newest entry. Outside the radius use the base.
   No stored target influences routing. Exact-cue recognition and noisy-cue
   generalization are separate outcomes; the radius is not learned semantic scope.

Surprise is measured automatically, but the target and trust are external.
Call this **prediction-error-gated retention of supplied feedback**, not a
self-supervised truth detector. A trusted but wrong target can enter the buffer;
that failure must be measured, not explained away. More than k simultaneously
necessary exceptions necessarily tests eviction and forgetting.

The buffer allocates cue/outcome arrays, uint64 ages, validity bits and fixed-width
policy/counter state up front. It copies inserted arrays and returned outcomes;
caller mutation does not modify retained memories. It is single-threaded,
in-memory development code. Persistence for the full hybrid, robust numeric RLS
under long unexcited streams, and semantic provenance/version reconciliation are
not implemented. The base's existing checkpoint does not include exceptions and
must not be described as a complete hybrid checkpoint.

## Required experimental conditions

The primary condition should be a trusted, scoped conflicting correction amid
N=1,000 routine writes, evaluated after the remaining writes. Final generator,
primary gain/decay selection rule and evaluation seeds are pending review.

Include genuinely new orthogonal patterns; conflicting same-cue targets; several
nearby but differently scoped cues; isotropic/unrelated routine controls; correction
reversals; multiple exceptions below, at and above capacity; noisy and near-boundary
cue queries; and trusted-but-erroneous feedback. Include an always-admit buffer
and disable-buffer controls so surprise gating is tested rather than assumed.

Sweep gain relative to routine mass (e.g. g/N) and decay relative to horizon
(e.g. decay*N), not just fixed gain values. Hold stream order and each observation's
normalization/weight constant across matched arms. Show immediate recall and later
recall. Keep unrelated future routines separate from later obsolete conflicting
repeats. If a stream supplies contradictory feedback, declare how timestamps/trust
resolve it and give that information to every method; an unexplained mixture of
old/new labels cannot justify a truth-retention claim.

Test inputs must be generated without exposing hidden targets, component identity
or true scope boundaries to any reader. Hold out entire source examples/episodes
before constructing nearby queries. Validation may tune radius, admission threshold,
ridge, gain and decay under equal search budgets. No test-set selection of the
most favorable gain, decay, checkpoint or exception count.

## Baselines and two distinct fairness comparisons

| Arm | Purpose |
|---|---|
| Field alone, unweighted and gain/decay sweeps | Pilot mechanism and forgetting trade-off |
| Direct moment alone with identical gains/decay/ridge | Matched field-statistic control |
| RLS with forgetting, tuned on validation only | Classical adaptive predictor |
| Field plus surprise buffer | Proposed hybrid |
| Direct moment plus the SAME buffer | Separates exception policy from FFT representation |
| RLS plus the SAME buffer | Strong hybrid competitor, not only a bare RLS comparison |
| Admit-all / recency buffer at the same capacity | Tests whether surprise-based admission helps |
| Budget-limited explicit cue/outcome memory | Tests whether consolidation is needed at all |

Matched-policy control: equal k, radius, threshold, weights and stream for field
and direct moment, with every actual byte reported. Same-k is NOT equal memory.

Budget comparison: a common instance-owned byte ceiling, proposed 8 KiB primary
and 6/16 KiB secondary. `fit_budget()` chooses the largest whole exception capacity
under that ceiling for each backend. The more compact direct/RLS bases can use
more exception entries; do not reserve their savings or pad them with unused data.
Publish capacities and unused remainders. A common cap is not a claim of exactly
identical consumption, since records are indivisible. Freeze the runtime, byte
counter, accepted exclusions and capacity table before evaluation.

The shared counter includes instance-reachable base state, arrays, buffer, fixed
configuration and Python containers, counting aliases once. Also report numeric
array bytes independently. It excludes module/class code, interpreter RSS,
allocator slack, temporary workspace, external input streams and caller-owned
copies. Report update/query latency and peak workspace separately. Use no hidden
full-record store. Any future checkpoint or transform metadata must be charged.

## Proposed gates: preserve the user's thresholds without ambiguous percentages

For a nonzero ground-truth outcome, define each error as
`e=||prediction-target||^2/||target||^2`; score `s=1-e`. Keep negative scores;
do not clip them or interpret them as confidence. A zero-target convention must
be frozen or those targets excluded by the generator before evaluation.

Per independent seed, average correction error over its held-out correction
queries (Ec) and still-valid routine error over a distinct fixed suite (Er).
Report a balanced joint error `J=(Ec+Er)/2`, so 1,000 routine observations do not
numerically overwhelm a rare correction's metric. These are proposed, not final
registered decision rules:

1. Lower one-sided/paired-seed confidence bound for mean correction score >= 0.90.
2. Upper bound for `Er_hybrid - 1.01*Er_field_reference` <= 0. This is a **relative
   one-percent error allowance**, not a one-percentage-point score allowance.
   Compute the difference, not a ratio dividing by a possibly near-zero reference.
   Also compare against an unweighted no-correction-stream reference, to prevent
   a badly damaged gain-heavy field from making the routine guardrail easy.
3. Positive paired lower confidence bound for `J_bare_RLS - J_hybrid`, with the
   minimum practical improvement fixed before evaluation. RLS settings are chosen
   on validation only, never by comparing test scores and selecting a weak run.
4. All retained-state budget and data-isolation checks pass.

A pass against **bare** RLS supports a hybrid benefit for that task, not superiority
to the best classical hybrid. Report direct-plus-buffer and RLS-plus-buffer next
to the primary result. Their results may tie or outperform HME without invalidating
an application-level benefit of bounded exceptions. No universal "field cannot,
hybrid can" theorem follows from a finite sweep.

Use independent stream seeds as the resampling unit, not correlated queries from
one seed. Predeclare confidence levels, bootstrap seeds/counts, multiplicity policy,
primary selection, sample size and all failures. No formal PASS is computed by
this prototype: the dataset and statistical evaluator are not frozen or implemented.

## Publication and scope

Before any SAL-1 evaluation, publish the COMPLETE protocol, exact implementation,
evaluator, tests, byte table, validation-selection rule and disjoint seed sets.
Then push the evaluator/registration commit, freshly fetch the canonical origin,
verify remote containment and frozen blobs, and retain server-side provenance
before generating evaluation data. Publish all cells including failures. Opening
this development PR is not that preregistration and reserves no unseen test seeds.

The fast-exception/slow-shared-model analogy has prior art in complementary learning
systems. That is motivation, not evidence that this numerical prototype models a
human memory system, establishes semantic continuity, or is product-ready.

Method sources:
- McClelland, McNaughton, O'Reilly (1995), complementary learning systems:
  https://pubmed.ncbi.nlm.nih.gov/7624455/
- Lai and Bernstein (2024), SIFt-RLS and forgetting context:
  https://arxiv.org/abs/2404.10844
  The prototype implements ordinary scalar exponential forgetting, NOT SIFt-RLS.
- Existing HME second-moment and consolidation contracts:
  ../../docs/CONSOLIDATION.md and ../reconstruction_v1/REPORT.md.

## Run development checks

```bash
python -m pytest tests/test_salience_memory.py -q
python experiments/salience_v1/smoke.py --output outputs/sal1-development.json
```

The smoke uses fixed basis-vector fixtures, no random evaluation seed. It exercises
one scoped reversal, 1,000 subsequent off-scope writes, bounded state and classical
controls. An exact stored-cue buffer hit in that demonstration is an implementation
check, not evidence of generalization or a registered correction-retention result.
