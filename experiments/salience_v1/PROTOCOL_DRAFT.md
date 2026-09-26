# SAL-1: surprise-gated exceptions alongside consolidated numerical memory

**Status: DEVELOPMENT PROTOTYPE AND DRAFT, not a preregistration.**
No evaluation seeds have been frozen or run. The policy-review constants in
[POLICY_CONSTANTS.json](POLICY_CONSTANTS.json) now fix admission, matching, capacities,
threshold, candidate radii, explicit radius profiles, eviction arms, and required cue-noise levels. Those constants plus development
fixtures are NOT a complete performance preregistration. The owner's one-seed pilot is
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
normalize itself.

### Gain semantics under joint normalization

For a raw observed row z=[cue,outcome], every backend trains on u=z/||z||:

```text
moment contribution = gain * u u^T = (gain / ||z||^2) * z z^T
RLS data-term weight in raw coordinates = gain / ||z||^2
```

`gain` is the weight of the normalized joint direction, NOT a raw observation
weight. At an unchanged cue, multiplying the outcome by three changes that raw
weight by `(||cue||^2+||outcome||^2)/(||cue||^2+9||outcome||^2)`.
Large outcomes are therefore down-weighted relative to raw-space regression.
This is deliberate common preprocessing, not compensation for salience and not
an outcome-independent weighting rule. Normalized moments carry gain units of
trace mass. A raw-weight alternative would need an explicit magnitude-compensated
write policy in all arms, including its effects on ridge and mass accounting.
This review does not change the encoder, normalization, or gain/decay update.

There are no strings, language model, semantic embeddings,
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
2. Before updating, compute BOTH base and current hybrid predictions. Admission
   surprise is `||hybrid(cue)-outcome||^2/max(||outcome||^2,1e-12)`. When no entry
   matches, the hybrid uses the base. The threshold is 0.1 NMSE, strictly exceeded.
   The base loss remains available for diagnostics and safe exception retirement,
   not for admitting repeats already handled correctly by the hybrid.
3. Revision, removal and recall use the SAME nearest cue within the selected radius in
   absolute Euclidean units (boundary included); exact distance ties choose the
   newest accepted entry. With eligible feedback, remove a matched exception if
   the PRE-UPDATE BASE is already adequate (base NMSE <=0.1). Otherwise retain it
   unchanged when the hybrid is adequate, even if the base still gets it wrong.
   Unsurprising repeats never increase admissions. FIFO does not refresh ages;
   the confirmation-refresh ablation updates eviction age as specified below. For surprising
   feedback, replace the matched target in place; without a match allocate a new
   slot and evict the oldest entry by the chosen eviction clock when full. A revision keeps its first
   accepted cue anchor fixed, so small changes cannot walk a matching region.
4. Every trusted observation still updates the base, including admitted corrections
   and unsurprising repeats. No buffer state changes if the base rejects its update.
   Ineligible observations cannot create, revise or retire entries. An explicit
   `always_admit` control reuses the same matching/anchor policy but always admits
   eligible feedback, and does not apply the base-adequacy retirement rule.
5. At recall, return the matched stored outcome, or the base outside all matching
   radii. Only cues and acceptance order affect routing, never hidden test outcomes.
   Nearby distinct contexts can still collide inside one radius. No geometric
   radius establishes semantic identity; conflicting nearby scopes and boundary
   crossings are mandatory controls. Larger cue noise can exceed the radius and
   legitimately create additional entries; the policy is not an unlimited deduper.

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

Required cue noise is now literal: iid zero-mean Gaussian noise per cue component,
with absolute standard deviations 0, 1e-6, 0.01 and 0.05, applied to repeated
feedback cues and independently generated held-out recall cues. Repeated sightings
of one scoped correction carry the same supplied outcome; noise on outcomes is a
separate condition. The final corpus must declare base cue scaling and the primary
noise cell. The fixed development regression uses six deterministic 1e-6-scale
perturbations, not evaluation RNG seeds or an empirical Gaussian study.

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
before constructing nearby queries. Admission threshold remains fixed; radius
uses the validation-only rule below. Validation may select
ridge, gain and decay under a subsequently frozen equal-budget selection rule;
changing a fixed policy constant requires a new public version before evaluation.
No test-set selection of the
most favorable gain, decay, checkpoint or exception count.

