# HME architecture

Classification:

- Type: Typed Realization
- Status: DEVELOP
- Canonical weight: none
- Primary claim: a deterministic hybrid field-plus-ledger memory implementation with explicit provenance and auditable retrieval
- Compatible with: qoft-qosmos Kernel v1.1 DEVELOP candidate through an
  explicit Ψmeta_post adapter; the candidate remains pending adoption

## Data path

```
payload or symbol
  → deterministic vectorization
  → FFT-derived complex pattern
  → boundary-safe placement into the HME field
  → HMEArtifact ledger record
  → QMesh memory node / lineage edge
```

Retrieval:

```
position + optional query
  → local field decode
  → candidate artifacts from the ledger
  → distance score + query score + pattern score
  → ranked HMERetrieval receipt
```

Runtime overlay (HME, realization-local):

```
ψ input
  → W(t) diagnostic projection
  → compute Ψmeta_pre diagnostic fields
  → realization-local collapse predicate
  → optional Λψ projection
  → finalize collapse_triggered (same HME tick record)
  → explicit adapter emits Ψmeta_post if pairing with the qoft-qosmos candidate
  → optional Σ◯ HME write
  → QMesh lineage + append-only event record
```

Kernel QOFT tick is owned by `qoft-qosmos` and is not this overlay:

```
Observe → Πᴽ → Φ → Γ → ⊕ → ρ_assess → Λψ? → Ψmeta_post → Σ◯/Θλ → Π↺
```

## Pattern construction

Each payload is resampled to `encoding_resolution`, optionally Hann-windowed,
normalized, FFT’d, outer-producted in the spectral domain, then IFFT2’d into
a complex patch. The patch is gain-scaled (`recursive_factor * observer_weight`)
and added into a bounded spatial window of the field. Field decay, if set,
applies before the write.

## Records

`HMEArtifact`: artifact_id, t, tag, glyph, position, gain, observer_weight,
payload_size, payload_hash, pattern_hash, metadata.

`HMERetrieval`: position, radius, window, decoded_surface, decoded_vector,
confidence (top score), hits[].

`PsiMetaFrame`: run_id, step, phase, rho, phi_energy, gamma_mag, reflex_conf,
entropy, dS, drift, stable, collapse_triggered, tags, c_psi, scalars,
slot (`pre` | `post`).

`CollapseLayer`: event_id, step, center, radius, score, threshold, mode, glyph
(Λψ), pre_hash, post_hash, reason.

## Collapse (implementation-local)

```
C(ψ) = Φ / max(ρ, ρ_min) − κ_damp · dS
ρ_min = 1e-6
collapse iff C(ψ) > λ_c
```

C(ψ) and W(t) are Tier 2 runtime metrics, not glyph operators.

Hysteresis prevents chatter: after firing, re-arm only when C(ψ) < λ_c − 0.08.
Cooldown default 2 steps. Mode: localized phase-lock + magnitude quantization
inside a Gaussian mask around argmax |W|.

Φ, ρ, dS, κ_damp, and λ_c are implementation quantities. Their use does not
establish universal QOFT constants or physical collapse.

## Evidence (reported public audit, 2026-08-23)

These reported results are linked to the repository evidence and were not
rerun for this skill-packaging change.

- Deterministic artifacts and exact linear superposition reconstruction: pass
- Top-1 identity under Gaussian query noise:
  - σ 0.00–0.25 → 128 / 128
  - σ 0.50 → 119 / 128
  - σ 1.00 → 59 / 128
- Unrelated query can still score ~0.733. Do not treat top-1 as NO_MATCH-gated.

Repo: https://github.com/donaldtuttle/HME

Audit record: https://github.com/donaldtuttle/HME/blob/main/evidence/hme_independent_audit_2026-08-23.json
