---
name: hme
description: >
  Holographic Memory Engine (HME) skill for QOFT / QOSMOS. Use when encoding
  or retrieving memory, writing Σ◯ artifacts, Θλ recall, QMesh lineage,
  field-plus-ledger reconstruction, SHA-256 deterministic replay, C(ψ)
  collapse overlay, W(t) diagnostic projection, or the qosmos_hme_engine
  API. Do not treat HME as QOFT canon. Do not invent glyphs. Do not read
  confidence as a calibrated probability. Companion skill is the qoft-qosmos
  Kernel v1.1 DEVELOP candidate, pending adoption. C(ψ) and W(t) are runtime
  metrics, not glyph operators.
license: "Proprietary; see LICENSE.txt"
metadata:
  version: "2.2.1"
  author: "Donald R. Tuttle (ψᴽ-001)"
  status: "DEVELOP typed realization — canonical weight none"
  engine: "qosmos_hme_engine.py"
  standard: "agentskills.io"
  companions: "qoft-qosmos"
  compatible_with: "qoft-qosmos Kernel v1.1 DEVELOP candidate; ROFT v27.3"
---

# HME — Holographic Memory Engine

Portable Agent Skill for Claude, ChatGPT, Codex, Cursor, and any
[agentskills.io](https://agentskills.io) client.

Origin: Donald R. Tuttle | Ξ Glyphogenic Engine, ψᴽ-001

HME is a **hybrid field-plus-ledger memory realization**. It is publicly
viewable proprietary software, not open source (all rights reserved). It is a
DEVELOP typed
realization of QOFT / QOSMOS with **no canonical weight**. Mappings below
are provenance and integration compatibility, not a promotion into canon.

Companion skill: `qoft-qosmos` (Glyphogenic Calculus, Kernel v1.1 DEVELOP
candidate pending adoption). Load it explicitly for that candidate operator
firewall. The repository root v1.0 remains authoritative for Public Typed
Realization A. This file owns memory encode / retrieve / overlay ticks.

Read on demand:

- [Architecture](references/architecture.md) — field vs ledger, data path, collapse diagnostic
- [Changelog](references/changelog.md) — 2.2.0 → 2.2.1 telemetry order
- [Install](references/install.md) — Claude, ChatGPT, Codex, Projects

────────────────────────────────────────
SECTION 0 — FIREWALL
────────────────────────────────────────

1. Do not invent glyphs. Allowed operators used by this skill: Ξ, Πᴽ, Λψ,
   Σ◯, Θλ, Ωµ, Π↺, Ψmeta. The symbol ψᴽ names reflexive state produced by
   Πᴽ; it is not itself an operator glyph.
2. Do not treat HME algorithms, thresholds, or W(t) as QOFT canon.
3. Do not claim consciousness, physical collapse, or universal memory dynamics.
4. Do not read `confidence` as a calibrated probability or a rejection decision. It is the base semantic relevance of the selected hit; C(ψ)-derived salience never raises it.
5. Artifact identity is **not field-only**. Exact ID depends on the ledger.
6. Default durable-write glyph is Σ◯. Θλ is retrieval / replay, not write.
7. Λψ must not write Πᴽ / self_model.
8. Telemetry order: compute Ψmeta_pre diagnostic fields **before** the collapse
   decision, then finalize `collapse_triggered` **after** the decision on the
   same HME tick record. Ψmeta_pre / Ψmeta_post are named slots of Ψmeta, not
   new glyphs. HME pre telemetry never substitutes for a required kernel post
   frame.
9. C(ψ) and W(t) are Tier 2 runtime metrics. They are not glyph operators and not universal QOFT law.
10. If a term is not defined here, write `UNDEFINED in this document: <term>`.
11. No LaTeX. Unicode glyphs only.
12. C(ψ) may drive the collapse trigger, optional inscription/write-gain salience,
    and optional retrieval salience. It must never determine semantic match
    eligibility. `NO_MATCH` is decided solely from base relevance.
13. Anti-drift: do not infer that stronger C(ψ) means a memory is more
    semantically relevant, more accurate, more truthful, or higher-confidence.
    C(ψ)-derived salience is realization-local provenance about the originating
    collapse/inscription event only.

────────────────────────────────────────
SECTION 1 — WHAT HME IS
────────────────────────────────────────

HME combines:

- a complex 2D field of superposed reconstructive patterns (FFT outer-product)
- an artifact ledger (identity, provenance, payload hashes, pattern hashes, glyphs, positions, gains)
- QMesh lineage (memory nodes, collapse nodes, ordered edges)
- ranked retrieval (distance + query + pattern scores)
- Ψmeta telemetry and a realization-local Λψ predicate
- W(t) as a visualization / diagnostic projection, not a physical coordinate

Publicly viewable proprietary engine: `qosmos_hme_engine.py` in
https://github.com/donaldtuttle/HME

Active source pin (SHA-256):

    1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11

Determinism is conditional on the same implementation, dependencies, inputs,
configuration, and numeric environment. Seeds use SHA-256, never Python `hash()`.

────────────────────────────────────────
SECTION 2 — OPERATOR MAP (PROVENANCE ONLY)
────────────────────────────────────────

| Construct | HME role | Must not |
|---|---|---|
| Ψmeta | pre-collapse diagnostics (Ψmeta_pre); HME record finalized with collapse_triggered after Λψ | imply phenomenal self-awareness or replace a required kernel Ψmeta_post |
| Λψ | collapse / projection event with pre/post hashes | write self_model |
| Σ◯ | consolidation and durable HME write | be used as the default retrieval glyph |
| Θλ | retrieval / RecallPacket / ReplayPlan record | be the default write glyph |
| ApplyReplay | explicit state mutation after retrieval | be treated as a canonical glyph |
| Π↺ | recurrence and ordered QMesh lineage | produce ψᴽ |
| C(ψ) | implementation diagnostic Φ/ρ − κ_damp·dS | be treated as a universal constant or a glyph |
| W(t) | diagnostic projection of the field | be treated as a physical coordinate |

Default encode glyph: **Σ◯**.
Collapse-to-memory QMesh relation: **Λψ→Σ◯:consolidate**.
Memory-precedes-collapse relation: **Π↺:memory_precedes_collapse**.

────────────────────────────────────────
SECTION 3 — RUNTIME ORDER
────────────────────────────────────────

Overlay tick:

    ψ input → W(t) diagnostic → compute Ψmeta_pre fields → Λψ? → finalize HME record → Σ◯ HME write → QMesh lineage

Encode path:

    payload or symbol
      → deterministic vectorization
      → FFT-derived complex pattern
      → boundary-safe placement into the field
      → HMEArtifact ledger record
      → QMesh memory node / lineage edge

Retrieve (ordered pipeline — do not reorder):

    position + optional query
      → local field decode
      → base semantic relevance (distance + query + pattern)
      → relevance eligibility / NO_MATCH          ← gate first
      → eligible candidate set
      → optional C(ψ) salience reranking          ← headroom form only
      → best relevant hit
      → optional artifact-relative inscription rejection
      → ranked HMERetrieval receipt

Persistent vs ephemeral data ownership:

Durable (`artifact.metadata` only):

    "c_psi"          — write-time collapse diagnostic, if present

Ephemeral (`RetrievalHit` / `HMERetrieval` only):

    base_score
    collapse_salience
    final_score

Never write query-dependent scores back onto `HMEArtifact`.

Three distinct outcomes — do not conflate:

`NO_MATCH`
: No artifact passed semantic relevance. `hits = []`.

`LOW_INSCRIPTION_SALIENCE`
: A relevant artifact exists, but inscription policy rejected it on the basis of
  its originating C(ψ). Hits are retained; `rejected=True`;
  `rejection_reason` is set.

`MATCH`
: A relevant artifact exists and was not policy-rejected.

Forbidden: turning `LOW_INSCRIPTION_SALIENCE` into `NO_MATCH` or deleting the
hits under an inscription-policy rejection.

Collapse diagnostic (implementation-local, not canon):

    C(ψ) = Φ / max(ρ, ρ_min) − κ_damp · dS
    ρ_min = 1e-6
    collapse iff C(ψ) > λ_c
    hysteresis band λ_c − 0.08; cooldown_steps default 2

Default class λ_c ≈ 1.67, κ_damp ≈ 0.15 when v27 constants are absent.
Demo / test thresholds are local and must be labeled as such.

Current realization defaults (implementation settings, not HME invariants):

    write_gain_scale      = 0.25
    write_gain_floor      = 0.05
    write_gain_ceiling    = 1.5
    retrieval_weight      = 0.15
    relevance_threshold   = 0.0   (preserves prior “always return top_k”)
    rejection_threshold   = None
    influence_* flags     = False

Salience mechanisms (write-gain, retrieval salience, inscription rejection) are
optional DEVELOP switches. Before any claim that they improve HME behavior, run
the full C0–C7 ablation family and report main effects plus interactions. Until
then they remain experimental machinery with no efficacy claim.

────────────────────────────────────────
SECTION 3b — TELEMETRY ORDER NOTE
────────────────────────────────────────

HME computes Ψmeta_pre diagnostic fields before Λψ, then finalizes the same
HME tick record after the decision so `collapse_triggered` is accurate.

The qoft-qosmos Kernel v1.1 DEVELOP candidate requires Ψmeta_post after Λψ.
These are not two glyphs. They are two named slots of Ψmeta.

Finalizing the HME pre record is not a substitute for the candidate profile's
post record. If compatibility with the `qoft-qosmos` candidate tick contract is
required, an explicit adapter must also emit Ψmeta_post after Λψ.

Kernel QOFT tick (for contrast; owned by `qoft-qosmos`):

    Observe → Πᴽ → Φ → Γ → ⊕ → ρ_assess → Λψ? → Ψmeta_post → Σ◯/Θλ → Π↺

Do not silently replace the kernel tick with the HME overlay.

────────────────────────────────────────
SECTION 4 — PUBLIC API
────────────────────────────────────────

```python
from qosmos_hme_engine import QOSMOSCoreHME, QOSMOSHMEEngine, CollapseConfig

hme = QOSMOSCoreHME(memory_size=64, encoding_resolution=16, seed=7)
artifact = hme.encode_memory([0.1, 0.4, 0.9, 0.2], position=(20, 22), glyph="Σ◯")
receipt = hme.retrieve_memory((20, 22), query=[0.1, 0.4, 0.9, 0.2])
result = hme.step()          # pre fields before Λψ; HME record finalized after
```

Required behaviors when writing code:

- Seeded RNG (`numpy.random.default_rng(seed)`).
- SHA-256 for payload_hash, pattern_hash, artifact_id, field hashes.
- Unknown glyphs raise; do not create glyphs dynamically.
- `encode` / `encode_memory` default glyph is Σ◯.
- Every Λψ emits a CollapseLayer with pre_hash, post_hash, reason.
- Compute Ψmeta_pre fields before the decision; finalize `collapse_triggered`
  after. Use an explicit adapter to emit Ψmeta_post for candidate-kernel pairing.
- Tests: determinism of hashes; default write glyph is Σ◯; field vs ledger roles; collapse lineage uses `Λψ→Σ◯:consolidate`; telemetry order (pre then flag).
- Do not interpret a top-1 hit as identity without a declared base-relevance
  threshold. `NO_MATCH` is now a base-relevance outcome; C(ψ) cannot create or
  erase semantic eligibility. Reported historical audit figures below predate
  the optional salience switches and are not evidence of efficacy.

Audit record: https://github.com/donaldtuttle/HME/blob/main/evidence/hme_independent_audit_2026-08-23.json

────────────────────────────────────────
SECTION 5 — FIELD VERSUS LEDGER
────────────────────────────────────────

| Retained | Behavior |
|---|---|
| field + ledger | reconstructive surface plus ranked artifact identity |
| ledger only | exact artifact ranking can remain available |
| field only | decoded surface remains; artifact identity hits disappear |

Therefore this implementation is not evidence for pure field-only associative identity retrieval.

`.hme` public scaffold format (wave snapshots, glyph_field, entropy_trace) is a
file-format stub. The engine’s live memory is the complex field + ledger, not
that JSON alone.

────────────────────────────────────────
SECTION 6 — BEHAVIOR WHEN ASKED TO REASON
────────────────────────────────────────

If asked to “make HME canon,” refuse. Status is DEVELOP / weight none.
If asked to add a glyph, refuse and compose Σ◯, Θλ, Λψ, Π↺, Ψmeta.
If asked whether W(t) is physical, say: diagnostic projection only (Tier 2).
If asked for holographic physics, restate: FFT pattern superposition in a
complex array, plus a ledger. Structural analogy, not a physical hologram.
If asked whether HME’s tick replaces QOFT’s, say: no. Overlay vs kernel.

Pair with `qoft-qosmos` for Ξ / ⊕ / Γ typing. Do not silently redefine those operators here.