## Radius review: validation selection plus declared geometric stress

This supersedes the universal fixed-radius reading of policy v2. That exact JSON
is preserved as `POLICY_CONSTANTS_v2.json`. Policy v3 chooses (a) plus (c): tune
radius using validation streams for the efficacy comparison, and keep an explicit
fixed-radius high-noise stress arm. No radii have yet been selected from real
validation streams, and no SAL-1 evaluation has run.

### Quantified limitation of the old fixed radius

If an anchor and a later cue are independent observations of one true cue, each
with independent N(0,sigma^2 I_d) noise, their difference has covariance 2 sigma^2 I:

```text
||difference|| / (sqrt(2)*sigma) ~ chi_d
P(match at radius r) = F_chi2_d(r^2/(2*sigma^2))
d=8, r=0.1:
  sigma=0.01 -> 0.9999999591324105
  sigma=0.05 -> 0.01898815687615381
```

These are analytic pairwise probabilities, not measured SAL-1 outcomes. A clean
anchor gives a different variance; conditioning on one fixed noisy anchor gives
a noncentral law. Admission selection and multiple stored anchors change total
hit rates. The 1.9% figure is not the recall rate of an adaptive six-entry store
and does not determine total task error because the base can also predict.
The owner's 20-trial table is a separate development report, not independently
rerun here. Expected fragmentation/misses at fixed r=0.1, sigma=0.05 are a declared
stress failure mechanism, not a surprise violation of the revised admission rule.

### Separate radius profiles and validation-only selection

- **Primary candidate:** sigma=0.01 with a validation-selected radius. This is a
  proposed primary cell, still subject to the complete pre-evaluation registration.
- **Secondary candidates:** sigma=0, 1e-6 and 0.05 with validation-selected radii.
- **Declared stress:** sigma=0.05 with fixed radius 0.1. Report the expected geometric
  limitation even if it fails. Never substitute its result for the tuned cell.
- `fixed_development` keeps r=0.1 for existing correctness fixtures, NOT a default
  efficacy arm. `fixed_stress` rejects a noise designation other than 0.05.

Use the literal candidate radii `[0.05,0.1,0.15,0.2,0.25,0.3,0.4]`, in absolute
raw-cue units, with the same stream/feedback information for every candidate.
For each declared backend, budget profile, and known noise regime, reduce the
FIFO validation results by independent stream: Ec is correction NMSE, Er is
still-valid routine NMSE, and J=(Ec+Er)/2. First require mean Er <= 1.01 times
the mean error of a common no-correction routine reference. Among feasible radii
choose minimum mean J; exact ties choose the smallest radius. The reference must
be identical across radii for each stream. Log all candidate losses, false matches,
duplicate admissions, evictions and technical failures, not just the winner.
This feasibility rule is a validation selection rule, not a statistical PASS gate.

`radius_selection.select_validation_radius()` implements that deterministic table
reduction. It requires every candidate to contain the same complete stream IDs,
rejects evaluation/test-labelled input, invalid or duplicate rows, and returns an
explicit infeasible record when nothing passes. Construction refuses an infeasible
record; no silent widening, fallback or dropped candidate is allowed. The harness
must retain technical failure logs even when selection aborts. The reducer does
not generate data or authenticate a claimed split label: the future frozen corpus,
source hashes and validation/evaluation provenance must establish independence.

The selection record retains candidate tables, stream IDs, noise/backend/profile
binding and the policy hash. `build_fixed_memory(radius_profile='validation_selected',
...)` requires this checked record, recomputes its choice, and uses literal capacity
with the existing byte cap. No table/stream is retained by the memory instance;
only the selected radius lives in its already-counted policy array. The full audit
record is experimental provenance, not a hidden deployed record store.

