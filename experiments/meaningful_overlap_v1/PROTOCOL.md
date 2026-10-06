# HME-MO-1 proposed registration

Status: **DESIGN / DEVELOP. NOT REGISTERED.** User authorization covers implementation, correctness, development and validation only. The confirmatory command must remain blocked until explicit approval and an immutable pre-execution registration. Final handoff state is READY_FOR_PROTOCOL_REVIEW if the implementation checks complete, never EVALUATION_PASSED.

## Question and scope

Does assigning related numeric memories to overlapping locations improve sibling retrieval while retaining exact identity? The intervention rearranges whole encoded patterns. It does not implement feature masks, shared-feature binding, a new encoder, a decoder, novelty detection or rejection. Texture filtering and bleeding are explanatory analogies only. It is possible for a local readout to mix additive contributions without proving irrecoverable destruction of every original. (ρ̂_conf_HIGH: writer semantics)

The hypothesis that this assignment helps the specified readout is untested before execution. (ρ̂_conf_UNK) A conventional vector graph may explain any apparent benefit without a spatial field. No QOFT construct is implemented or amended here; no physical or consciousness claim is at issue. The tested realization is HME's numeric Hann/FFT writer and NN-2B's experimental candidate-patch readout.

Historical NN-2B, including its failed gate, protocol, scorers, fixtures, raw data, report, archive, source pins and 4 MiB cap remain unchanged. New data never enter its headline numbers. This is not an authorized Stage 3. See `IMPLEMENTATION_MAP.md` and `SOURCE_PROVENANCE.json` for source commits, byte lengths, hashes and inspection time.

## Corpus and information boundary

All parameters are in `protocol.json`. There are 128 items in 16 families of 8, dimension 16. Generate independent standard-normal prototypes and residuals, with x[g,j] = sqrt(r) prototype[g] + sqrt(1-r) residual[g,j]. Keep their original scale until encoder preprocessing. Each corpus namespace generates fresh data. The primary r is 0.50. Descriptive r values are 0, 0.25 and 0.75; labels at r=0 have no generative relationship available in the vectors.

Queries are x + sigma epsilon, four independent perturbations per item and sigma, with sigma in {0, .25, .5, 1}. Only queries are corrupted. There are no noisy writes and no stored-field corruption in the primary task. Sigma 1.0 is primary. At sigma zero repeated queries coincide; they still do not count as independent corpus replicates.

Corpus vectors, opaque external IDs, insertion order, layouts, perturbations and query order use named SHA-256-derived PCG64 streams. No direct historical numeric seed is reused. `HME-MO-1/development/000..003`, `validation_tune/000..011`, `validation_check/000..011` and `reserved_test/000..049` are separate. Stream calls have no advancing shared global state. Changing layout call count cannot change data or queries.

Insertion order is independently permuted before construction and shared by all arms. It is the stable tie order. External IDs are independent 128-bit opaque strings, do not encode family, and map to position-dependent HME artifact IDs for each rebuilt field. Placement sees processed stored vectors only. Hidden prototypes, labels, targets and future evaluation queries are absent from its API. Labels and clean target indices enter scoring only after every candidate receives its score. All layouts are constructed before their corpus's evaluation queries are generated.

## Layouts and writer

All layouts use 16 × 16 patterns, a 256 × 256 complex128 canvas, strength .10, weight 1, no salience, decay or eviction, no clipping. The raw length-16 vector receives exactly one Hann window and L2 normalization in the unchanged writer. The normalized FFT outer-product pattern is added at the supplied address. Do not substitute deterministic string hashes for relationships.

RANDOM_MATCHED and SIMILARITY_PLACED share an 8 × 16 centered slot grid with spacing 8. Their occupancy and complete intersection geometry match exactly. SEPARATED uses spacing 16 on the same canvas and is the no-interference reference.

J is the sum of pair overlap fractions times signed processed-vector cosine divided by total pair overlap weight. Overlap is the product of positive intersection widths divided by 256, including diagonal intersections; self-pairs have weight zero. Zero vectors have cosine zero. The implementation computes the equivalent symmetric ordered-pair sum.

Swap search uses two restarts and 4096 index-pair proposals per restart. Restart zero begins at the random matched assignment. The second begins at its own fixed random permutation. Proposed pairs are uniform with replacement, generated in advance from the restart's separate stream. Self-swaps are skipped. Accept only J gains >1e-12; equal proposals are rejected. Retain the best restart, with lexicographically smaller slot-to-item sequence breaking differences <=1e-12. No retrieval score or label selects a layout. No validation retuning of the layout is permitted in this milestone.

Placement is achieved only if primary J exceeds random matched J by >1e-6 for every corpus. Otherwise classify the intended comparison as MECHANISM_NOT_TESTED. Also measure pair geometry, occupancy histogram, signed neighbor similarity, evaluator-only family enrichment, actual-offset complex pattern inner products and normalized real agreement, full-field norm/energy, and candidate-patch error relative to its known isolated write. Those known writes remain evaluator diagnostics, absent from field-only search snapshots.

