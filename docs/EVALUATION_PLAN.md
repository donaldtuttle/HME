# Evaluation plan

Status: proposed work, not implemented calibration or comparative results.

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