**Selection isolation:** select using FIFO and reuse exactly that radius for the
confirmation-refresh pair. Do not retune the radius between eviction arms in the
primary ablation. Hold all other settings, cap, stream, and queries fixed. For the
non-binding field/direct diagnostic, both use the SAME direct-moment validation
selection at matched k=4. Equal-byte arms may select separately under equal budgets;
that comparison includes capacity/policy interactions, not a new FFT effect.

Noise level is allowed setup information shared by all arms, not a quantity supplied
only to HME. A future deployment without known noise needs its own estimation rule.
Gain/decay/ridge selection must be nested on validation data with matched search
budgets and fixed before evaluation. Stream IDs, population cue scaling, resulting
radius table, gain/decay procedure, exact runtime and decision settings remain
pending. Publish the complete protocol first; run validation and push the selected
configuration table before generating the held-out evaluation seeds.

## Eviction ablation: confirmation, not query popularity

The FIFO control evicts by last acceptance/revision time. Its name is shorthand
for the existing oldest-accepted policy: a real revision already refreshes it.
The new `refresh_on_confirmation=True` arm uses least-recently-confirmed eviction,
where a new admission/revision initially counts as a confirmation.

Refresh an existing age only when supplied feedback is trusted and eligible,
the matched PRE-UPDATE HYBRID is adequate (NMSE <=0.1), and the PRE-UPDATE BASE
is inadequate. Base adequacy still retires the entry first; surprising feedback
still revises it. Confirmation alone changes neither anchor, outcome, admissions,
threshold nor radius. Every trusted observation continues to update the base.
Read-only `predict()` calls NEVER refresh an entry, because no new observed outcome
has confirmed correctness. A user repeatedly querying an erroneous exception
cannot make it immortal through query count. Supplied trusted-but-wrong feedback
can still confirm a wrong entry; surprise is not truth.

The same uint64 ages are reused; a mode bit shares the existing one-byte policy
flags field. Retained array/object counts and literal capacities remain the same.
To isolate eviction from recall ties, valid slots are stored in acceptance order.
Confirmations update age without reordering; admissions/revisions move a logical
entry to the newest acceptance position. Thus equal-distance recall/revision ties
still choose newest ACCEPTED, not most recently confirmed. Compaction can move
private array slots, but does not duplicate an entry or move its cue anchor.
Compaction work and temporary copies are costs to measure, not free performance.
No persisted hybrid format is changed because one has not been implemented.

Required capacity-pressure controls: recurrent confirmations of useful exceptions;
stale exceptions that should expire; repeated erroneous supplied feedback;
nearby conflicting scopes; more necessary exceptions than capacity; confirmations
near/outside the radius; and streams where frequency is not importance. Measure
correction score AND routine error, plus false overrides, duplicate admissions,
confirmations, evictions, occupancy, and update/query costs. The hybrid may win or
lose; confirmation refresh is an ablation, not guaranteed improvement. At matched
statistic and policy the existing field/direct equality expectation is unchanged.

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

### Predetermined representation equality versus policy outcomes

Field and direct moments carry the same statistic with the same regularizer.
At equal buffer capacity and identical policy decisions they yield the same
predictions in exact arithmetic. A tiny floating discrepancy near an admission
threshold can trigger different discrete decisions; record decision margins and
check policy-state parity rather than treating such divergence as an advantage.
This comparison is a representation/capacity-accounting result, NOT an open
field-specific accuracy hypothesis.

The matched non-binding condition fixes k=4 in both arms (also available for RLS).
The eventual diagnostic corpus must ensure the buffer does not need to evict, and
log every occupancy and policy decision. If it binds, that cell is not evidence
of non-binding equality and must be retained as a failed diagnostic, not silently
excluded. Correctness fixtures already exercise the equality away from thresholds.

The direct backend can emulate a field hybrid's same-k policy using fewer bytes;
its feasible design set includes that choice. Extra bytes permit a larger buffer.
However, automatically using more slots is NOT a theorem of pointwise lower loss
for this noisy nearest-radius policy: it may retain a wrong or overbroad entry that
a smaller buffer evicts. Hybrid-aware admission also makes future buffer histories
capacity-dependent. A deterministic nearby-scope counterexample is in the tests.
Report the memory advantage without assuming a fixed larger-buffer policy weakly
dominates on every stream. No extra predictive information comes from the field.

