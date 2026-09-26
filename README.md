# Holographic Memory Engine (HME)

[![Tests](https://github.com/donaldtuttle/HME/actions/workflows/test.yml/badge.svg)](https://github.com/donaldtuttle/HME/actions/workflows/test.yml)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![Version 3.1.0](https://img.shields.io/badge/version-3.1.0-2563EB)
![Status: alpha](https://img.shields.io/badge/status-alpha-F59E0B)

HME is a standalone experimental memory engine that combines **complex-valued pattern storage, an artifact ledger, and similarity-ranked retrieval**. It runs on Python and NumPy.

Use it to investigate how overlapping stored patterns, query noise, spatial cues, and retained item records affect recall. For example, store a set of numeric sensor signatures, query with a noisy signature, and inspect both the ranked matches and the contribution of each scoring component. Field-only and ledger-only ablations help identify what actually produced the match.

## Quick start

```bash
git clone https://github.com/donaldtuttle/HME.git
cd HME
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[test]"
hme --self-test
python -m pytest -q
```

```python
from hme_engine import HMEEngine

memory = HMEEngine(memory_size=64, encoding_resolution=16)
item = memory.encode_memory(
    [0.1, 0.4, 0.9, 0.2],
    position=(20, 22),
    tag="sensor-reading-001",
    metadata={"source": "sensor-A"},
)
result = memory.retrieve_memory(
    (20, 22), query=[0.12, 0.39, 0.88, 0.21], top_k=1,
)
print(result.hits[0].artifact_id == item.artifact_id)
print(result.relevance_score)  # Ranking score, not a probability
print(memory.lineage.to_dict())
```

Strings are also accepted. They map deterministically to random vectors using SHA-256; similar wording does not imply similar vectors. For semantic text retrieval, supply externally computed embeddings and evaluate the resulting system.

## What runs

| Component | Current implementation |
|---|---|
| Encoding | Resample a numeric item, apply an optional Hann window, normalize, and construct a 2D pattern from an FFT spectral outer product |
| Storage | Add a weighted pattern to a bounded patch of a complex-valued grid |
| Ledger | Retain processed item vectors, patterns, hashes, positions, operation labels, and metadata, up to a configured record limit |
| Retrieval | Rank retained items using spatial proximity, absolute normalized inner-product similarity, and pattern correlation with the stored field |
| Reconstruction | Inverse FFT of a field window; a separate decoded vector is a weighted average of retained item vectors |
| Lineage | Record insertion order and artifact metadata in an in-memory graph |
| Optional salience | Write weighting, eligible-candidate reranking, and low-salience rejection; disabled by default; values supplied by the caller or the optional field runtime |
| Optional field runtime | Evolving state, phase projection, state-derived write salience, phase-lock events, telemetry, lineage and animation |
| Optional spatial dynamics | Seeded diffusion, damping, periodic drive, ablations and spectral signatures |

The artifact ledger is necessary for exact identity retrieval. The graph is not cryptographically chained, and records can be evicted. See [Architecture](docs/ARCHITECTURE.md) for the algorithm and identity contract.

## Evolving fields

Version 3.1 restores the numerical runtime removed during the 3.0 extraction,
under plain names and through optional imports. Use `FieldRuntime` for field
ticks, or `AgentRuntime` for symbol-driven ticks with explicit adapters:

```python
from hme_engine import SalienceConfig
from hme_runtime import AgentRuntime

runtime = AgentRuntime(
    salience_config=SalienceConfig(influence_write_gain=True), seed=7,
)
tick = runtime.step_symbol("sensor-update", position=(20, 22))
print(tick.meta.write_salience)  # Calculated from field state before the write
print(tick.meta.event_triggered)
```

`hme_dynamics.FieldDynamics` restores spatial diffusion and the field-to-memory
signature bridge. Run `python examples/runtime_demo.py` for an example using
only NumPy. Install `.[dynamics]` for text rasterization or `.[visualization]`
for plots and GIF export. The [runtime guide](docs/RUNTIME.md) explains update
order, adapters, switches and the restoration boundary.

## Interactive browser demo

[HME Plate](demos/hme-plate/README.md) provides a local browser instrument for
the released field-plus-ledger model. Place writes and queries, inspect score
components, and erase the field or ledger independently. It runs entirely in
the browser, with a relative static build suitable for a repository subpath.
The port has numerical and DOM regression checks; rendered desktop/mobile
verification remains pending. It does not visualize consolidation or SAL-1,
and its probe is separate from published experiments. See the
[verification record](demos/hme-plate/verification.md).

## Relationship to established work

Holographic associative memory and **Holographic Reduced Representations (HRR)** are established research areas within the broader **Vector Symbolic Architecture (VSA)** literature. They provide useful reference designs and benchmarks for HME.

HME currently uses spatial FFT-pattern superposition. Standard HRR uses circular-convolution binding and corresponding retrieval operations. HME does not yet implement that bind/unbind algebra. [Related work](docs/RELATED_WORK.md) records the distinction and primary references.

## Raw-input retrieval check

The [HME-NN-3 follow-up](experiments/raw_vector_baseline_v1/REPORT.md) separates
raw cosine NN from the earlier matched-processed-vector baseline. Its protocol
and evaluator were published before thirty fixed evaluation seeds were run.
All 120 seed/noise cells completed, using 128 Gaussian items of dimension 16
at one shared position.

| Method | Top-1 at noise sigma 0.5 | Top-1 at noise sigma 1.0 |
|---|---:|---:|
| Raw signed-cosine NN | 99.43% | 74.11% |
| Default HME | 92.14% | 42.21% |
| HME with Hann window disabled | 99.01% | 65.65% |
| Experimental no-window, signed HME | 99.32% | 73.93% |

Disabling the window recovered 73.5% of the default-to-raw-NN high-noise gap
(a descriptive ratio, not a causal attribution). Applying the window to queries
too made HME worse: 28.78% at sigma 1.0. The no-window signed variant differed
from raw NN by -0.18 percentage points (95% interval [-0.57, +0.21]); this study
does not establish equivalence or superiority. The field-erased no-window arm
exactly reproduced absolute-cosine rankings for every evaluated query.

For numeric-vector experiments, the existing opt-out is explicit:

```python
from hme_engine import HMEConfig, HMEEngine
memory = HMEEngine(hme_config=HMEConfig(use_hann_window=False))
```

This does not switch to signed retrieval. The signed variant is an experimental
scoring ablation, not the production API. **The pinned storage component and its
Hann-on default remain unchanged** to preserve earlier results and compatibility;
a default change needs a versioned migration. For this tested identity-retrieval
workload, raw signed-cosine NN remains the reference choice. See the
[review response](docs/REVIEW_2026_09_25.md) for fixes and decision boundaries.

## Evidence and limitations

The new [HME-REC-1 reconstruction study](experiments/reconstruction_v1/REPORT.md)
tests recovery of missing coordinates in unseen correlated signals, with NN copying,
weighted blending, a direct second-moment control, identity checks and measured costs.
Its field readout is experimental; the released engine and defaults are unchanged.

The next application-level study, [HME-CM-1](experiments/conversation_memory_v1/PROTOCOL.md),
now has a runnable Ollama harness for project decisions, corrections, absent
information, project separation and task resumption. It compares a rolling
summary, full-dimensional semantic NN, projected NN and HME's experimental
hybrid. **No real-model outcomes are available yet.** The implementation passed
development checks; execution awaits a local reader/embedding runtime and its
published model pins. [Local run instructions](experiments/conversation_memory_v1/RUN_LOCAL.md)
include the required preregistration step. This is an independent synthetic QA
study, not a LongMemEval result or an encoder redesign.

The earlier field experiment, [HME-NN-2B](experiments/field_retrieval_v1/REPORT.md),
gave the field a query-dependent, candidate-specific readout and still found a
negative primary result. Thirty new seeds covered five overlap layouts, four
noise levels, two preprocessing modes and a separate antipodal stress set.
The protocol and implementation were published before evaluation.

At the registered primary condition (128 items, dimension 16, 50% adjacent-patch
overlap, native queries and noise sigma 1.0):

| Experimental retrieval arm | Mean top-1 accuracy |
|---|---:|
| Signed cosine NN | 52.03% |
| Signed cosine plus candidate-specific field readout | 50.29% |
| Field readout plus position-to-ID map | 24.04% |

Hybrid minus signed NN was **-1.74 percentage points**, with a paired 95% interval
of **[-2.42, -1.09]**. The registered requirement was a lower endpoint above +2
points. Isolated-patch and shared-position controls reproduced their predicted
NN rankings; all polarity and cache controls passed. Every registered seed and
condition completed without deviations. The accuracy gate for proceeding
automatically to a separate encoder redesign was not met.

At this task size, the cached hybrid retained **9.34 times** NN's accounted
storage and took **4.21 times** its query time. The uncached hybrid took 29.35
times NN's query time. These are newly measured, compact experimental search
snapshots returning indices and scores; the older public API's decoded-output
workload is absent from every arm. All arms retain the same provenance records
and fit a common 4 MiB maximum allowance. The report publishes actual bytes,
cache construction/discard times, raw observations and all secondary results.

The first **preregistered matched-processed-vector comparison found a negative result**.
[HME-NN-1](experiments/nn_baseline_v1/REPORT.md) froze its protocol and evaluator
on GitHub before running ten new seeds, with 128 items, dimension 16, matched
inputs and preprocessing, identical provenance information, and a common 4 MiB
persistent-storage cap.

At the primary high-noise condition (sigma 1.0, native query preprocessing):

| Method | Mean top-1 accuracy |
|---|---:|
| Current HME | 47.73% |
| Exact signed-cosine nearest neighbors | 57.27% |

HME's paired difference was **-9.53 percentage points**, with a 95% seed-bootstrap
interval of **[-10.70, -8.28]**. The registered requirement was a lower interval
endpoint above +2 points. HME used **4.48 times** the accounted persistent storage.
Its public retrieval API was **68.9 times** slower by the median paired latency
ratio on this host, although HME also constructs decoded outputs that NN does not.
Erasing the field gave the same rankings as absolute-cosine NN; the full field's
primary-condition gain over that control was +0.70 points, with an interval
crossing zero. No reliable field benefit was established there.

**For this tested synthetic identity-retrieval task, use exact cosine NN with the
same provenance records.** HME remains an experimental system for studying field
storage and retrieval. This comparison does not settle other loads, dimensions,
spatial cues, semantic data or optional runtime policies. The report includes
all registered conditions, raw ranks, storage and timing observations, and the
frozen reproduction command. All ten seeds completed without deviations.

The subsequent [HME-NN-2A sign ablation](experiments/sign_ablation_v1/REPORT.md)
preregistered thirty fresh seeds and a **plus or minus one percentage point
equivalence margin**. Changing only the query-similarity sign, while retaining
the field bias, produced the following primary high-noise accuracies:

| Arm | Mean top-1 accuracy |
|---|---:|
| Current HME (absolute similarity) | 44.01% |
| Experimental HME (signed similarity) | 53.80% |
| Exact signed-cosine NN | 52.97% |

The sign change improved HME by **9.79 points** (95% interval [8.85, 10.73]).
Signed HME minus NN was **+0.83 points**, with a 90% interval [0.08, 1.56] and a
95% interval [-0.05, 1.69]. **Noninferiority within one point is supported;
equivalence within plus or minus one point is not established**, because the
90% interval extends above +1. The 95% interval also does not establish superiority.
The secondary symmetric-preprocessing, high-noise condition still favored NN
by 1.33 points (descriptive 95% interval [0.70, 2.01]).

All thirty seeds completed without deviations. Costs were measured again:
signed HME's median accounted storage was 834,232 bytes versus NN's 186,230;
its median paired API latency ratio was 70.4 times, with the same decoded-output
qualification described above. The signed variant is experimental; the default
engine remains unchanged. That stage had **109 passing tests**, and Stage 2 had
**117**. The active suite had **128** after conversation-harness development
checks and now has **138** after raw-baseline and direct-checkout regression tests. Candidate-specific field
retrieval is evaluated in HME-NN-2B above; its
[design rationale](docs/FIELD_RETRIEVAL_DESIGN.md) is retained.

The extraction preserves the earlier memory core's numerical encoding and ranking, checked against the archived implementation under identical inputs. The `hme-v3` schema deliberately changes field names and artifact IDs. [Migration](docs/MIGRATION_V3.md) describes the boundary.

The [current v3.1 results](evidence/current_release_v3_1.json) come from a fresh
run against source commit `935b0d0`, with exact engine/harness hashes recorded.
All **94 active tests** passed. The **11 archived tests** also passed, separately
labelled as v2.2 preservation checks.

The current memory core's retrieval sweep uses five preselected seeds, 128
Gaussian item vectors per seed, and the same position for all items:

| Query noise sigma | Correct / total | Mean top-1 accuracy |
|---|---:|---:|
| 0, 0.05, 0.10, 0.25 (each) | 640 / 640 | 100% |
| 0.50 | 596 / 640 | 93.1% |
| 1.00 | 282 / 640 | 44.1% |

Raw runs and approximate intervals across seeds are included in the report.
Twenty current-runtime runs also record per-tick salience, stored gains, events,
state hashes and exact-query outcomes. These are functional observations; the
enabled write gains saturate at their ceiling under this drive. They do not
establish selective prioritization or comparative retrieval advantage.

The [evidence index](docs/EVIDENCE.md) distinguishes current-release results,
the [3.1 restoration checks](evidence/runtime_restoration_validation.json),
the preserved [3.0 extraction validation](evidence/standalone_validation.json)
and [3.0 retrieval audit](evidence/hme_audit_v3.json), and the v2.2 archive.
Older results remain available under their original source pins.

Reproduce the current-release bundle (install `.[test,legacy-test,visualization]`),
or run the smaller single-seed audit:

```bash
python scripts/collect_current_evidence.py --output outputs/current_release_v3_1.json
python tests/hme_independent_audit.py \
  --engine ./hme_engine.py --output outputs/hme_audit.json
```

`relevance_score` is the selected hit's base score, **not calibrated confidence**. A high score can accompany an unrelated query. `MATCH` means a candidate passed the configured relevance threshold; it does not certify that the identity is correct. The default threshold is zero.

Comparative retrieval advantage was not supported by the first registered NN
comparison or the candidate-specific field experiment. The sign ablation
supported primary-condition noninferiority, with equivalence and superiority
unresolved. Calibrated probabilities and production persistence remain
unestablished. The [evaluation plan](docs/EVALUATION_PLAN.md) tracks the completed
comparison and remaining load/dimension sweeps, held-out calibration and HRR
comparisons. [Known limitations](docs/KNOWN_LIMITATIONS.md) lists current boundaries.

## Field-only consolidation (DEVELOP)

The opt-in [consolidation adapter](docs/CONSOLIDATION.md) can discard its owned
records, payload/pattern caches and lineage while preserving the active FFT patch.
Consolidation releases the unused full grid; later writes remain patch-only.
The adapter defaults to Hann off and refuses reconstruction when Hann is on.
Fixed-width weight metadata supports weighted
numerical reconstruction and a complete field-only checkpoint. This is Step-0
invariant validation, not a salience, damage-tolerance or semantic-memory result.
The [study plan](experiments/consolidation_plan/README.md) separates those questions.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Optional field runtime](docs/RUNTIME.md)
- [Reproducibility and source pins](docs/REPRODUCIBILITY.md)
- [Evidence by version](docs/EVIDENCE.md)
- [Related work](docs/RELATED_WORK.md)
- [Evaluation plan](docs/EVALUATION_PLAN.md)
- [Version 3 migration](docs/MIGRATION_V3.md)
- [Portable HME agent instructions](skills/hme/SKILL.md)
- [Historical v2.2 snapshot](archive/README.md)

## Rights and maintenance

HME is source-available proprietary software. The [license](LICENSE) permits local installation and execution of unmodified copies for non-commercial evaluation, testing, and reproduction of published results. Other rights are reserved.

The repository is owner-maintained. Reproducibility reports and defect notices are welcome through GitHub Issues; see [Contributing](CONTRIBUTING.md).
