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

Version 3.0 moved state dynamics, projections, integration and animation into the archive. Version 3.1 restores the numerical mechanisms through optional plain-language modules: `hme_runtime` and `hme_dynamics`. Their exact previous implementation, tests, evidence, skill, and experimental harness remain in [the v2.2 archive](../archive/README.md). Importing or installing HME 3 does not load that archive.

| Archived runtime API | Optional 3.1 API |
|---|---|
| `QOSMOSHMEEngine` | `hme_runtime.FieldRuntime` |
| `QOSMOSCoreHME` / `step_core` | `hme_runtime.AgentRuntime` / `step_symbol` |
| `psi_field`, `set_psi_field`, `inject_psi` | `state_field`, `set_state_field`, `inject_state` |
| `W()` | `project()` |
| `CollapseConfig` | `EventConfig` for field events; `SalienceConfig` for memory weighting/ranking |
| `lambda_c`, `kappa_damp` | `threshold`, `entropy_damping` |
| `collapse_override`, `collapse_event` | `event_override`, `field_event` |
| `gamma_mag`, `reflex_conf`, `c_psi` | `state_change_norm`, `projection_stability`, `write_salience` |
| `SymbolicFieldDynamicsEngine` / `SymbolicFieldConfig` | `hme_dynamics.FieldDynamics` / `DynamicsConfig` |

The [runtime guide](RUNTIME.md) documents adapters, optional dependencies and tick order. Framework auto-imports and historical snapshot parsers remain archived. Runtime telemetry uses `hme-runtime-v1`; simulation records use `hme-dynamics-v1`. The memory core and `hme-v3` schema are unchanged from 3.0. Numeric parity does not imply identical serialized metadata, event IDs or renamed string inputs.

The old C0–C7 harness still targets its frozen v2.2 source. Porting it would require a newly versioned protocol and pins; historical results have not been silently reassigned to v3.
