# Evaluation plan

Status: the first exact nearest-neighbor comparison is complete.
[HME-NN-1 results](../experiments/nn_baseline_v1/REPORT.md) report all ten
preregistered seeds without deviations. The current HME ranker scored 47.73%
versus signed-cosine NN's 57.27% on the primary condition, a paired difference of
-9.53 percentage points (95% interval [-10.70, -8.28]). The registered practical
advantage claim failed. The protocol and evaluator were published before execution.

Completed scope: four query-noise levels, two preprocessing modes, exact signed
and absolute NN, an erased-field/ledger-retained control, a field-only structural
check, top-1/top-5/MRR, unmatched-query acceptance, actual persistent storage
under a common maximum budget, and online API latency. Remaining work includes
load/dimension/spatial-cue sweeps, an equal-consumed-byte capacity frontier,
semantic datasets, HRR/VSA, calibrated rejection and the calibration plan below.
Any new efficacy claim needs a new frozen protocol; this result must remain visible.

## Sign ablation and candidate-specific field retrieval

Stage 1 is [HME-NN-2A](../experiments/sign_ablation_v1/PROTOCOL.md): thirty new
seeds, current HME, a one-expression signed-similarity variant retaining the
field bias, and signed NN. [All results](../experiments/sign_ablation_v1/REPORT.md)
are now published without deviations. The sign change added 9.79 percentage
points in the primary condition. Signed HME minus NN was +0.83 points, with a
90% interval [0.08, 1.56]: noninferiority within one point is supported, while
the primary equivalence criterion within plus or minus one point is not met.
The 95% interval [-0.05, 1.69] does not establish superiority. The public
registration preceded execution; the package's default engine is unchanged.

Stage 2 is [HME-NN-2B](../experiments/field_retrieval_v1/REPORT.md): thirty new
seeds, five overlap layouts, matched signed/absolute NN, candidate-specific
field-only and hybrid retrieval, permuted-field and shared-position controls,
antipodal stress, and newly measured cached/uncached costs. Its preregistration
preceded execution and all seeds completed without deviations. At the primary
50%-overlap, native-query, sigma-1 condition, signed NN scored 52.03%, hybrid
50.29% and field-only 24.04%. Hybrid minus NN was -1.74 points (95% interval
[-2.42, -1.09]); the +2-point practical-gain criterion failed. All structural
controls passed. Cached hybrid used 9.34 times the accounted storage and 4.21
times the online query latency of matched-output NN at the primary layout.
[Design requirements](FIELD_RETRIEVAL_DESIGN.md) preserve the rationale.
A polarity-preserving encoder is a separate future experiment and is not
triggered automatically: the registered Stage 3 accuracy gate did not pass.

## Retrieval comparison

Freeze datasets, encoding, query corruption, splits, seeds, candidate counts, and primary metrics before inspecting test results. Include:

1. Exact nearest-neighbor search over the same processed item vectors. Report conventional cosine and HME's absolute normalized inner product separately where they differ.
2. A ledger-only control with the same spatial and metadata information available to HME.
3. HME with its default ranker, then field-only and ledger-only ablations.
4. A specified HRR/VSA baseline with explicit bind/unbind operations and dimensions.

Give all arms identical queries and side information. A supplied target position can leak identity; use co-located items or an independently generated noisy location channel. Charge retained payloads, patterns, graph records, and index overhead against the memory budget. Match preprocessing, including windowing/resampling, or explicitly ablate it.

Sweep query noise, number of stored items, vector dimension, field overlap, and out-of-distribution queries. Measure top-1/top-k accuracy, false matches, rejection coverage, latency, and total storage with uncertainty intervals across independent seeds. Add approximate indexes such as HNSW only after an exact-search reference establishes the recall/latency tradeoff.

An advantage claim fails if it disappears under equal side information and memory budgets, or if uncertainty does not support the preregistered minimum effect.

## Probability calibration

Define the event first: “the selected artifact is the intended target.” Include queries with no stored target. Split by underlying item or task so noisy copies of one item cannot leak across fitting and test sets.

Fit a score-to-probability mapping on training/calibration data only. Freeze it before the held-out test. Raw similarity is not automatically a probability. Report a reliability diagram of **predicted correctness probability versus observed correctness**, Brier score, and ECE with the binning rule and sample counts. Stratify by noise, candidate count, and distribution shift rather than relying only on a pooled metric.

Calibrate rejection thresholds independently of optional salience. A high ranking score, successful self-test, or retained top hit is not calibration evidence.
