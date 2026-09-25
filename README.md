# Holographic Memory Engine (HME)

[![Tests](https://github.com/donaldtuttle/HME/actions/workflows/test.yml/badge.svg)](https://github.com/donaldtuttle/HME/actions/workflows/test.yml)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![Version 3.0.0](https://img.shields.io/badge/version-3.0.0-2563EB)
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
| Optional salience | Caller-supplied write weighting, eligible-candidate reranking, and low-salience rejection; disabled by default |

The artifact ledger is necessary for exact identity retrieval. The graph is not cryptographically chained, and records can be evicted. See [Architecture](docs/ARCHITECTURE.md) for the algorithm and identity contract.

## Relationship to established work

Holographic associative memory and **Holographic Reduced Representations (HRR)** are established research areas within the broader **Vector Symbolic Architecture (VSA)** literature. They provide useful reference designs and benchmarks for HME.

HME currently uses spatial FFT-pattern superposition. Standard HRR uses circular-convolution binding and corresponding retrieval operations. HME does not yet implement that bind/unbind algebra. [Related work](docs/RELATED_WORK.md) records the distinction and primary references.

## Evidence and limitations

The extraction preserves the earlier memory core's numerical encoding and ranking, checked against the archived implementation under identical inputs. The `hme-v3` schema deliberately changes field names and artifact IDs. [Migration](docs/MIGRATION_V3.md) describes the boundary.

The [local validation record](evidence/standalone_validation.json) reports 21 standalone tests and 11 historical tests passing. The [v3 audit](evidence/hme_audit_v3.json) reproduces the original top-1 counts: 128/128 at noise 0–0.25, 119/128 at 0.5, and 59/128 at 1.0. These are single-seed implementation checks, not comparative performance evidence.

Run the retrieval and ablation audit:

```bash
python tests/hme_independent_audit.py \
  --engine ./hme_engine.py --output outputs/hme_audit.json
```

`relevance_score` is the selected hit's base score, **not calibrated confidence**. A high score can accompany an unrelated query. `MATCH` means a candidate passed the configured relevance threshold; it does not certify that the identity is correct. The default threshold is zero.

Comparative retrieval advantage, calibrated probabilities, and production persistence remain unestablished. [Evaluation plan](docs/EVALUATION_PLAN.md) specifies held-out calibration and comparisons with exact nearest-neighbor retrieval, metadata-matched controls, and HRR. [Known limitations](docs/KNOWN_LIMITATIONS.md) lists current boundaries.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Reproducibility and source pins](docs/REPRODUCIBILITY.md)
- [Related work](docs/RELATED_WORK.md)
- [Evaluation plan](docs/EVALUATION_PLAN.md)
- [Version 3 migration](docs/MIGRATION_V3.md)
- [Portable HME agent instructions](skills/hme/SKILL.md)
- [Historical v2.2 snapshot](archive/README.md)

## Rights and maintenance

HME is source-available proprietary software. The [license](LICENSE) permits local installation and execution of unmodified copies for non-commercial evaluation, testing, and reproduction of published results. Other rights are reserved.

The repository is owner-maintained. Reproducibility reports and defect notices are welcome through GitHub Issues; see [Contributing](CONTRIBUTING.md).
