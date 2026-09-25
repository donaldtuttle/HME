# Optional field runtime

HME 3.1 restores the numerical dynamics that the 3.0 extraction moved into the
archive. Import `hme_runtime` to use them. Importing `hme_engine` alone still
loads only the memory core. No framework or archive module is imported by either
runtime module.

## Choose a component

| API | Behavior |
|---|---|
| `HMEEngine` | Explicit memory writes and ranked reads, unchanged from 3.0 |
| `FieldRuntime` | Complex state field, real diagnostic projection, state-derived write salience, threshold events, telemetry and frame history |
| `AgentRuntime` | Adds symbol injection, bounded history, activity accumulation, neighbor-transfer diagnostics and explicit host adapters |
| `FieldDynamics` | Seeded 1D spatial diffusion, damping and periodic drive; optional text-to-waveform input; spectral signatures and a memory-write bridge |

The runtime state field and the memory field are distinct arrays. The diagnostic
projection can combine them. Phase-lock events change the state field; memory
writes change the memory field. The diffusion simulator returns a trajectory;
the caller decides which states to supply to `FieldRuntime`.

## Run a field tick

```python
import numpy as np
from hme_engine import SalienceConfig
from hme_runtime import EventConfig, FieldRuntime

runtime = FieldRuntime(
    memory_size=24,
    encoding_resolution=8,
    event_config=EventConfig(threshold=1.67),
    salience_config=SalienceConfig(influence_write_gain=True),
    seed=7,
)
rng = np.random.default_rng(7)
field = rng.normal(size=(24, 24)) + 1j * rng.normal(size=(24, 24))
tick = runtime.step(
    field,
    memory_payload=[0.1, 0.4, 0.9, 0.2],
    memory_position=(12, 12),
)
print(tick.meta.write_salience)
print(tick.meta.event_triggered)
print(tick.memory_artifact.metadata["write_salience"])
result = runtime.retrieve_memory((12, 12), query=[0.1, 0.4, 0.9, 0.2])
```

Tick order is input update, measurement, event decision/application, optional
memory write, then one finalized telemetry record and optional projection frame.
Metrics in that record describe the measurement **before** the event/write;
`event_triggered` describes the actual decision. The returned projection and
recorded image are from **after** the event/write. This retains the archived
measurement order without publishing an inaccurate pre-decision event flag.

The restored write signal is:

```text
combined = state_field + memory_field
field_rms = sqrt(mean(abs(combined)**2))
coherence = magnitude-weighted phase alignment(combined)
write_salience = field_rms / max(coherence, min_coherence)
                - entropy_damping * entropy_change
```

Entropy is measured on the absolute diagnostic projection. `state_change_norm`
is the norm of the state update, not a spatial derivative or prediction error.
`projection_stability` is clipped `1 - relative_projection_drift`, not calibrated
confidence. Write salience is computed on every tick and attached to its memory
write. As before, gain weighting, retrieval reranking and low-salience rejection
are separate `SalienceConfig` switches, all off by default. Event triggering is
enabled by default and has a threshold, hysteresis and cooldown. An explicit
`event_override=True` bypasses that gate, including `enabled=False` and cooldown.

Each applied event logs the rounded pre/post state hashes and creates lineage
edges to surrounding memory writes. The local event operation combines Gaussian
spatial weighting, phase locking and magnitude quantization. These mechanisms
are restored numerical behavior; their usefulness has not been established by a
comparative benchmark.

## Agent and host adapters

`AgentRuntime.step_symbol("sample")` injects a deterministic symbol pattern and
commits a memory on each tick. Strings are arbitrary input labels, not a closed
operator vocabulary. Identical string bytes retain the original numeric encoding;
renaming the *input data* changes that encoding.

Optional adapter objects are supplied to the constructor:

| Argument | Methods used |
|---|---|
| `history` | `push(symbol)`, `get_trace()` or a `stack` list |
| `activity` | `update(change_magnitude, neighbor_transfer_sum)` |
| `transfer` | `propagate_to_neighbors(source_id, deltas, weights)` |
| `bias` | `score_with_activity(symbol, activity_value)` |
| `logger` | `log(event_name, data, agent=source_id)` |

Defaults reproduce the archived standalone fallback formulas. History/activity
and bias remain diagnostics; they do not implement semantic context-conditioned
retrieval. `step_symbol` accepts explicit `field_rms`, `coherence` and
`entropy_change` overrides, matching the former external-input path.

`attach_to_host` attaches an overlay without replacing a different existing one.
It can explicitly merge the host's memory/state into the runtime; if the host has
a compatible `lineage`, it also receives a snapshot of the runtime lineage.
`bind_agent` optionally shares `agent.stack` and imports `agent.projection_field`.
`sync_bound_agent` explicitly exports a projection and updates `hme_bundles`.
These are plain, duck-typed interfaces. Automatic discovery of QOSMOS modules and
legacy snapshot parsers remain in the unchanged archive.

## Spatial dynamics and visualization

```python
from hme_dynamics import AblationConfig, DynamicsConfig, FieldDynamics

simulator = FieldDynamics(DynamicsConfig(grid_size=48, num_steps=36, seed=7))
x, trajectory, metrics = simulator.evolve([0.0, 1.0, 0.0, -1.0])
```

`evolve()` requires only NumPy and restores the double spatial derivative,
diffusion coefficient, damping, periodic drive, clipping and seeded initial
noise. Its `stable` and `legacy` modes preserve the archived formulas. Ablation
switches are `symbol_seed`, `initial_noise`, `phase_modulation`, `periodic_drive`,
`diffusion`, and `damping`.

Install `.[dynamics]` for Pillow-based `run(symbol="A")`, then use
`to_hme_payload(result)` or `commit_to_hme(memory, result, position=(...))`.
The bridge writes a signature and source hashes; it does not automatically copy
the simulation trajectory into the runtime state or use its diagnostic event
score as write salience. Font selection affects raster inputs and is logged.

Install `.[visualization]` for `render_overlay()`, `animate("run.gif")`, and
`save_diagnostics()`. Animation uses recorded state projections and event times.
MP4 export additionally requires a local FFmpeg executable.

Run `python examples/runtime_demo.py` for a NumPy-only end-to-end example.

## Restoration boundary

This restores numerical mechanisms, not the proposed semantic-context or
prediction-discrepancy redesign. It does not add an inverse semantic decoder,
novelty classification, probability calibration or a nearest-neighbor advantage.
The encoder still loses global phase/sign; decoding a position alone does not
separate items sharing that position.

Runtime and simulation records have new plain-language schemas (`hme-runtime-v1`
and `hme-dynamics-v1`). Memory records remain `hme-v3`. Event IDs and serialized
metadata are not promised to match archived framework identities. No Kernel
v1.1 conformance claim is made. The exact v2.2 files and historical evidence stay
pinned separately.

The parity tests compare full state/memory arrays, projections, diagnostics,
event timing/hashes, gains and retrieval order across both controllers, all eight
salience settings, and automatic/disabled/forced events. Diffusion tests compare
both integration modes and all six ablations against the frozen simulator. The
restoration report records the executed tests and source hashes.
