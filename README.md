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

## Relationship to established work

Holographic associative memory and **Holographic Reduced Representations (HRR)** are established research areas within the broader **Vector Symbolic Architecture (VSA)** literature. They provide useful reference designs and benchmarks for HME.

HME currently uses spatial FFT-pattern superposition. Standard HRR uses circular-convolution binding and corresponding retrieval operations. HME does not yet implement that bind/unbind algebra. [Related work](docs/RELATED_WORK.md) records the distinction and primary references.

## Evidence and limitations

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

Comparative retrieval advantage, calibrated probabilities, and production persistence remain unestablished. [Evaluation plan](docs/EVALUATION_PLAN.md) specifies held-out calibration and comparisons with exact nearest-neighbor retrieval, metadata-matched controls, and HRR. [Known limitations](docs/KNOWN_LIMITATIONS.md) lists current boundaries.

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
