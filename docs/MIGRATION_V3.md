# Migration to standalone HME 3

Version 3 separates the memory core from the QOFT/QOSMOS runtime. It changes the package name, imports, API vocabulary, and serialized identity schema. Existing v2.2 artifact IDs must not be relabeled as v3 IDs.

| Previous API | Standalone API |
|---|---|
| `qosmos-hme` package/command | `holographic-memory-engine` package; `hme` command |
| `qosmos_hme_engine` module | `hme_engine` module |
| `QOSMOSHMEEngine` / memory methods of `QOSMOSCoreHME` | `HMEEngine` |
| `glyph="Σ◯"` | `operation="write"` (default) |
| `observer_weight` | `write_weight` |
| `recursive_factor` | `strength` |
| `qmesh`, `QMesh` | `lineage`, `LineageGraph` |
| `confidence` | `relevance_score` (same uncalibrated base score) |
| `collapse_salience` on a retrieval hit | `salience` |
| `metadata["c_psi"]` | `metadata["write_salience"]` supplied by the caller |
| Salience fields on `CollapseConfig` | `SalienceConfig` |
| `enable_inscription_rejection` | `enable_salience_rejection` |
| `LOW_INSCRIPTION_SALIENCE` | `LOW_WRITE_SALIENCE` |

Memory fields, processed vectors, derived patterns, and ranking formulas are retained. New IDs include `schema="hme-v3"` and plain operation labels. Re-encode from original payloads to create v3 records; keep an external old-ID/new-ID mapping if needed. There is no automatic snapshot migration.

Framework state, collapse dynamics, glyph validation, core binding, SFD integration, and framework animation are absent from the standalone runtime. Their exact previous implementation, tests, evidence, skill, and experimental harness remain in [the v2.2 archive](../archive/README.md). Importing or installing HME 3 does not load that archive.

The old C0–C7 harness still targets its frozen v2.2 source. Porting it would require a newly versioned protocol and pins; historical results have not been silently reassigned to v3.