### Fixed capacity and policy constants, checked rather than rederived

For the 8 KiB (8,192 byte) instance-owned cap and cue/outcome dimensions 8/8:

| Backend | Budget-condition k | Matched non-binding k |
|---|---:|---:|
| Field | 20 | 4 |
| Direct moment | 37 | 4 |
| RLS | 43 | 4 |

All use threshold NMSE 0.1. The fixed development/stress radius remains 0.1;
selected-radius arms use one validation-selected constant per declared noise level.
Capacities and the radius-selection rule are explicit in `POLICY_CONSTANTS.json`,
not estimates recalculated for each runtime.
`configuration.build_fixed_memory()` instantiates these literal capacities and
asserts the byte cap before use. A changed runtime that exceeds the cap must abort;
it must not silently shrink capacity, change thresholds, or enlarge the budget.
`fit_budget()` remains DEVELOPMENT-ONLY for planning future profiles, never for
selecting capacity in an evaluation. The 6/16 KiB secondary suggestions remain
unregistered until their own literal capacity tables are chosen and published.

The source of variation is real: Python's `sys.getsizeof` reports object storage
using implementation-specific object hooks, not portable algorithmic parameter
counts. The complete registration must pin the reference Python/NumPy/platform,
byte-accounting code and policy JSON before data generation. Development runs on
other versions may assert the same capacities fit but do not redefine the table.
Publish actual used bytes and remainders; same cap is not exactly equal consumption.

Open efficacy questions are hybrid versus bare base; moment-hybrid versus
validation-tuned RLS; surprise-gated versus admit-all retention; and performance
against direct+buffer and RLS+buffer with identical information and the fixed caps.

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
evaluator, tests, fixed policy JSON and byte table, validation-selection rule and disjoint seed sets.
Then push the evaluator/registration commit, freshly fetch the canonical origin,
verify remote containment and frozen blobs, and retain server-side provenance
before generating evaluation data. Publish all cells including failures. Opening
this development PR is not that preregistration and reserves no unseen test seeds.

The fast-exception/slow-shared-model analogy has prior art in complementary learning
systems. That is motivation, not evidence that this numerical prototype models a
human memory system, establishes semantic continuity, or is product-ready.

Method sources:
- Chi / chi-square CDF conventions: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2.html
- Python object-size contract: https://docs.python.org/3/library/sys.html#sys.getsizeof
- McClelland, McNaughton, O'Reilly (1995), complementary learning systems:
  https://pubmed.ncbi.nlm.nih.gov/7624455/
- Lai and Bernstein (2024), SIFt-RLS and forgetting context:
  https://arxiv.org/abs/2404.10844
  The prototype implements ordinary scalar exponential forgetting, NOT SIFt-RLS.
- Existing HME second-moment and consolidation contracts:
  ../../docs/CONSOLIDATION.md and ../reconstruction_v1/REPORT.md.

## Run development checks

```bash
python -m pytest tests/test_salience_memory.py tests/test_salience_radius_review.py -q
python experiments/salience_v1/smoke.py --output outputs/sal1-development.json
```

The smoke uses fixed basis-vector fixtures, no random evaluation seed. It exercises
one scoped reversal, six tiny-noise sightings without duplicate admission, 1,000
subsequent off-scope writes, fixed-capacity byte assertions and classical controls.
The prior records are preserved as `development_checks_base_only.json` and
`development_checks_fixed_radius_v2.json`; the regenerated `development_checks.json`
records the new policy and source hashes. Neither is performance evidence. An exact
stored-cue buffer hit in that demonstration is an implementation
check, not evidence of generalization or a registered correction-retention result.

The radius/eviction review adds deterministic selection-table fixtures, exact
Gaussian pair-coverage calculations, confirmation-versus-FIFO eviction checks,
trusted/eligible/read-only safeguards, unchanged newest-accepted ties, and byte
parity. Fabricated score tables test reducer logic only, not selected SAL-1 radii
or evidence that validation tuning improves performance. No performance seeds
were reserved or run by this amendment.