## Retrieval and conventional comparisons

Each method scores all 128 candidates. No target address, target ID, family filter, salience hint or target-specific candidate pruning is accepted.

| Method | Score and retained numerical state |
|---|---|
| SIGNED_NN | Signed cosine of matched processed vectors; retains those vectors. |
| ABSOLUTE_NN | Absolute cosine of the same vectors; encoder diagnostic. |
| FIELD_ONLY | Frozen NN-2B normalized candidate-patch/query-pattern absolute Frobenius correlation; retains field and optional accumulated-patch cache, no original vectors or isolated patterns. |
| HYBRID | .42 signed cosine + .20 field score, unchanged weights. Retains field plus processed vectors and optional accumulated-patch cache. |
| RAW_SIGNED_NN | Cosine of normalized original vectors and raw queries, no Hann. This representation difference is intentional and disclosed. |
| VECTOR_AGGREGATE | (1-lambda) own cosine + lambda positive-weight mean of other items' query cosines, using a graph from stored vectors. |

Frozen field/NN snapshot metadata includes records, lineage, addresses and artifact IDs; local external identity maps are also charged. Raw and aggregate baselines retain the IDs and numerical data they use; metadata is not padded to equal consumption. Every method has the same candidates and information-access ceiling. No array retained for scoring may be omitted from cost accounting.

For VECTOR_AGGREGATE, top-k neighbors exclude self, rank by signed cosine and use stable insertion ties. Negative/zero similarities receive weight zero; positive weights sum to one. An empty neighborhood uses own signed score. Before validation, declare 30 candidates: representation {raw, processed}, k {4,8,16}, lambda {0,.1,.25,.5,.75}. Tune only on all 12 validation_tune corpora in the primary cell. Maximize mean sibling precision among rules with mean exact accuracy >= raw NN minus .01. Ties within 1e-12 prefer smaller lambda, smaller k, then raw. Lambda zero is included; the raw lambda-zero candidate is always feasible. Save the complete table and selected rule to FROZEN_BASELINE.json before validation_check or reserved test execution.

The primary query mode is **symmetric**: Hann once, normalize, and pattern generation with no second Hann. NN-2B used **native** as its primary. Native remains descriptive here; raw NN always uses raw query normalization. Processed aggregation uses the declared query mode, raw aggregation always uses raw queries.

## Controls

1. Geometry-preserving content shuffle: shuffle the optimized item assignment over the same slots, rebuild memory and all accurate maps. It is a valid rebuilt layout, not a broken candidate association.
2. Association permutation: cyclically shift field-score columns by a fixed nonzero namespace-derived offset while signed vectors remain aligned. This deliberately broken readout is diagnostic only.
3. Zero field: replace a hybrid snapshot's field with zeros, invalidate its cache, and require exact signed NN scores/rankings after the frozen readout's algebraic common-offset cancellation.
4. Isolated patterns: require field score = abs(cosine)^2 within 1e-12 and identical hybrid/signed NN rankings. For real vectors, .42c+.20c² is strictly increasing over [-1,1]. SEPARATED HYBRID and SIGNED_NN are displayed but not independent confirmations.
5. Shared-address and opposite-polarity fixtures: candidate patches at one address tie, and opposite queries give identical field scores. These are small structural checks, not the semantic dataset.
6. Firewall fixtures: changing/removing evaluator labels or targets changes no construction or score vector; query reordering only reorders score rows. A field-only snapshot has no source vectors or isolated patterns. Cached and uncached score agreement <=1e-13, exact ranks, and invalidation after replacement are required.

## Metrics and statistics

Primary association is sibling_precision_at_5. Score/rank the entire candidate set first. The evaluator then removes the exact target and takes the next five, scoring the fraction in its family. Identity is exact_top1_accuracy on all candidates. Also report exact top-5, MRR, wrong member in right family, wrong family, family top-1/precision-at-5 including target, and ties. Family-including metrics are descriptive. Ranker outputs do not establish calibrated recognition or rejection of unknown queries.

Average query outcomes within each independent corpus first. Layout restarts and queries are not independent experimental replicates. Propose 50 confirmatory corpora. Validation_check provides paired-effect SDs and normal-approximation simultaneous halfwidths at n=50, using 2.394 SD/sqrt(50), solely to inform protocol review. No sample-size change after reserved-data generation. Any requested revision occurs before immutable registration.

All six effects are SIMILARITY_PLACED HYBRID minus the named comparator:

