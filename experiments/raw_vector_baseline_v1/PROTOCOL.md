# HME-NN-3: raw-vector baseline and Hann-window ablation

Status: prospective protocol; no evaluation outcomes were used to choose this design.
Registered in response to the owner's supplied independent review on 2026-09-25.
The review's approximate five-seed results are prior exploratory evidence, not
results of this study. Its source, seeds and complete evaluator were not supplied.

## Question and primary endpoint

How much of the frozen HME ranker's identity-retrieval loss is associated with
its stored-vector Hann taper, query asymmetry, similarity sign and field term?
The prior HME-NN-1 matched-processed-vector comparison remains valid for its
stated question; it is not a raw-input nearest-neighbor benchmark.

Primary condition: 128 independent N(0,1) vectors, dimension 16, all at (32,32)
in a 64 by 64 field, native numeric queries x + sigma*z, sigma=1.0.
Do not normalize x before adding noise. For each seed generate all item vectors
first, then independent standard-normal query perturbations in sigma order
[0.0, 0.25, 0.5, 1.0]. Each item is queried once per condition. All arms receive
identical raw items and identical raw noisy queries before their named transforms.
Tie-break on original insertion index; report top-1 correct count and accuracy.

Evaluation seeds: consecutive integers 26092501 through 26092530 inclusive.
Development/unit-test seeds must be below 10000 and cannot enter these results.
No tuning, fitting, seed replacement, optional stopping or primary switching.
Any failed cell invalidates a complete-result claim and must be disclosed.

## Arms (all candidates available; no target-ID input to ranking)

1. raw_signed_nn: unit-normalized raw item vectors and raw queries; signed cosine.
2. raw_absolute_nn: same raw vectors and queries; absolute cosine.
3. processed_signed_nn: frozen HME's Hann-processed ledger vectors, raw queries;
   the explicitly named matched-processed baseline used by HME-NN-1.
4. processed_symmetric_nn: same processed vectors, Hann-tapered queries.
5. hme_default: the unchanged pinned engine with its default Hann window.
6. hme_symmetric: the unchanged default engine, with queries tapered once before
   entering retrieve_memory (the native query path does not taper).
7. hme_no_window: unchanged engine with HMEConfig(use_hann_window=False).
8. hme_no_window_field_erased: arm 7 with only the field zeroed; keep the ledger.
9. hme_no_window_signed: experimental scoring-only sign substitution, preserving
   every other component of arm 7. Verify it against public per-hit components.

The experimental signed arm is not a production engine modification. The source
pins, archived results and default configuration remain unchanged. Erasing the
ledger while retaining the field is a structural identity check, not an accuracy
arm. Run it for each seed and require zero identity hits.

## Analysis

Publish every seed, noise level and arm, including per-query predicted indices,
item/query data hashes, source hashes, Python/NumPy versions and configuration.
Primary contrast: hme_default minus raw_signed_nn at sigma=1.0, in percentage
points. Prespecified explanatory contrasts: hme_no_window minus hme_default;
hme_symmetric minus hme_default; processed_signed_nn minus raw_signed_nn;
hme_no_window minus raw_signed_nn; hme_no_window_signed minus raw_signed_nn;
raw_absolute_nn minus raw_signed_nn; and hme_no_window minus its field-erased arm.
Use paired seed means and a percentile 95% seed-bootstrap interval, 10000 draws,
with bootstrap seed 26092500. Secondary noise conditions and all decomposition
contrasts are descriptive (no multiplicity-adjusted causal/superiority claims).
Also report gap reduction (no-window improvement / default-to-raw gap), only when
the denominator is positive; this ratio is descriptive and not a causal share.
Do not confuse counts out of 128 with percentage points. Do not claim equivalence
from a nonsignificant difference. This is an accuracy study: no latency, memory,
semantic-memory, field-only identity or real-model efficacy claim is authorized.

## Publication and execution boundary

Push this protocol before implementing or running evaluation seeds. Then publish
the evaluator and its development tests in a second registration commit, before
running evaluation. The evaluator must accept that exact registration commit,
verify its frozen protocol/evaluator/test/engine bytes with git, refuse existing
output directories, and write failures explicitly. Record both registrations.
Only development tests may run before the evaluator registration is public.
Publish results in a subsequent commit. Preserve existing experiment reports.

This review follows already completed HME-NN-2A sign and HME-NN-2B field studies;
it does not retroactively change their questions or rerun their fixed seeds.
A default change requires a separately versioned migration decision, not a silent
edit to the frozen 3.0 storage component or its 3.1 runtime package.
