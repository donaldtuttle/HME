# Changelog — hme

## 2.2.1 — 2026-08-23

Telemetry-order alignment with the qoft-qosmos Kernel v1.1 DEVELOP candidate.

- Overlay tick: ψ input → W(t) → compute Ψmeta_pre fields → Λψ? → finalize
  HME record → Σ◯ → QMesh.
- Ψmeta_pre is realization-local diagnostic telemetry, not QOFT canon; its
  fields are computed before Λψ and its HME record is finalized after.
- Pairing: finalizing the HME pre record does not substitute for Ψmeta_post. If
  candidate-kernel compatibility is required, an explicit adapter emits
  Ψmeta_post after Λψ.
- C(ψ) and W(t) labeled as Tier 2 runtime metrics, not glyphs.
- Compatible with qoft-qosmos Kernel v1.1 and ROFT v27.3.
- Canonical weight remains none. DEVELOP typed realization.

## 2.2.0 — prior

Field + ledger, SHA-256 replay, Σ◯ default write, Θλ recall, QMesh lineage.
