# QOSMOS Holographic Memory Engine (HME)

> Publicly viewable, proprietary QOFT/QOSMOS research repository. Typed Realization / DEVELOP. Canonical weight: none.

![QOSMOS HME symbolic overlay](assets/qosmos_hme_symbolic_overlay.gif)

## What this repository contains

This repository isolates the current HME implementation from a mixed July 2026 archive whose surrounding QOFT/QOSMOS material includes superseded generations. The active engine is the later operator-conformance source, preserved byte-for-byte at `qosmos_hme_engine.py`.

HME is a **hybrid field-plus-ledger memory realization**:

- a complex 2D field stores superposed reconstructive patterns;
- deterministic SHA-256-derived encodings make replay and comparison stable;
- an artifact ledger retains identity, provenance, payload hashes, pattern hashes, glyphs, positions, and gains;
- QMesh records memory/collapse lineage;
- ranked retrieval combines position, query, and pattern similarity;
- Ψmeta telemetry is emitted before the realization-local Λψ predicate;
- W(t) is a visualization/diagnostic projection, not a canonical physical coordinate.

Artifact identity retrieval is **not field-only**. The field can retain a decoded surface when the ledger is removed, while exact artifact identification depends on the ledger.

## Operator ownership in the active realization

| Construct | Realization role |
|---|---|
| `Ψmeta` | pre-collapse telemetry |
| `Λψ` | collapse / projection event |
| `Σ◯` | consolidation and durable HME write |
| `Θλ` | retrieval / recall or replay-plan record |
| `ApplyReplay` | explicit state mutation after retrieval |
| `Π↺` | recurrence and ordered lineage |

The numerical HME algorithms were not changed by the semantic conformance patch. See `docs/OPERATOR_CONFORMANCE_PATCH.md`.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[test,visual,sfd]"

python qosmos_hme_engine.py --self-test
pytest -q
python tests/hme_independent_audit.py \
  --engine ./qosmos_hme_engine.py \
  --output outputs/hme_audit.json
```

Minimal use:

```python
from qosmos_hme_engine import QOSMOSCoreHME

hme = QOSMOSCoreHME(memory_size=64, encoding_resolution=16, seed=7)
artifact = hme.encode_memory(
    [0.1, 0.4, 0.9, 0.2],
    position=(20, 22),
    glyph="Σ◯",
)
receipt = hme.retrieve_memory((20, 22), query=[0.1, 0.4, 0.9, 0.2])
print(artifact.artifact_id, receipt.confidence)
```

## Verified ingest baseline

Active engine source:

```text
SHA-256  f81fb49e265d83f5206220584dfc6cabf28aeee5266aca33654182be1549c080
```

Preserved pre-conformance source:

```text
SHA-256  6780f974db55380fb4841d3b35c135be10eac8e0c79bc55ff7ff349138febaa6
```

The focused ingest reproduced the supplied SFD → HME bridge receipt, including:

```text
signature hash   7fef693477ffaf55104f12f25be9b91b72a8ab8e4aed8d13c4c3604fa5719ce9
trajectory hash  e90921fbd2fd990efab3b684249de68a28e7186e8fc226d2f3ca3a4038e8f5db
artifact ID      d902825c52772941b345
retrieval score  0.9307851800354882
write glyph      Σ◯
```

The independent audit reproduced deterministic artifacts, exact linear superposition reconstruction, and the following numeric top-1 results:

| Gaussian query noise σ | Correct top-1 |
|---:|---:|
| `0.00–0.25` | `128 / 128` |
| `0.50` | `119 / 128` |
| `1.00` | `59 / 128` |

Full evidence is under `evidence/`; provenance and scope are recorded in `docs/HME_INGEST_MANIFEST.md`.

## Important limitation

The current `confidence` value is the highest available retrieval score, not a calibrated probability and not a rejection decision. An unrelated query received a score near `0.733` during audit. Do not interpret every top-ranked result as a valid identity match. A calibrated threshold or explicit `NO_MATCH` policy remains open.

## Repository boundaries

Included:

- current HME/QMesh/collapse-layer engine;
- current SFD → HME bridge module and deterministic example;
- HME-specific audit harness and evidence;
- current operator-typing governance references;
- pre-conformance HME source as provenance only.

Excluded:

- obsolete canon generations;
- T-01 and unrelated experiment packages;
- broad Visual World claims and generated output sets;
- codec probes, toy agents, caches, and Finder metadata.

## Status and rights

This is a publicly viewable proprietary research repository, not an open-source project. Copyright is retained and all rights are reserved; see [`LICENSE`](LICENSE). Except for the limited platform rights arising under GitHub's Terms of Service, no permission is granted to copy, modify, redistribute, sublicense, sell, or create derivative works without prior written permission, except where applicable law expressly permits otherwise.

Implementation conformance does not validate QOFT as physics, establish consciousness, or promote this realization into canon.

## Contribution policy

This is a closed-source, owner-maintained repository. External contributions are not accepted. Public users may fork the repository or propose changes through GitHub, but those actions cannot alter this repository or its `main` branch unless the owner explicitly accepts and merges them. See [`CONTRIBUTING.md`](CONTRIBUTING.md).
