# Candidate-specific field retrieval: requirements before registration

Status: design requirements preserved as background. The concrete Stage 2
specification is [HME-NN-2B](../experiments/field_retrieval_v1/PROTOCOL.md), whose
protocol and implementation are published before evaluation. Results are pending.
Stage 1 is the separate [sign ablation](../experiments/sign_ablation_v1/PROTOCOL.md).
The negative [HME-NN-1 result](../experiments/nn_baseline_v1/REPORT.md) remains the
evidence for the default ranker.

## Addressing and readout

Freeze the number of positions K, patch size s, grid spacing d, field dimensions,
boundary handling and items per position before execution. Use one item per
position for the main comparison and assign positions independently of content.
Query every candidate position; the query must never receive the target address.
Retain a position-to-ID map and give the same map/provenance to the NN arms.

Compare the query pattern and candidate field readout in the same representation.
Freeze precisely whether readout means a field patch, its Fourier transform or
another reconstruction, and apply the matching transformation to the query.
The existing inverse-FFT surface is not an inverse semantic-vector decoder.
Avoid accidentally applying the Hann window twice to the pattern query.

Freeze hybrid weights or fit them on a separate development split and freeze
them before evaluation. Include signed NN, absolute NN, the hybrid, and a
field-only ranker that uses only the field, query representation and identity map
for scoring. Charge all actually retained vectors, patterns, maps and caches.

## Overlap and controls

Sweep overlap. For equal square patches aligned horizontally or vertically,
pairwise overlap fraction is `max(0, 1-d/s)`; diagonal overlap is its square.
Specify whether reported overlap means this pairwise quantity or total overlap
with the union of neighbours. Hold field dimensions fixed if isolating layout
effects from storage capacity.

A field containing only the known target removes interference but its construction
uses ground truth. Treat it as an **oracle diagnostic**, not an ordinary retrieval
arm or a demonstrated lower bound. A fairer no-interference ranker compares the
query against an isolated reference for every candidate, charging that storage
or explicitly identifying it as a diagnostic reference.

Retain a shared-position negative control. Every candidate then receives the
same query-dependent field score. For a positive signed-score coefficient and
unclipped additive ranking, its ordering must match signed NN mathematically.
Implement common-offset cancellation to avoid artificial floating-point ties;
verify equality in correctness tests. Field-only scores all tie in that case.
Also consider zeroed or permuted field readouts to test whether any gain depends
on the correct field-to-candidate association rather than the additional feature.

## Polarity: the actual limitation

The current spectral outer-product encoder obeys `pattern(x) = pattern(-x)`
(and is invariant to global complex phase). That is an identifiability limit,
not a universal accuracy ceiling equal to absolute NN on arbitrary datasets.

For complete isolated patterns, normalized Frobenius correlation of this encoder
equals squared absolute normalized inner-product similarity of the corresponding
processed vectors. Under matched preprocessing and positive write weights, the
isolated-pattern ordering should therefore match absolute NN. Clipping at field
boundaries, interference and nonlinear readout changes require separate analysis.

Include balanced antipodal pairs as a structural stress set. Paired queries that
encode identically cannot identify both opposite-sign members using the current
query pattern alone; a fixed deterministic field-only ranking can be correct for
at most one member per equally weighted pair. This gives a defensible 50% ceiling
for that explicitly constructed pair-identification test, not for the main random
corpus. A hybrid loss from sign-insensitive field evidence is a directional
hypothesis to register, not a foregone conclusion.

## Costs and later encoder work

Readouts depend on the field and candidate position, so they can be cached between
writes. Report uncached query cost, cached query cost, cache storage and cache
construction/invalidation cost separately. Scanning K fixed-size readouts is
linear work in K for that implementation, but K fresh decodes per query are not
mandatory. Measure timing; do not import HME-NN-1's storage or latency ratios.

Only after Stage 2 supplies a reason to proceed should Stage 3 change encoding
to preserve polarity/phase. Give that intervention a separate protocol, fresh
evaluation data and its own costs; do not redefine Stage 2 after observing it.
