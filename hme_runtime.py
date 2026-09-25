"""Optional evolving-field controllers for HME.

Restores the archived numerical runtime under plain names. The memory core is
imported independently; no framework imports or canonical-operator claims.
See docs/RUNTIME.md for update order and the restoration boundary.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike

from hme_engine import (
    HME, HMEEngine, HMEConfig, SalienceConfig, HMEArtifact, LineageGraph,
    LineageNode, LineageEdge, ComplexArray, FloatArray, _EPS, _field_hash,
    _jsonable, _resize_2d, _sha256, _validate_operation, deterministic_symbol_vector,
)

ENGINE_ID = "hme-runtime-3.1.0"
SCHEMA_ID = "hme-runtime-v1"

@dataclass(slots=True)
class EventConfig:
    """Thresholded phase locking and magnitude quantization of the state field."""
    enabled: bool = True
    threshold: float = 1.67
    entropy_damping: float = 0.15
    min_coherence: float = 1.0e-6
    hysteresis: float = 0.08
    cooldown_steps: int = 2
    radius_fraction: float = 0.12
    phase_lock_strength: float = 0.78
    quantization_levels: int = 12
    stable_drift_max: float = 0.08

    def __post_init__(self) -> None:
        for name in ("threshold", "entropy_damping", "min_coherence", "hysteresis",
                     "radius_fraction", "phase_lock_strength", "stable_drift_max"):
            if not np.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        if not 0 <= self.entropy_damping <= 10 or self.min_coherence <= 0:
            raise ValueError("entropy_damping must be in [0, 10]; min_coherence must be positive")
        if self.cooldown_steps < 0 or self.hysteresis < 0 or self.stable_drift_max < 0:
            raise ValueError("cooldown_steps, hysteresis and stable_drift_max must be non-negative")
        if not 0.01 <= self.radius_fraction <= 0.5:
            raise ValueError("radius_fraction must be in [0.01, 0.5]")
        if not 0 <= self.phase_lock_strength <= 1 or self.quantization_levels < 2:
            raise ValueError("phase_lock_strength must be in [0, 1]; quantization_levels must be >= 2")

def _normalized_entropy(values: ArrayLike) -> float:
    weights = np.abs(np.asarray(values, dtype=np.float64)).reshape(-1)
    total = float(weights.sum())
    if total <= _EPS or weights.size <= 1:
        return 0.0
    p = weights / total
    p = p[p > _EPS]
    entropy = -float(np.sum(p * np.log(p)))
    return entropy / math.log(weights.size)


def _phase_coherence(field: ComplexArray) -> float:
    weights = np.abs(field).reshape(-1)
    total = float(weights.sum())
    if total <= _EPS:
        return 0.0
    unit_phase = np.exp(1j * np.angle(field.reshape(-1)))
    return float(np.clip(np.abs(np.sum(weights * unit_phase) / total), 0.0, 1.0))


@dataclass(slots=True)
class TelemetryFrame:
    run_id: str
    step: int
    phase: int
    coherence: float
    field_rms: float
    state_change_norm: float
    projection_stability: float
    entropy: float
    entropy_change: float
    drift: float
    stable: bool
    event_triggered: bool
    tags: list[str]
    write_salience: float
    engine_id: str = ENGINE_ID
    schema_id: str = SCHEMA_ID
    notes: list[str] = field(default_factory=list)
    scalars: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(slots=True)
class FieldEvent:
    event_id: str
    step: int
    center: tuple[int, int]
    radius: int
    score: float
    threshold: float
    mode: str
    operation: str
    pre_hash: str
    post_hash: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(slots=True)
class RuntimeStep:
    projection: FloatArray
    meta: TelemetryFrame
    memory_artifact: HMEArtifact | None
    field_event: FieldEvent | None


class RuntimeLineage(LineageGraph):
    """Memory insertion lineage plus field-event provenance."""

    def __init__(self) -> None:
        super().__init__()
        self._last_event_node: str | None = None

    def add_field_event(self, event: FieldEvent) -> LineageNode:
        node_id = f"event:{event.event_id}"
        node = self.add_node(
            LineageNode(
                node_id=node_id,
                kind="FieldEvent",
                t=event.step,
                position=event.center,
                operation=event.operation,
                payload_hash=event.post_hash,
                attrs={
                    "score": event.score,
                    "threshold": event.threshold,
                    "mode": event.mode,
                    "reason": event.reason,
                    "pre_hash": event.pre_hash,
                    **event.metadata,
                },
            )
        )
        if self._last_event_node is not None:
            self.add_edge(
                LineageEdge(
                    source=self._last_event_node,
                    target=node_id,
                    relation="next_event",
                )
            )
        if self._last_memory_node is not None:
            self.add_edge(
                LineageEdge(
                    source=self._last_memory_node,
                    target=node_id,
                    relation="memory_precedes_event",
                    weight=event.score,
                )
            )
        self._last_event_node = node_id
        return node


    def link_event_to_memory(
        self, event: FieldEvent, artifact: HMEArtifact
    ) -> None:
        source = f"event:{event.event_id}"
        target = f"memory:{artifact.artifact_id}"
        if source in self.nodes and target in self.nodes:
            self.add_edge(
                LineageEdge(
                    source=source,
                    target=target,
                    relation="event_to_memory",
                    weight=max(event.score, 0.0),
                )
            )


class FieldRuntime(HMEEngine):
    """State field, diagnostic projection, events and optional memory writes."""

    def __init__(self, memory_size: int = 64, encoding_resolution: int = 16, *,
                 hme_config: HMEConfig | None = None,
                 salience_config: SalienceConfig | None = None,
                 event_config: EventConfig | None = None,
                 seed: int = 7, run_id: str | None = None) -> None:
        super().__init__(memory_size, encoding_resolution, hme_config=hme_config,
                         salience_config=salience_config, seed=seed, run_id=run_id)
        self.lineage = RuntimeLineage()
        self.event_config = event_config or EventConfig()
        self.rng = np.random.default_rng(self.seed)
        self.state_field = np.zeros_like(self.hme.field)
        self._previous_state_field = self.state_field.copy()
        self._previous_projection: FloatArray | None = None
        self._previous_entropy = 0.0
        self._last_event_step = -10**9
        self._event_armed = True
        self.phase = 0
        self.telemetry: list[TelemetryFrame] = []
        self.event_log: list[FieldEvent] = []
        self.frame_history: list[FloatArray] = []
        self.frame_steps: list[int] = []
        self._attached_host: Any | None = None

    def set_state_field(self, field_value: ArrayLike, *, blend: float = 1.0) -> None:
        if not 0.0 <= blend <= 1.0:
            raise ValueError("blend must be in [0, 1]")
        incoming = np.asarray(field_value, dtype=np.complex128)
        if incoming.size == 0 or not np.all(np.isfinite(incoming)):
            raise ValueError("state_field must be non-empty and finite")
        if incoming.ndim == 1:
            side = int(round(math.sqrt(incoming.size)))
            if side * side != incoming.size:
                raise ValueError("1D state_field input must have a square number of elements")
            incoming = incoming.reshape(side, side)
        if incoming.ndim != 2:
            raise ValueError("state_field must be a 2D array")
        if incoming.shape != self.state_field.shape:
            incoming = _resize_2d(incoming, self.state_field.shape)
        self._previous_state_field = self.state_field.copy()
        self.state_field = (
            (1.0 - blend) * self.state_field + blend * incoming
        ).astype(np.complex128)


    def inject_state(self, delta: ArrayLike, *, gain: float = 1.0) -> None:
        incoming = np.asarray(delta, dtype=np.complex128)
        if incoming.size == 0 or not np.all(np.isfinite(incoming)) or not np.isfinite(gain):
            raise ValueError("delta and gain must be finite; delta must be non-empty")
        if incoming.ndim != 2:
            raise ValueError("delta must be a 2D array")
        if incoming.shape != self.state_field.shape:
            incoming = _resize_2d(incoming, self.state_field.shape)
        self._previous_state_field = self.state_field.copy()
        self.state_field += float(gain) * incoming


    def project(
        self,
        t: float | None = None,
        *,
        phase: float | None = None,
        normalize: bool = True,
        include_memory: bool = True,
    ) -> FloatArray:
        """
        Phase-project the state field and optional memory residue into a real plane.
        This diagnostic projection is not an inverse of the memory encoder.
        """
        tick = float(self.step_index if t is None else t)
        angle = float(phase) if phase is not None else 2.0 * math.pi * (tick % 64.0) / 64.0
        combined = self.state_field + (self.hme.field if include_memory else 0.0)

        y, x = np.indices(combined.shape)
        cy = (combined.shape[0] - 1) / 2.0
        cx = (combined.shape[1] - 1) / 2.0
        radial_phase = np.arctan2(y - cy, x - cx)
        carrier = np.exp(1j * (angle + 0.125 * radial_phase))
        projected = np.real(combined * carrier).astype(np.float64)
        if normalize:
            scale = float(np.max(np.abs(projected)))
            if scale > _EPS:
                projected = projected / scale
        return projected


    def _measure_telemetry(
        self,
        projection: FloatArray,
        *,
        state_change_norm: float,
        notes: Sequence[str] = (),
    ) -> TelemetryFrame:
        combined = self.state_field + self.hme.field
        field_rms = float(np.sqrt(np.mean(np.abs(combined) ** 2)))
        coherence = _phase_coherence(combined)
        entropy = _normalized_entropy(np.abs(projection))
        entropy_change = float(entropy - self._previous_entropy)

        if self._previous_projection is None:
            drift = 0.0
        else:
            denom = float(np.linalg.norm(self._previous_projection)) + _EPS
            drift = float(np.linalg.norm(projection - self._previous_projection) / denom)

        projection_stability = float(np.clip(1.0 - drift, 0.0, 1.0))
        write_salience = (
            field_rms / max(coherence, self.event_config.min_coherence)
            - self.event_config.entropy_damping * entropy_change
        )
        stable = bool(drift <= self.event_config.stable_drift_max)
        tags = ["tick", f"phase:{self.phase}", "measurement:pre-event"]

        frame = TelemetryFrame(
            run_id=self.run_id,
            step=self.step_index,
            phase=self.phase,
            coherence=coherence,
            field_rms=field_rms,
            state_change_norm=float(state_change_norm),
            projection_stability=projection_stability,
            entropy=entropy,
            entropy_change=entropy_change,
            drift=drift,
            stable=stable,
            event_triggered=False,
            tags=tags,
            write_salience=float(write_salience),
            notes=list(notes),
            scalars={
                "threshold": float(self.event_config.threshold),
                "entropy_damping": float(self.event_config.entropy_damping),
                "projection_peak": float(np.max(np.abs(projection))),
                "hme_norm": float(np.linalg.norm(self.hme.field)),
                "state_norm": float(np.linalg.norm(self.state_field)),
            },
        )
        return frame


    def _event_predicate(self, meta: TelemetryFrame) -> bool:
        cfg = self.event_config
        if not cfg.enabled:
            return False
        if self.step_index - self._last_event_step < cfg.cooldown_steps:
            return False

        # Hysteresis prevents rapid arm/disarm chatter around threshold.
        if self._event_armed:
            fire = meta.write_salience > cfg.threshold
            if fire:
                self._event_armed = False
            return fire

        if meta.write_salience < cfg.threshold - cfg.hysteresis:
            self._event_armed = True
        return False


    def _event_center(self, projection: FloatArray) -> tuple[int, int]:
        flat_index = int(np.argmax(np.abs(projection)))
        return tuple(map(int, np.unravel_index(flat_index, projection.shape)))


    def _apply_field_event(
        self,
        meta: TelemetryFrame,
        projection: FloatArray,
        *,
        center: tuple[int, int] | None = None,
        reason: str = "write_salience exceeded implementation threshold",
    ) -> FieldEvent:
        cfg = self.event_config
        center = center or self._event_center(projection)
        radius = max(2, int(round(self.memory_size * cfg.radius_fraction)))
        pre_hash = _field_hash(self.state_field)

        y, x = np.indices(self.state_field.shape)
        distance_sq = (y - center[0]) ** 2 + (x - center[1]) ** 2
        sigma = max(radius / 2.0, 1.0)
        mask = np.exp(-distance_sq / (2.0 * sigma * sigma))

        local = self.state_field * mask
        weights = np.abs(local)
        if float(weights.sum()) <= _EPS:
            target_phase = 0.0
        else:
            target_phase = float(
                np.angle(np.sum(weights * np.exp(1j * np.angle(local))))
            )

        magnitude = np.abs(self.state_field)
        levels = cfg.quantization_levels
        max_mag = float(magnitude.max())
        if max_mag > _EPS:
            quantized_mag = np.round((magnitude / max_mag) * (levels - 1))
            quantized_mag = quantized_mag / (levels - 1) * max_mag
        else:
            quantized_mag = magnitude

        locked = quantized_mag * np.exp(1j * target_phase)
        strength = cfg.phase_lock_strength * mask
        self.state_field = (
            (1.0 - strength) * self.state_field + strength * locked
        ).astype(np.complex128)
        post_hash = _field_hash(self.state_field)

        event_id = _sha256(
            {
                "run_id": self.run_id,
                "step": self.step_index,
                "center": center,
                "radius": radius,
                "score": meta.write_salience,
                "pre": pre_hash,
                "post": post_hash,
            }
        )[:20]
        event = FieldEvent(
            event_id=event_id,
            step=self.step_index,
            center=center,
            radius=radius,
            score=meta.write_salience,
            threshold=cfg.threshold,
            mode="localized_phase_lock_quantize",
            operation="phase_lock",
            pre_hash=pre_hash,
            post_hash=post_hash,
            reason=reason,
            metadata={
                "coherence": meta.coherence,
                "field_rms": meta.field_rms,
                "entropy_change": meta.entropy_change,
                "phase_lock_strength": cfg.phase_lock_strength,
                "quantization_levels": cfg.quantization_levels,
                "threshold_scope": "implementation-specific",
            },
        )
        self.event_log.append(event)
        self.lineage.add_field_event(event)
        self._last_event_step = self.step_index
        return event


    def step(
        self,
        input_field: ArrayLike | None = None,
        *,
        input_blend: float = 1.0,
        memory_payload: ArrayLike | str | None = None,
        memory_position: tuple[int, int] | None = None,
        memory_gain: float = 0.1,
        memory_operation: str = "write",
        write_weight: float = 1.0,
        event_override: bool | None = None,
        event_center: tuple[int, int] | None = None,
        metadata: Mapping[str, Any] | None = None,
        record_frame: bool = True,
    ) -> RuntimeStep:
        """Advance one audited HME/event-overlay tick."""
        if input_field is not None:
            self.set_state_field(input_field, blend=input_blend)

        state_change_norm = float(np.linalg.norm(self.state_field - self._previous_state_field))
        projection_pre = self.project(self.step_index)

        # Load-bearing order: telemetry is computed before the event decision.
        meta_pre = self._measure_telemetry(projection_pre, state_change_norm=state_change_norm)
        should_apply_event = (
            self._event_predicate(meta_pre)
            if event_override is None
            else bool(event_override)
        )

        field_event: FieldEvent | None = None
        if should_apply_event:
            field_event = self._apply_field_event(
                meta_pre,
                projection_pre,
                center=event_center,
                reason=(
                    "manual event override"
                    if event_override is True
                    else "write_salience exceeded implementation threshold"
                ),
            )

        memory_artifact: HMEArtifact | None = None
        if memory_payload is not None:
            if memory_position is None:
                memory_position = event_center or (
                    field_event.center
                    if field_event is not None
                    else self._event_center(projection_pre)
                )
            memory_artifact = self.encode_memory(
                memory_payload,
                memory_position,
                memory_gain,
                operation=memory_operation,
                write_weight=write_weight,
                metadata={
                    **dict(metadata or {}),
                    "committed_after_event": field_event is not None,
                    "write_salience": float(meta_pre.write_salience),
                },
                t=self.step_index,
            )
            if field_event is not None:
                self.lineage.link_event_to_memory(field_event, memory_artifact)

        projection_post = self.project(self.step_index)
        tags = list(meta_pre.tags)
        if field_event is not None:
            tags.append("event")
        if memory_artifact is not None:
            tags.append("memory_commit")
        meta = replace(
            meta_pre,
            event_triggered=field_event is not None,
            tags=tags,
        )
        self.telemetry.append(meta)

        if record_frame:
            self.frame_history.append(projection_post.copy())
            self.frame_steps.append(self.step_index)

        self._previous_projection = projection_post.copy()
        self._previous_entropy = meta.entropy
        self._previous_state_field = self.state_field.copy()
        self.step_index += 1
        self.phase += 1

        return RuntimeStep(
            projection=projection_post,
            meta=meta,
            memory_artifact=memory_artifact,
            field_event=field_event,
        )


    def merge_hme(self, other: HME | ArrayLike, *, weight: float = 1.0) -> None:
        self.hme.merge(other, weight=weight)
        if isinstance(other, HME):
            for artifact in other.records.values():
                if f"memory:{artifact.artifact_id}" not in self.lineage.nodes:
                    self.lineage.add_memory_artifact(artifact)


    def attach_to_host(
        self,
        host: Any,
        *,
        merge_existing_hme: bool = False,
        merge_state_field: bool = False,
        state_blend: float = 0.5,
        attach_name: str = "hme_overlay",
    ) -> dict[str, Any]:
        """
        Duck-typed optional merge into external host.

        Existing attributes are never overwritten silently. The overlay is
        attached under ``attach_name``. Compatible ``hme``, ``HME``, ``lineage``,
        and ``state_field`` values are merged only when explicitly requested.
        """
        if hasattr(host, attach_name):
            existing = getattr(host, attach_name)
            if existing is not self:
                raise AttributeError(
                    f"host already has a different {attach_name!r} attribute"
                )
        else:
            setattr(host, attach_name, self)

        report: dict[str, Any] = {
            "attached_as": attach_name,
            "hme_merged": False,
            "lineage_merged": False,
            "state_field_merged": False,
            "projection_adapter": False,
            "notes": [],
        }

        if merge_existing_hme:
            existing_hme = getattr(host, "hme", getattr(host, "HME", None))
            if isinstance(existing_hme, HME):
                self.hme.merge(existing_hme)
                report["hme_merged"] = True
            elif existing_hme is not None:
                candidate = getattr(
                    existing_hme,
                    "field",
                    getattr(existing_hme, "memory_grid", None),
                )
                if candidate is not None:
                    self.hme.merge(np.asarray(candidate, dtype=np.complex128))
                    report["hme_merged"] = True
                else:
                    report["notes"].append(
                        "existing HME object had no field or memory_grid array"
                    )

        existing_lineage = getattr(host, "lineage", None)
        if isinstance(existing_lineage, LineageGraph):
            existing_lineage.merge_from(self.lineage, prefix="overlay:")
            report["lineage_merged"] = True
        elif existing_lineage is not None and hasattr(existing_lineage, "add_node"):
            try:
                for node in self.lineage.nodes.values():
                    node_attrs = node.to_dict()
                    node_attrs.pop("node_id", None)
                    existing_lineage.add_node(node.node_id, **node_attrs)
                if hasattr(existing_lineage, "add_edge"):
                    for edge in self.lineage.edges:
                        edge_attrs = edge.to_dict()
                        edge_attrs.pop("source", None)
                        edge_attrs.pop("target", None)
                        existing_lineage.add_edge(
                            edge.source,
                            edge.target,
                            **edge_attrs,
                        )
                report["lineage_merged"] = True
            except TypeError:
                report["notes"].append(
                    "lineage add_node/add_edge signature was not NetworkX-compatible"
                )

        if merge_state_field and hasattr(host, "state_field"):
            host_field = np.asarray(getattr(host, "state_field"), dtype=np.complex128)
            self.set_state_field(host_field, blend=state_blend)
            report["state_field_merged"] = True

        if not hasattr(host, "hme_projection"):
            setattr(host, "hme_projection", self.project)
            report["projection_adapter"] = True
        else:
            report["notes"].append("host.hme_projection already existed and was not overwritten")

        self._attached_host = host
        return report


    def export_telemetry_jsonl(self, path: str | os.PathLike[str]) -> Path:
        out = Path(path)
        with out.open("w", encoding="utf-8") as handle:
            for frame in self.telemetry:
                handle.write(json.dumps(frame.to_dict(), ensure_ascii=False) + "\n")
        return out


    def export_events_jsonl(self, path: str | os.PathLike[str]) -> Path:
        out = Path(path)
        with out.open("w", encoding="utf-8") as handle:
            for event in self.event_log:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return out


    def state_summary(self) -> dict[str, Any]:
        return {
            "engine_id": ENGINE_ID,
            "schema_id": SCHEMA_ID,
            "run_id": self.run_id,
            "step": self.step_index,
            "phase": self.phase,
            "state_field_hash": _field_hash(self.state_field),
            "hme_field_hash": _field_hash(self.hme.field),
            "memory_records": len(self.hme.records),
            "field_events": len(self.event_log),
            "lineage_nodes": len(self.lineage.nodes),
            "lineage_edges": len(self.lineage.edges),
            "event_threshold_scope": "implementation-specific",
            "projection_scope": "extension diagnostic / visualization projection",
        }


    @staticmethod
    def _require_matplotlib() -> tuple[Any, Any, Any]:
        try:
            import matplotlib.pyplot as plt
            from matplotlib import animation
            from matplotlib.patches import Circle
        except ImportError as exc:
            raise RuntimeError(
                "Visualization requires matplotlib; GIF export also needs Pillow"
            ) from exc
        return plt, animation, Circle


    def _overlay_labels(
        self,
        ax: Any,
        *,
        upto_step: int | None = None,
        show_lineage: bool = True,
        show_events: bool = True,
        show_labels: bool = True,
    ) -> None:
        _, _, Circle = self._require_matplotlib()
        max_step = self.step_index if upto_step is None else int(upto_step)

        visible_nodes = [
            node
            for node in self.lineage.nodes.values()
            if node.position is not None and node.t <= max_step
        ]
        node_by_id = {node.node_id: node for node in visible_nodes}

        if show_lineage:
            for edge in self.lineage.edges:
                source = node_by_id.get(edge.source)
                target = node_by_id.get(edge.target)
                if source is None or target is None:
                    continue
                x0, y0 = source.position
                x1, y1 = target.position
                ax.plot([y0, y1], [x0, x1], linewidth=0.8, alpha=0.45)

        for node in visible_nodes:
            if node.operation is None:
                continue
            x, y = node.position
            label = node.operation
            if show_labels and node.kind == "HMEArtifact":
                tag = str(node.attrs.get("tag", ""))
                if tag:
                    label = f"{label}\n{tag[:14]}"
            ax.text(
                y,
                x,
                label,
                ha="center",
                va="center",
                fontsize=9,
                bbox={"boxstyle": "round", "alpha": 0.62},
            )

        if show_events:
            for event in self.event_log:
                if event.step > max_step:
                    continue
                x, y = event.center
                ax.add_patch(
                    Circle(
                        (y, x),
                        event.radius,
                        fill=False,
                        linewidth=1.2,
                        alpha=0.75,
                    )
                )
                ax.text(
                    y,
                    x - event.radius - 1,
                    "phase_lock",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                )


    def render_overlay(
        self,
        *,
        field_mode: str = "projection",
        t: int | None = None,
        save_path: str | os.PathLike[str] | None = None,
        title: str | None = None,
        show_lineage: bool = True,
        show_events: bool = True,
        show_labels: bool = True,
        dpi: int = 160,
        close: bool = False,
    ) -> tuple[Any, Any]:
        plt, _, _ = self._require_matplotlib()
        mode = field_mode.lower()
        if mode == "projection":
            image = self.project(self.step_index if t is None else t)
            default_title = "HME field projection and events"
        elif mode in {"hme", "memory"}:
            image = np.abs(self.hme.field)
            default_title = "HME memory field and lineage"
        elif mode in {"state", "state_field"}:
            image = np.abs(self.state_field)
            default_title = "HME state field / event overlay"
        else:
            raise ValueError("field_mode must be 'projection', 'memory', or 'state'")

        fig, ax = plt.subplots(figsize=(8, 7))
        shown = ax.imshow(image, origin="lower", interpolation="nearest")
        fig.colorbar(shown, ax=ax, label="field magnitude / projection")
        self._overlay_labels(
            ax,
            upto_step=self.step_index if t is None else t,
            show_lineage=show_lineage,
            show_events=show_events,
            show_labels=show_labels,
        )
        ax.set_title(title or default_title)
        ax.set_xlabel("field y")
        ax.set_ylabel("field x")
        fig.tight_layout()

        if save_path is not None:
            fig.savefig(Path(save_path), dpi=dpi, bbox_inches="tight")
        if close:
            plt.close(fig)
        return fig, ax


    def animate(
        self,
        save_path: str | os.PathLike[str],
        *,
        frames: Sequence[ArrayLike] | None = None,
        frame_steps: Sequence[int] | None = None,
        fps: int = 8,
        interval_ms: int | None = None,
        title: str = "HME field evolution and memory events",
        dpi: int = 120,
    ) -> Path:
        plt, animation, _ = self._require_matplotlib()
        source_frames = (
            [np.asarray(frame, dtype=np.float64) for frame in frames]
            if frames is not None
            else [frame.copy() for frame in self.frame_history]
        )
        if not source_frames:
            raise ValueError("no frames are available for animation")
        steps = (
            list(map(int, frame_steps))
            if frame_steps is not None
            else list(self.frame_steps)
        )
        if len(steps) != len(source_frames):
            steps = list(range(len(source_frames)))

        fig, ax = plt.subplots(figsize=(8, 7))
        shown = ax.imshow(source_frames[0], origin="lower", interpolation="nearest")
        fig.colorbar(shown, ax=ax, label="field projection")
        ax.set_xlabel("field y")
        ax.set_ylabel("field x")

        def update(frame_index: int) -> list[Any]:
            ax.clear()
            shown_local = ax.imshow(
                source_frames[frame_index],
                origin="lower",
                interpolation="nearest",
            )
            self._overlay_labels(
                ax,
                upto_step=steps[frame_index],
                show_lineage=True,
                show_events=True,
                show_labels=False,
            )
            ax.set_title(f"{title}\nstep={steps[frame_index]}")
            ax.set_xlabel("field y")
            ax.set_ylabel("field x")
            return [shown_local]

        interval = interval_ms if interval_ms is not None else int(1000 / max(fps, 1))
        anim = animation.FuncAnimation(
            fig,
            update,
            frames=len(source_frames),
            interval=interval,
            blit=False,
        )
        out = Path(save_path)
        suffix = out.suffix.lower()
        if suffix == ".gif":
            writer = animation.PillowWriter(fps=fps)
        elif suffix in {".mp4", ".m4v"}:
            writer = animation.FFMpegWriter(fps=fps)
        else:
            plt.close(fig)
            raise ValueError("animation output must end in .gif, .mp4, or .m4v")
        anim.save(out, writer=writer, dpi=dpi)
        plt.close(fig)
        return out


class HistoryBuffer:
    def __init__(self, max_length: int = 12):
        self.stack: list[str] = []
        self.max_length = int(max_length)

    def push(self, symbol: str) -> None:
        self.stack.append(str(symbol))
        if len(self.stack) > self.max_length:
            self.stack.pop(0)

    def get_trace(self) -> list[str]:
        return list(self.stack)

    def has_pattern(self, pattern: list[str]) -> bool:
        return ",".join(pattern) in ",".join(self.stack)

    def decay(self, decay_factor: float = 0.5) -> None:
        keep = max(0, int(round(len(self.stack) * (1.0 - float(decay_factor)))))
        self.stack = self.stack[-keep:] if keep else []


class ActivityTrace:
    def __init__(self, initial_value: float = 1.0, damping: float = 0.03):
        self.activity = float(initial_value)
        self.damping = float(damping)

    def update(self, change_magnitude: float, neighbor_transfer_sum: float) -> float:
        self.activity += 0.4 * float(change_magnitude) + 0.2 * float(neighbor_transfer_sum)
        self.activity *= 1.0 - self.damping
        return self.activity

    def get_value(self) -> float:
        return float(self.activity)


class NeighborTransfer:
    def __init__(self, scale: float = 0.7, exponent: float = 1.25):
        self.scale = float(scale)
        self.exponent = float(exponent)

    def compute_transfer(self, state_delta: float, weight: float) -> float:
        return self.scale * abs(float(state_delta)) ** self.exponent * float(weight)

    def propagate_to_neighbors(self, agent_id: str, state_delta_map: Mapping[str, float], weight_map: Mapping[str, float]) -> dict[str, float]:
        return {
            neighbor: self.compute_transfer(delta, weight_map.get(neighbor, 1.0))
            for neighbor, delta in state_delta_map.items()
        }


class AgentRuntime(FieldRuntime):
    """Symbol-driven ticks with injectable history, activity and neighbor adapters.

    Defaults reproduce the archived standalone adapters. Adapters are explicitly
    passed objects; there is no implicit discovery of external framework modules.
    """

    def __init__(self, memory_size: int = 64, encoding_resolution: int = 16, *,
                 hme_config: HMEConfig | None = None,
                 salience_config: SalienceConfig | None = None,
                 event_config: EventConfig | None = None,
                 seed: int = 7, run_id: str | None = None,
                 history: Any | None = None, activity: Any | None = None,
                 transfer: Any | None = None, bias: Any | None = None,
                 logger: Any | None = None) -> None:
        super().__init__(memory_size, encoding_resolution, hme_config=hme_config,
                         salience_config=salience_config, event_config=event_config,
                         seed=seed, run_id=run_id)
        self.stack = history if history is not None else HistoryBuffer()
        self.activity = activity if activity is not None else ActivityTrace()
        self.transfer = transfer if transfer is not None else NeighborTransfer()
        self.bias = bias
        self.logger = logger
        self.bound_agent: Any | None = None

    @staticmethod
    def _default_position(symbol: str, size: int, step: int) -> tuple[int, int]:
        digest = hashlib.sha256(f"{symbol}|{step}".encode("utf-8")).digest()
        margin = max(2, size // 10)
        span = max(1, size - 2 * margin)
        return (
            margin + int.from_bytes(digest[:4], "big") % span,
            margin + int.from_bytes(digest[4:8], "big") % span,
        )


    def _inject_symbol(
        self,
        symbol: str,
        position: tuple[int, int],
        gain: float,
    ) -> None:
        vector = deterministic_symbol_vector(symbol, self.hme.encoding_resolution)
        _, pattern = self.hme._generate_pattern(vector)
        grid_slice, pattern_slice = self.hme._patch_slices(position, pattern.shape)
        self._previous_state_field = self.state_field.copy()
        self.state_field[grid_slice] += float(gain) * pattern[pattern_slice]


    def bind_agent(
        self,
        agent: Any,
        *,
        use_agent_history: bool = True,
        import_projection_field: bool = True,
        attach_name: str = "hme_engine",
    ) -> dict[str, Any]:
        """Bind an existing input agent without replacing its current methods."""
        report = {
            "attached_as": attach_name,
            "stack_bound": False,
            "projection_field_imported": False,
            "notes": [],
        }
        existing = getattr(agent, attach_name, None)
        if existing is not None and existing is not self:
            raise AttributeError(f"agent already has a different {attach_name!r}")
        setattr(agent, attach_name, self)
        self.bound_agent = agent

        if use_agent_history and hasattr(agent, "stack"):
            self.stack = agent.stack
            report["stack_bound"] = True
        if import_projection_field and hasattr(agent, "projection_field"):
            try:
                self.set_state_field(np.asarray(agent.projection_field), blend=1.0)
                report["projection_field_imported"] = True
            except Exception as exc:
                report["notes"].append(f"projection_field import skipped: {exc}")
        return report


    def sync_bound_agent(self, *, export_projection_field: bool = False) -> dict[str, bool]:
        """Explicitly synchronize selected fields back to a bound agent."""
        report = {"projection_field_exported": False, "hme_bundles_linked": False}
        agent = self.bound_agent
        if agent is None:
            return report
        if export_projection_field and hasattr(agent, "projection_field"):
            agent.projection_field = self.project(normalize=False).copy()
            report["projection_field_exported"] = True
        if hasattr(agent, "hme_bundles"):
            agent.hme_bundles = list(self.hme.records.values())
            report["hme_bundles_linked"] = True
        return report


    def step_symbol(
        self,
        symbol: str,
        *,
        field_rms: float | None = None,
        coherence: float | None = None,
        entropy_change: float | None = None,
        state_delta: float = 0.0,
        source_id: str = "source-001",
        neighbor_deltas: Mapping[str, float] | None = None,
        neighbor_weights: Mapping[str, float] | None = None,
        input_field: ArrayLike | None = None,
        input_blend: float = 1.0,
        position: tuple[int, int] | None = None,
        payload: ArrayLike | str | None = None,
        memory_gain: float = 0.1,
        write_weight: float = 1.0,
        event_override: bool | None = None,
        record_frame: bool = True,
        metadata: Mapping[str, Any] | None = None,
    ) -> RuntimeStep:
        """Advance one symbol-driven tick with the configured adapters."""
        symbol = _validate_operation(symbol, fallback="input")
        if input_field is not None:
            self.set_state_field(input_field, blend=input_blend)

        position = position or self._default_position(
            symbol, self.memory_size, self.step_index
        )
        self._inject_symbol(
            symbol,
            position,
            gain=max(0.01, 0.08 * float(write_weight)),
        )
        if hasattr(self.stack, "push"):
            self.stack.push(symbol)

        projection_pre = self.project(self.step_index)
        entropy = _normalized_entropy(np.abs(projection_pre))
        entropy_change_value = (
            float(entropy - self._previous_entropy)
            if entropy_change is None
            else float(entropy_change)
        )
        combined = self.state_field + self.hme.field
        rms_value = (
            float(np.sqrt(np.mean(np.abs(combined) ** 2)))
            if field_rms is None
            else float(field_rms)
        )
        coherence_value = (
            max(_phase_coherence(combined), self.event_config.min_coherence)
            if coherence is None
            else max(float(coherence), self.event_config.min_coherence)
        )

        neighbor_deltas = dict(neighbor_deltas or {})
        neighbor_weights = dict(neighbor_weights or {})
        neighbor_transfers = self.transfer.propagate_to_neighbors(
            source_id,
            neighbor_deltas,
            neighbor_weights,
        ) if neighbor_deltas else {}
        neighbor_transfer_sum = float(sum(abs(value) for value in neighbor_transfers.values()))

        # Current host convention: telemetry is updated before phase_lock is applied.
        activity_value = float(
            self.activity.update(abs(float(state_delta)), neighbor_transfer_sum)
        )

        if self._previous_projection is None:
            drift = 0.0
        else:
            drift = float(
                np.linalg.norm(projection_pre - self._previous_projection)
                / (float(np.linalg.norm(self._previous_projection)) + _EPS)
            )
        state_change_norm = float(np.linalg.norm(self.state_field - self._previous_state_field))
        projection_stability = float(np.clip(1.0 - drift, 0.0, 1.0))
        write_salience = (
            rms_value / coherence_value
            - self.event_config.entropy_damping * entropy_change_value
        )
        bias_score = 0.0
        if self.bias is not None and hasattr(self.bias, "score_with_activity"):
            try:
                bias_score = float(
                    self.bias.score_with_activity(symbol, activity_value)
                )
            except Exception:
                bias_score = 0.0

        meta_pre = TelemetryFrame(
            run_id=self.run_id,
            step=self.step_index,
            phase=self.phase,
            coherence=coherence_value,
            field_rms=rms_value,
            state_change_norm=state_change_norm,
            projection_stability=projection_stability,
            entropy=entropy,
            entropy_change=entropy_change_value,
            drift=drift,
            stable=bool(drift <= self.event_config.stable_drift_max),
            event_triggered=False,
            tags=["tick", f"symbol:{symbol}", "measurement:pre-event", "runtime:agent"],
            write_salience=float(write_salience),
            notes=[
                "RMS/coherence/entropy_change use current-host inputs when supplied; otherwise field diagnostics"
            ],
            scalars={
                "activity": activity_value,
                "state_delta": float(state_delta),
                "neighbor_transfer_sum": neighbor_transfer_sum,
                "bias_score": bias_score,
                "threshold": float(self.event_config.threshold),
                "entropy_damping": float(self.event_config.entropy_damping),
                "history_compression": self._stack_compression_ratio(),
            },
        )

        should_apply_event = (
            self._event_predicate(meta_pre)
            if event_override is None
            else bool(event_override)
        )
        field_event = None
        if should_apply_event:
            field_event = self._apply_field_event(
                meta_pre,
                projection_pre,
                center=position,
                reason=(
                    "manual event override"
                    if event_override is True
                    else "write_salience exceeded threshold"
                ),
            )
            field_event.metadata.update({
                "source_id": source_id,
                "source_symbol": symbol,
                "activity": activity_value,
                "neighbor_transfers": neighbor_transfers,
            })

        memory_payload = symbol if payload is None else payload
        artifact = self.encode_memory(
            memory_payload,
            position,
            strength=memory_gain,
            operation="write",
            write_weight=write_weight,
            metadata={
                **dict(metadata or {}),
                "source_symbol": symbol,
                "source_id": source_id,
                "activity": activity_value,
                "write_salience": float(write_salience),
                "event_triggered": field_event is not None,
                "neighbor_transfers": neighbor_transfers,
            },
            t=self.step_index,
        )
        if field_event is not None:
            self.lineage.link_event_to_memory(field_event, artifact)

        projection_post = self.project(self.step_index)
        tags = list(meta_pre.tags) + ["memory_commit"]
        if field_event is not None:
            tags.append("event")
        meta = replace(
            meta_pre,
            event_triggered=field_event is not None,
            tags=tags,
        )
        self.telemetry.append(meta)

        if self.logger is not None and hasattr(self.logger, "log"):
            self.logger.log(
                "hme_runtime_step",
                {
                    "symbol": symbol,
                    "field_rms": rms_value,
                    "coherence": coherence_value,
                    "entropy_change": entropy_change_value,
                    "write_salience": write_salience,
                    "event_triggered": field_event is not None,
                    "activity": activity_value,
                    "artifact_id": artifact.artifact_id,
                },
                agent=source_id,
            )

        if record_frame:
            self.frame_history.append(projection_post.copy())
            self.frame_steps.append(self.step_index)
        self._previous_projection = projection_post.copy()
        self._previous_entropy = entropy
        self._previous_state_field = self.state_field.copy()
        self.step_index += 1
        self.phase += 1

        return RuntimeStep(
            projection=projection_post,
            meta=meta,
            memory_artifact=artifact,
            field_event=field_event,
        )


    def _stack_compression_ratio(self) -> float:
        trace = []
        if hasattr(self.stack, "get_trace"):
            trace = list(self.stack.get_trace())
        elif hasattr(self.stack, "stack"):
            trace = list(self.stack.stack)
        depth = len(trace)
        uniq = len(set(map(str, trace)))
        if depth == 0 or uniq == 0:
            return 0.0
        return float(math.log2(max(depth / uniq, 1.0)))
