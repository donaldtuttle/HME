# HME Archive Ingest Manifest

**Archive:** `QOFT QOSMOS HME JULY2026.zip`  
**Archive SHA-256:** `6a147099bbbf4fa859a5e1378ba3929ae4cf45eb78acc89dfd9d784cec7a6776`  
**Ingest date:** 2026-08-23  
**Scope:** HME/QMesh, SFD→HME bridge, HME-specific tests, provenance, and code-derived HME evidence only.  
**Classification:** Typed Realization / DEVELOP. Canonical weight: none.

## 1. Extraction integrity

- ZIP central directory: 119 entries.
- CRC test: PASS, no bad member.
- Extracted: 59 ordinary files.
- Ignored: 59 `__MACOSX` / AppleDouble metadata entries.
- Unsafe absolute paths, traversal paths, duplicate names, and symlinks: none detected.

## 2. Active HME source selection

### Active candidate

`QOSMOS_visual_world_engine_v0.1.1_SOURCE.zip/qosmos_visual_world_engine_v0_1_1/qosmos_world/qosmos_hme_engine.py`

- SHA-256: `f81fb49e265d83f5206220584dfc6cabf28aeee5266aca33654182be1549c080`
- Size: 89,079 bytes.
- Reason: this is the later semantic-conformance version. It assigns durable write/consolidation to `Σ◯`, retrieval/replay records to `Θλ`, explicit state mutation to `ApplyReplay`, and recurrence/lineage to `Π↺`.

### Preserved legacy source

Top-level `qosmos_hme_engine.py`

- SHA-256: `6780f974db55380fb4841d3b35c135be10eac8e0c79bc55ff7ff349138febaa6`
- Size: 88,955 bytes.
- Status: original pre-conformance source, preserved as provenance.
- Difference from active candidate: semantic defaults and QMesh relationship labels only; numerical HME algorithms are unchanged.

## 3. HME mechanism ingested

The implementation is a hybrid memory realization containing:

- a complex 2D HME field;
- deterministic SHA-256-derived symbol/vector encoding;
- FFT-based pattern construction and boundary-safe field placement;
- an artifact ledger with payload hashes, pattern hashes, glyphs, positions, gains, and metadata;
- query-aware ranked retrieval;
- QMesh memory/collapse lineage;
- pre-collapse `Ψmeta` telemetry;
- realization-local collapse metric `C(ψ) = Φ/ρ − κ_damp·dS`;
- append-only collapse records;
- `W(t)` as a visualization/diagnostic projection;
- legacy HME/QMesh snapshot import;
- SFD signature conversion and commit into HME.

The current realization is not a field-only associative memory. Artifact identity ranking depends on the ledger, while the field supplies reconstructive surface information.

## 4. Verification executed during ingest

### Syntax and built-in tests

- Original HME source: `py_compile` PASS; built-in self-test PASS.
- Patched HME source: `py_compile` PASS; built-in self-test PASS.
- Visual World integration suite: `8 passed` under Python 3.13.5 / NumPy 2.3.5.
- Symbolic Field Dynamics v1.0: built-in self-test PASS.

### SFD → HME bridge reproduction

The supplied bridge protocol was rerun against the patched HME source. It reproduced the supplied receipt exactly on the load-bearing fields:

- SFD signature hash: `7fef693477ffaf55104f12f25be9b91b72a8ab8e4aed8d13c4c3604fa5719ce9`
- SFD trajectory hash: `e90921fbd2fd990efab3b684249de68a28e7186e8fc226d2f3ca3a4038e8f5db`
- HME artifact ID: `d902825c52772941b345`
- Payload hash: `d363f67bdd7ac2d963c7884cd1750211872314cac8b198fb8c43681c46d80b4b`
- Pattern hash: `f28f0fa635dd31ad745d096fa948791ab0e5a7bddbe3e142a414c4ed97f754b3`
- Write glyph: `Σ◯`
- Top retrieval hit: committed artifact
- Retrieval confidence: `0.9307851800354882`

### Independent HME audit

Both original and patched sources produced identical numerical audit results:

- deterministic artifacts, hashes, and field: PASS;
- exact linear superposition reconstruction: PASS;
- numeric top-1 retrieval:
  - σ = 0.00 through 0.25: 128/128;
  - σ = 0.50: 119/128;
  - σ = 1.00: 59/128;
- field erased, ledger preserved: exact artifact retrieval remained 128/128;
- ledger erased, field preserved: decoded surface remained, but artifact hit count became 0;
- partial string queries were unreliable;
- an unrelated query still received a top-score confidence of approximately 0.733, confirming that current confidence is not a calibrated probability or rejection test.

## 5. HME-specific cleanup issues for the GitHub build

1. The top-level source is legacy, while the active patched source is nested inside another package.
2. Both original and patched sources report the same internal `qosmos_hme_v2.2.0` engine identity despite different bytes.
3. `qosmos_hme_v2_2_SHA256.txt` pins the legacy source and references an absent `qosmos_hme_patch_v2_2.zip` and an absent top-level overlay PNG.
4. `hme_independent_audit.py` explicitly writes audit memories with glyph `Θλ`; this should be changed to `Σ◯` for the active realization or clearly retained as a legacy-source audit.
5. The source README title says `v0.1.1.1`, while the package, changelog, and patch report say `v0.1.1`.
6. Retrieval confidence needs explicit calibration or an `UNKNOWN / NO_MATCH` rejection policy before it can be treated as confidence in identity.
7. The GitHub README must describe the implementation as hybrid field reconstruction plus ledger-ranked provenance, not as pure field-only holographic retrieval.

## 6. Materials intentionally excluded from HME authority

Not ingested as HME authority:

- duplicate or obsolete canon packages;
- T-01 branch-lifecycle results and correction packages;
- general QOFT knowledge documents inside the archive;
- generic toy-runtime outputs;
- broad Visual World scientific claims beyond their role as HME integration evidence;
- codec-parity bait probes;
- Finder metadata.

## 7. Working baseline

For the HME GitHub, use the patched source hash `f81fb49e…` as the working implementation, preserve `6780f974…` under `legacy/`, and keep all claims scoped to this DEVELOP typed realization until a separate governance action says otherwise.
