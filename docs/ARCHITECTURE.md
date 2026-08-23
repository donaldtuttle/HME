# HME Architecture

## Classification

- **Type:** Typed Realization
- **Status:** DEVELOP
- **Canonical weight:** none
- **Primary claim:** a deterministic hybrid field-plus-ledger memory implementation with explicit provenance and auditable retrieval

## Data path

```text
payload or symbol
  → deterministic vectorization
  → FFT-derived complex pattern
  → boundary-safe placement into the HME field
  → HMEArtifact ledger record
  → QMesh memory node / lineage edge
```

Retrieval:

```text
position + optional query
  → local field decode
  → candidate artifacts from the ledger
  → distance score + query score + pattern score
  → ranked HMERetrieval receipt
```

Runtime overlay:

```text
ψ input
  → W(t) diagnostic projection
  → Ψmeta telemetry
  → realization-local collapse predicate
  → optional Λψ projection
  → optional Σ◯ HME write
  → QMesh lineage + append-only event record
```

## Field versus ledger

The field and ledger preserve different behavior.

| Component retained | Behavior |
|---|---|
| field + ledger | reconstructive surface plus ranked artifact identity |
| ledger only | exact artifact ranking can remain available |
| field only | decoded surface remains, but artifact identity hits disappear |

Therefore this implementation is not evidence for pure field-only associative identity retrieval.

## Determinism

Stable JSON serialization and SHA-256-derived seeds are used for payload hashes, pattern hashes, artifact IDs, and replay comparisons. Determinism is conditional on the same implementation, dependencies, inputs, configuration, and numeric environment.

## Collapse diagnostics

The realization-local diagnostic is:

```text
C(ψ) = Φ / ρ − κ_damp·dS
collapse iff C(ψ) > λ_c
```

`Φ`, `ρ`, `dS`, `κ_damp`, and `λ_c` are implementation quantities here. Their use does not establish universal QOFT constants or physical collapse.
