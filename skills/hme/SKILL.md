---
name: hme
description: Use Holographic Memory Engine for standalone numeric or symbolic item storage, similarity-ranked retrieval, artifact provenance, lineage inspection, noise tests, and field-versus-ledger ablations with the hme_engine Python API.
---

# Holographic Memory Engine

Use the standalone `hme_engine` module and `HMEEngine` class. Require Python 3.10+ and NumPy. Respect the repository's proprietary evaluation license; see `LICENSE.txt`. Read [Architecture](references/architecture.md) before interpreting results.

## Run a memory task

```python
from hme_engine import HMEEngine

engine = HMEEngine(memory_size=64, encoding_resolution=16)
artifact = engine.encode_memory(
    [0.1, 0.4, 0.9, 0.2], (20, 22),
    tag="reading-001", metadata={"source": "sensor-A"},
)
result = engine.retrieve_memory((20, 22), query=[0.12, 0.39, 0.88, 0.21], top_k=1)
```

That snippet preserves the released defaults for compatibility.

## Choose the configuration by task

HME-NN-3 found that disabling the Hann window recovered 73.5% of the
default-to-raw-NN high-noise gap at sigma 1.0. Top-1 accuracy was 42.21% for
default HME, 65.65% with Hann disabled, 73.93% for the experimental no-window
signed HME arm, and 74.11% for raw signed-cosine NN. The experimental signed
no-window arm differed from raw signed NN by -0.18 percentage points with a
reported 95% interval of [-0.57, +0.21]. The observed difference stayed within
+/-0.6 pp; equivalence was not established.

- General HME exploration or compatibility with earlier results: use the default `HMEEngine(...)`.
- Numeric identity-retrieval benchmarks: use exact signed-cosine NN as the reference method; do not present default HME as the retrieval baseline.
- HME numeric experiments: consider `HMEConfig(use_hann_window=False)`. Signed HME scoring remains an experimental ablation, not a supported API option.

See the README HME-NN-3 section and the raw-vector report before running a retrieval comparison.

- Use `operation="write"` by default. Use `strength` and `write_weight` to control the stored gain.
- Inspect `result.outcome`, `result.rejected`, `result.hits`, and `result.relevance_score` together.
- Treat `relevance_score` as the selected hit's uncalibrated base score. Never report it as probability of correctness.
- Treat `MATCH` as threshold eligibility, not proof of identity. Set an evaluated `HMEConfig.relevance_threshold` for rejection experiments.
- Use `engine.lineage.to_dict()` for insertion lineage and `engine.hme.snapshot()` for field/record metadata.
- Supply numeric embeddings for semantic similarity tasks. String encoding hashes exact strings into random vectors and does not preserve paraphrase similarity.
- Use caller metadata `write_salience` with `SalienceConfig` only for explicitly requested experiments. All salience switches default off. Keep base relevance eligibility separate from reranking and salience rejection.

## Inspect or evaluate

Pin the source, environment, dimensions, seeds, and input corpus. Run `python hme_engine.py --self-test`, `python -m pytest -q`, and the repository's `tests/hme_independent_audit.py --engine ./hme_engine.py` as applicable. Distinguish a historical saved report from a rerun.

For comparisons, give all methods identical queries, preprocessing, positional information, and storage budgets, including cached vectors and patterns. Fit any probability calibration on separate data before evaluating held-out correctness.

Explain the current implementation as spatial FFT-pattern superposition plus retained-vector ranking. Do not call it standard HRR binding, field-only identity recovery, a Merkle DAG, an append-only tamper-proof ledger, or a complete restartable database.

Use `archive/v2.2/` only when reproducing that historical version. Keep its schema, artifact IDs, pins, and results separate from `hme-v3`. No companion framework skill is required.