| Effect | Metric | Comparator | Required lower bound |
|---|---|---|---:|
| 1 | sibling precision at 5 | RANDOM_MATCHED HYBRID | > .02 |
| 2 | sibling precision at 5 | SEPARATED HYBRID | > .02 |
| 3 | sibling precision at 5 | RAW_SIGNED_NN | > .02 |
| 4 | sibling precision at 5 | frozen VECTOR_AGGREGATE | > .02 |
| 5 | exact top-1 | SIGNED_NN | > -.01 |
| 6 | exact top-1 | RAW_SIGNED_NN | > -.01 |

Use 20,000 common paired-corpus bootstrap resamples, analysis seed 73610491, linear quantiles. Each directional decision uses the 0.05/6 lower percentile, a conservative Bonferroni family-alpha .05 procedure. Coverage is approximate. Hashes and draw counts do not supply exact finite-sample coverage. Show ordinary two-sided .025/.975 intervals separately. Zero-variance intervals describe observed corpora, not population certainty.

Machine-readable outcomes separate placement benefit, association over tested baselines, identity preservation and full proposed success. Full success requires all six strict bounds, all integrity checks, achieved placement and the memory cap. TRADEOFF means the association criterion passes while the identity safeguard does not; it does not automatically establish inferiority. Otherwise report ADVANTAGE_NOT_ESTABLISHED or MECHANISM_NOT_TESTED on invalidity. An interval crossing a margin proves neither equality nor inferiority. Development analysis uses the same logic diagnostically and is explicitly labeled DEVELOPMENT_OBSERVATIONS, never a preregistered result.

## Larger canvas and costs

Translate the unchanged three principal layouts into a 512 × 512 canvas, retaining patch values/gains and relative positions. Require score difference <=1e-12 and exact ranks before interpreting any size effect. A separate descriptive 512/spacing12 optimized layout changes spacing; its geometry, scores and costs are reported separately. Patch size and item count never change. Query corruption never controls canvas choice.

Propose a new 16 MiB retained-state cap per arm on both canvas sizes, subject to review before registration. This does not alter NN-2B's 4 MiB cap. Use the frozen NN-1 recursive CPython/owned-array accounting, deduplicating reachable aliases. Show field, vectors, graph arrays, address maps/records, accumulated-patch caches, Python overhead and independently measured uncompressed NPZ plus JSON serialized size. The serialization is a declared experiment search-state representation, not production save_npz restart support.

Measure placement/graph construction, actual writer insertion, snapshot construction and cache construction/invalidation separately. Rewrite throughput is not measured. Median and p95 online query latency use 16 primary queries ×3 repetitions after 3 warmups, one numerical thread, top five IDs/indices and scores only, with rotated method order. Report absolute nanoseconds and paired ratios. Separate tracemalloc query-workspace instrumentation from timing and from whole-process peak RSS, which includes all evaluator/build states and is not an arm's retained memory. Warm cached and uncached variants are reported. Exclude interpreter/shared-code/allocator overhead from retained-object accounting and state these limits.

Accuracy does not establish production suitability. No deployment workload or absolute latency acceptance limit has been specified. A large ratio and a small absolute increment should both be visible.

## Execution, failure and registration

1. Correctness fixtures and development namespaces 000 and 001 only.
2. Commit the complete source/protocol before running the declared 12-corpus vector tuning plan.
3. Freeze and commit its selected baseline, then run all 12 independent validation_check corpora and all descriptive cells.
4. Return source, tests, raw development records, plots, command receipts and proposed registration for review. Stop.

The confirmatory API refuses proposed status, missing approval, uncommitted/mismatched source hashes, unapproved or exposed namespace, missing frozen baseline and registration not freshly visible on canonical GitHub branches. It verifies all local experiment Python, configuration, protocol/review docs, correctness fixtures and imported writer/readout/accounting hashes against the approval and registration commit. This is a workflow guard, not a defense against an operator deliberately editing Python to bypass it.

The approved registration document must give approver, approval reference/time, exact hash map, explicit no-prior-test-exposure and contamination decision. Approval identity/reference must be verified during review; a JSON field alone is not proof of user authorization. No approval document is created by this build. See REGISTRATION_REVIEW.md for the exact approval sequence.

Every run refuses an existing output directory. Each completed corpus is saved immediately; failures receive a per-corpus record, are not replaced, and suppress aggregate decision output. A top-level FAILURE.json preserves failure details. Corrections after reserved-data exposure require an immutable amendment, retained failed outputs and an explicit contamination decision; this implementation refuses reuse of an exposed reserved namespace. All seeds/cells must be completed without outcome-driven selection.

A valid future positive result applies only to the frozen synthetic corpus, noise model, placement and readout. It cannot establish shared-feature binding, general vector-database superiority, real-world semantics, human-like memory, consciousness, quantum behavior, physics, optimal capacity or algorithmic novelty. A negative test of this whole-patch representation is not a verdict on every associative memory design. (ρ̂_conf_HIGH: limits of this experimental design; novelty remains ρ̂_conf_UNK)
