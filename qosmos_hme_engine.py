#!/usr/bin/env python3
"""
qosmos_hme_engine.py
================================
Direct HME / QMesh / collapse-layer engine for the qosmos_core_v2.X tree.

Status
------
Typed realization / DEVELOP implementation integrated with the current QOSMOS core modules. This module does not amend QOFT
canon. It preserves the operational order:

    ψ input → W(t) projection → Ψmeta → Λψ? → Σ◯/HME commit → QMesh lineage

The W(t) projection and the concrete HME field are implementation choices.
Fixed collapse thresholds are implementation-specific defaults.

Primary features
----------------
- Complex 2D HME field with boundary-safe FFT pattern placement.
- Deterministic SHA-256 symbol/vector seeding.
- Query-aware local retrieval with ranked artifact provenance.
- Lightweight QMesh nodes/edges for memory and collapse lineage.
- Ψmeta-before-collapse telemetry using the v27 local diagnostic form:

      C_psi = Φ / ρ - κ_damp * dS
      collapse iff C_psi > lambda_c

- Append-only collapse-layer records.
- W(t) field projection for visualization/diagnostics.
- Canonical-glyph overlays and GIF/MP4 animation.
- Conformance patch: Σ◯ labels consolidation/write; Θλ is reserved for retrieval/replay records.
- Direct binding to ReflectiveStack, PsiMetaField, RSBT_CollapseEngine, QosmosLogger, and glyph_vocab.
- Legacy QMesh/HME snapshot ingestion from xibuild_engine.py and Xi_HMEConverter.py.
- Legacy alias: HolographicMemory = HME.

Dependencies
------------
Required: numpy
Optional: matplotlib + Pillow (rendering/animation)

Quick use
---------
    from core.qosmos_hme_engine import QOSMOSCoreHME

    engine = QOSMOSCoreHME(memory_size=64, encoding_resolution=16, seed=7)
    engine.encode_memory([0.1, 0.4, 0.9, 0.2], position=(20, 22), glyph="Σ◯")
    result = engine.step()
    engine.render_overlay(save_path="hme_overlay.png")

Drop this file into the existing core/ directory. It does not
require a subfolder and does not monkey-patch imports at module import time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import OrderedDict
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


# ---------------------------------------------------------------------------
# Current qosmos_core_v2.X imports
# ---------------------------------------------------------------------------

# The v2.1.4 text patch declares v27_constants.py, while older validated trees
# expose only config.engine_parameters. This module supports both without
# silently changing either source.
try:  # Package-relative import when installed as core.qosmos_hme_engine
    from .v27_constants import CONST as _CORE_CONST
except Exception:  # Direct/root import or pre-v27 tree
    try:
        from core.v27_constants import CONST as _CORE_CONST
    except Exception:
        _CORE_CONST = None

try:
    from .reflective_stack import ReflectiveStack as _CoreReflectiveStack
except Exception:
    try:
        from core.reflective_stack import ReflectiveStack as _CoreReflectiveStack
    except Exception:
        _CoreReflectiveStack = None

try:
    from .ψmeta_state import PsiMetaField as _CorePsiMetaField
except Exception:
    try:
        from core.ψmeta_state import PsiMetaField as _CorePsiMetaField
    except Exception:
        _CorePsiMetaField = None

try:
    from .rsbt_engine import RSBT_CollapseEngine as _CoreRSBTEngine
except Exception:
    try:
        from core.rsbt_engine import RSBT_CollapseEngine as _CoreRSBTEngine
    except Exception:
        _CoreRSBTEngine = None

try:
    from .logger import QosmosLogger as _CoreLogger
except Exception:
    try:
        from core.logger import QosmosLogger as _CoreLogger
    except Exception:
        _CoreLogger = None

try:
    from .ψbias_module import PsiBiasCalculator as _CorePsiBiasCalculator
except Exception:
    try:
        from core.ψbias_module import PsiBiasCalculator as _CorePsiBiasCalculator
    except Exception:
        _CorePsiBiasCalculator = None

try:
    from .glyph_vocab import GLYPH_SET as _CORE_GLYPH_SET
    from .glyph_vocab import GLYPH_METADATA as _CORE_GLYPH_METADATA
except Exception:
    try:
        from core.glyph_vocab import GLYPH_SET as _CORE_GLYPH_SET
        from core.glyph_vocab import GLYPH_METADATA as _CORE_GLYPH_METADATA
    except Exception:
        _CORE_GLYPH_SET = set()
        _CORE_GLYPH_METADATA = {}


class _FallbackReflectiveStack:
    def __init__(self, max_length: int = 12):
        self.stack: list[str] = []
        self.max_length = int(max_length)

    def push(self, glyph_id: str) -> None:
        self.stack.append(str(glyph_id))
        if len(self.stack) > self.max_length:
            self.stack.pop(0)

    def get_trace(self) -> list[str]:
        return list(self.stack)

    def has_pattern(self, pattern: list[str]) -> bool:
        return ",".join(pattern) in ",".join(self.stack)

    def decay(self, decay_factor: float = 0.5) -> None:
        keep = max(0, int(round(len(self.stack) * (1.0 - float(decay_factor)))))
        self.stack = self.stack[-keep:] if keep else []


class _FallbackPsiMetaField:
    def __init__(self, initial_value: float = 1.0, damping: float = 0.03):
        self.psi_meta = float(initial_value)
        self.damping = float(damping)

    def update(self, collapse_intensity: float, w_drift_sum: float) -> float:
        self.psi_meta += 0.4 * float(collapse_intensity) + 0.2 * float(w_drift_sum)
        self.psi_meta *= 1.0 - self.damping
        return self.psi_meta

    def get_value(self) -> float:
        return float(self.psi_meta)


class _FallbackRSBT:
    def __init__(self, alpha: float = 0.7, kappa: float = 1.25):
        self.alpha = float(alpha)
        self.kappa = float(kappa)

    def compute_collapse_transfer(self, delta_psi: float, weight_uv: float) -> float:
        return self.alpha * abs(float(delta_psi)) ** self.kappa * float(weight_uv)

    def propagate_to_neighbors(self, agent_id: str, delta_psi_map: Mapping[str, float], weight_map: Mapping[str, float]) -> dict[str, float]:
        return {
            neighbor: self.compute_collapse_transfer(delta, weight_map.get(neighbor, 1.0))
            for neighbor, delta in delta_psi_map.items()
        }


ReflectiveStack = _CoreReflectiveStack or _FallbackReflectiveStack
PsiMetaField = _CorePsiMetaField or _FallbackPsiMetaField
RSBT_CollapseEngine = _CoreRSBTEngine or _FallbackRSBT
QosmosLogger = _CoreLogger
PsiBiasCalculator = _CorePsiBiasCalculator

_CORE_ENGINE = getattr(_CORE_CONST, "engine", "qosmos_core_v2.X")
_CORE_SCHEMA = getattr(_CORE_CONST, "schema", "v2X")
_CORE_LAMBDA_C = float(getattr(_CORE_CONST, "lambda_c", 1.67))
_CORE_KAPPA_DAMP = float(getattr(_CORE_CONST, "kappa_damp_default", 0.15))

ENGINE_ID = f"{_CORE_ENGINE}+qosmos_hme_v2.2.0"
SCHEMA_ID = f"{_CORE_SCHEMA}:qosmos-hme-v2"
CANONICAL_GLYPHS = tuple(dict.fromkeys((
    "Ξ",
    "Πᴽ",
    "ψᴽ",
    "Λψ",
    "Σ◯",
    "Θλ",
    "Ωµ",
    "Π↺",
    "Ψmeta",
    *_CORE_GLYPH_SET,
)))
DEFAULT_GLYPH_CYCLE = ("Θλ", "Σ◯", "Ξ", "Π↺", "Ψmeta")
_EPS = 1.0e-12

ComplexArray = NDArray[np.complex128]
FloatArray = NDArray[np.float64]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    """Convert nested dataclass/numpy values to stable JSON-compatible data."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, np.ndarray):
        if np.iscomplexobj(value):
            return {
                "real": value.real.tolist(),
                "imag": value.imag.tolist(),
                "shape": list(value.shape),
            }
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _stable_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    if isinstance(value, np.ndarray):
        arr = np.ascontiguousarray(value)
        payload = (
            str(arr.dtype).encode("ascii")
            + b"|"
            + str(arr.shape).encode("ascii")
            + b"|"
            + arr.tobytes()
        )
    elif isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = _stable_json_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def _validate_glyph(glyph: str | None, *, fallback: str = "Θλ") -> str:
    """Use only the declared QOSMOS glyph set; no dynamic glyph creation."""
    if glyph is None:
        return fallback
    if glyph not in CANONICAL_GLYPHS:
        raise ValueError(
            f"Unknown glyph {glyph!r}. Allowed glyphs: {', '.join(CANONICAL_GLYPHS)}"
        )
    return glyph


def _as_1d_complex(data: ArrayLike, *, target_size: int | None = None) -> ComplexArray:
    arr = np.asarray(data, dtype=np.complex128).reshape(-1)
    if arr.size == 0:
        raise ValueError("data must contain at least one value")
    if not np.all(np.isfinite(arr.real)) or not np.all(np.isfinite(arr.imag)):
        raise ValueError("data contains NaN or infinite values")
    if target_size is None or arr.size == target_size:
        return arr.copy()
    if target_size < 1:
        raise ValueError("target_size must be positive")

    # Linear resampling keeps the module dependency-light and accepts arbitrary
    # source lengths; np.fft itself does not require power-of-two lengths.
    src_x = np.linspace(0.0, 1.0, arr.size)
    dst_x = np.linspace(0.0, 1.0, target_size)
    real = np.interp(dst_x, src_x, arr.real)
    imag = np.interp(dst_x, src_x, arr.imag)
    return (real + 1j * imag).astype(np.complex128)


def _resize_2d(array: ArrayLike, shape: tuple[int, int]) -> NDArray[Any]:
    """Dependency-light 2D linear resize for real or complex arrays."""
    arr = np.asarray(array)
    if arr.ndim != 2:
        raise ValueError(f"expected a 2D array, received shape {arr.shape}")
    if arr.shape == shape:
        return arr.copy()

    src_y = np.linspace(0.0, 1.0, arr.shape[0])
    src_x = np.linspace(0.0, 1.0, arr.shape[1])
    dst_y = np.linspace(0.0, 1.0, shape[0])
    dst_x = np.linspace(0.0, 1.0, shape[1])

    def resize_real(real_array: NDArray[Any]) -> FloatArray:
        row_interp = np.empty((arr.shape[0], shape[1]), dtype=np.float64)
        for row_idx, row in enumerate(real_array):
            row_interp[row_idx] = np.interp(dst_x, src_x, row)
        out = np.empty(shape, dtype=np.float64)
        for col_idx in range(shape[1]):
            out[:, col_idx] = np.interp(dst_y, src_y, row_interp[:, col_idx])
        return out

    if np.iscomplexobj(arr):
        return resize_real(arr.real) + 1j * resize_real(arr.imag)
    return resize_real(arr.astype(np.float64))


def _normalize(array: ArrayLike) -> NDArray[Any]:
    arr = np.asarray(array)
    norm = float(np.linalg.norm(arr))
    if norm <= _EPS:
        return arr.copy()
    return arr / norm


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


def _field_hash(field: ArrayLike) -> str:
    arr = np.asarray(field)
    rounded = np.round(arr.real, 12)
    if np.iscomplexobj(arr):
        rounded = rounded + 1j * np.round(arr.imag, 12)
    return _sha256(np.asarray(rounded))


def deterministic_symbol_vector(symbol: str, dimension: int) -> FloatArray:
    """Stable symbol vector; unlike Python hash(), this is process-independent."""
    if dimension < 1:
        raise ValueError("dimension must be positive")
    seed_bytes = hashlib.sha256(symbol.encode("utf-8")).digest()[:8]
    seed = int.from_bytes(seed_bytes, byteorder="big", signed=False)
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(dimension)
    return _normalize(vector).astype(np.float64)


# ---------------------------------------------------------------------------
# Typed records
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class HMEConfig:
    memory_size: int = 64
    encoding_resolution: int = 16
    field_decay: float = 0.0
    max_records: int = 4096
    use_hann_window: bool = True
    normalize_patterns: bool = True
    retrieval_distance_scale: float = 0.25
    relevance_threshold: float = 0.0

    def __post_init__(self) -> None:
        if self.memory_size < 4:
            raise ValueError("memory_size must be at least 4")
        if self.encoding_resolution < 2:
            raise ValueError("encoding_resolution must be at least 2")
        if self.encoding_resolution > self.memory_size:
            raise ValueError("encoding_resolution cannot exceed memory_size")
        if not 0.0 <= self.field_decay < 1.0:
            raise ValueError("field_decay must be in [0, 1)")
        if self.max_records < 1:
            raise ValueError("max_records must be positive")
        if self.retrieval_distance_scale <= 0.0:
            raise ValueError("retrieval_distance_scale must be positive")
        if not np.isfinite(self.relevance_threshold) or not 0.0 <= self.relevance_threshold <= 1.0:
            raise ValueError("relevance_threshold must be finite and in [0, 1]")


@dataclass(slots=True)
class CollapseConfig:
    enabled: bool = True
    lambda_c: float = _CORE_LAMBDA_C
    kappa_damp: float = _CORE_KAPPA_DAMP
    min_rho: float = 1.0e-6
    hysteresis: float = 0.08
    cooldown_steps: int = 2
    radius_fraction: float = 0.12
    phase_lock_strength: float = 0.78
    quantization_levels: int = 12
    stable_drift_max: float = 0.08

    # DEVELOP realization-only salience switches. Disabled by default.
    influence_write_gain: bool = False
    influence_retrieval: bool = False
    enable_inscription_rejection: bool = False
    write_gain_scale: float = 0.25
    write_gain_floor: float = 0.05
    write_gain_ceiling: float = 1.5
    retrieval_weight: float = 0.15
    rejection_threshold: float | None = None

    def __post_init__(self) -> None:
        if not np.isfinite(self.lambda_c):
            raise ValueError("lambda_c must be finite")
        if not 0.0 <= self.kappa_damp <= 10.0:
            raise ValueError("kappa_damp must be in [0, 10]")
        if self.min_rho <= 0.0:
            raise ValueError("min_rho must be positive")
        if self.cooldown_steps < 0:
            raise ValueError("cooldown_steps cannot be negative")
        if not 0.01 <= self.radius_fraction <= 0.5:
            raise ValueError("radius_fraction must be in [0.01, 0.5]")
        if not 0.0 <= self.phase_lock_strength <= 1.0:
            raise ValueError("phase_lock_strength must be in [0, 1]")
        if self.quantization_levels < 2:
            raise ValueError("quantization_levels must be at least 2")
        if not np.isfinite(self.write_gain_scale) or self.write_gain_scale < 0.0:
            raise ValueError("write_gain_scale must be finite and non-negative")
        if not np.isfinite(self.write_gain_floor) or self.write_gain_floor < 0.0:
            raise ValueError("write_gain_floor must be finite and non-negative")
        if not np.isfinite(self.write_gain_ceiling) or self.write_gain_ceiling < self.write_gain_floor:
            raise ValueError("write_gain_ceiling must be finite and >= write_gain_floor")
        if not np.isfinite(self.retrieval_weight) or not 0.0 <= self.retrieval_weight <= 1.0:
            raise ValueError("retrieval_weight must be finite and in [0, 1]")
        if self.rejection_threshold is not None and not np.isfinite(self.rejection_threshold):
            raise ValueError("rejection_threshold must be finite or None")


@dataclass(slots=True)
class HMEArtifact:
    artifact_id: str
    t: int
    tag: str
    glyph: str
    position: tuple[int, int]
    gain: float
    observer_weight: float
    payload_size: int
    payload_hash: str
    pattern_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(slots=True)
class RetrievalHit:
    artifact_id: str
    base_score: float
    collapse_salience: float
    final_score: float
    distance_score: float
    query_score: float
    pattern_score: float

    @property
    def score(self) -> float:
        """Legacy alias: score is the ephemeral final retrieval score."""
        return self.final_score

    def to_dict(self) -> dict[str, Any]:
        data = _jsonable(asdict(self))
        data["score"] = self.final_score
        return data


@dataclass(slots=True)
class HMERetrieval:
    position: tuple[int, int]
    radius: int
    window: ComplexArray
    decoded_surface: ComplexArray
    decoded_vector: ComplexArray
    confidence: float
    hits: list[RetrievalHit]
    outcome: str = "MATCH"
    rejected: bool = False
    rejection_reason: str | None = None

    def __iter__(self):
        """Legacy convenience: iterate over decoded-surface rows."""
        return iter(self.decoded_surface)

    def __array__(self, dtype: Any = None) -> NDArray[Any]:
        return np.asarray(self.decoded_surface, dtype=dtype)

    @property
    def shape(self) -> tuple[int, ...]:
        return self.decoded_surface.shape

    def to_dict(self, include_arrays: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "position": self.position,
            "radius": self.radius,
            "confidence": self.confidence,
            "outcome": self.outcome,
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
            "hits": [hit.to_dict() for hit in self.hits],
            "decoded_vector": _jsonable(self.decoded_vector),
        }
        if include_arrays:
            data["window"] = _jsonable(self.window)
            data["decoded_surface"] = _jsonable(self.decoded_surface)
        return data


@dataclass(slots=True)
class PsiMetaFrame:
    run_id: str
    step: int
    phase: int
    rho: float
    phi_energy: float
    gamma_mag: float
    reflex_conf: float
    entropy: float
    dS: float
    drift: float
    stable: bool
    collapse_triggered: bool
    tags: list[str]
    c_psi: float
    engine_id: str = ENGINE_ID
    schema_id: str = SCHEMA_ID
    notes: list[str] = field(default_factory=list)
    scalars: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(slots=True)
class CollapseLayer:
    event_id: str
    step: int
    center: tuple[int, int]
    radius: int
    score: float
    threshold: float
    mode: str
    glyph: str
    pre_hash: str
    post_hash: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(slots=True)
class QMeshNode:
    node_id: str
    kind: str
    t: int
    position: tuple[int, int] | None
    glyph: str | None
    payload_hash: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(slots=True)
class QMeshEdge:
    source: str
    target: str
    relation: str
    weight: float = 1.0
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(slots=True)
class EngineStepResult:
    W_t: FloatArray
    meta: PsiMetaFrame
    memory_artifact: HMEArtifact | None
    collapse_event: CollapseLayer | None


# ---------------------------------------------------------------------------
# QMesh: minimal semantic/lineage mesh
# ---------------------------------------------------------------------------


class QMesh:
    """Small, dependency-free semantic mesh compatible with drop-in use."""

    def __init__(self) -> None:
        self.nodes: "OrderedDict[str, QMeshNode]" = OrderedDict()
        self.edges: list[QMeshEdge] = []
        self._last_memory_node: str | None = None
        self._last_collapse_node: str | None = None

    def add_node(self, node: QMeshNode) -> QMeshNode:
        existing = self.nodes.get(node.node_id)
        if existing is not None and existing != node:
            raise ValueError(f"QMesh node id collision: {node.node_id}")
        self.nodes[node.node_id] = node
        return node

    def add_edge(self, edge: QMeshEdge) -> QMeshEdge:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise KeyError("QMesh edge endpoints must exist before adding an edge")
        self.edges.append(edge)
        return edge

    def add_memory_artifact(self, artifact: HMEArtifact) -> QMeshNode:
        node_id = f"memory:{artifact.artifact_id}"
        node = self.add_node(
            QMeshNode(
                node_id=node_id,
                kind="HMEArtifact",
                t=artifact.t,
                position=artifact.position,
                glyph=artifact.glyph,
                payload_hash=artifact.payload_hash,
                attrs={
                    "tag": artifact.tag,
                    "gain": artifact.gain,
                    "observer_weight": artifact.observer_weight,
                    "pattern_hash": artifact.pattern_hash,
                    **artifact.metadata,
                },
            )
        )
        if self._last_memory_node is not None:
            self.add_edge(
                QMeshEdge(
                    source=self._last_memory_node,
                    target=node_id,
                    relation="Π↺:next_memory",
                )
            )
        self._last_memory_node = node_id
        return node

    def add_collapse_layer(self, event: CollapseLayer) -> QMeshNode:
        node_id = f"collapse:{event.event_id}"
        node = self.add_node(
            QMeshNode(
                node_id=node_id,
                kind="CollapseLayer",
                t=event.step,
                position=event.center,
                glyph=event.glyph,
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
        if self._last_collapse_node is not None:
            self.add_edge(
                QMeshEdge(
                    source=self._last_collapse_node,
                    target=node_id,
                    relation="Π↺:next_collapse",
                )
            )
        if self._last_memory_node is not None:
            self.add_edge(
                QMeshEdge(
                    source=self._last_memory_node,
                    target=node_id,
                    relation="Π↺:memory_precedes_collapse",
                    weight=event.score,
                )
            )
        self._last_collapse_node = node_id
        return node

    def link_collapse_to_memory(
        self, event: CollapseLayer, artifact: HMEArtifact
    ) -> None:
        source = f"collapse:{event.event_id}"
        target = f"memory:{artifact.artifact_id}"
        if source in self.nodes and target in self.nodes:
            self.add_edge(
                QMeshEdge(
                    source=source,
                    target=target,
                    relation="Λψ→Σ◯:consolidate",
                    weight=max(event.score, 0.0),
                )
            )

    def merge_from(self, other: "QMesh", *, prefix: str = "") -> dict[str, int]:
        added_nodes = 0
        added_edges = 0
        id_map: dict[str, str] = {}
        for node in other.nodes.values():
            node_id = f"{prefix}{node.node_id}" if prefix else node.node_id
            id_map[node.node_id] = node_id
            if node_id not in self.nodes:
                self.add_node(replace(node, node_id=node_id))
                added_nodes += 1
        for edge in other.edges:
            mapped = replace(
                edge,
                source=id_map[edge.source],
                target=id_map[edge.target],
            )
            if mapped not in self.edges:
                self.add_edge(mapped)
                added_edges += 1
        return {"nodes": added_nodes, "edges": added_edges}

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }


# ---------------------------------------------------------------------------
# HME: complex field memory
# ---------------------------------------------------------------------------


class HME:
    """
    Concrete Holographic Memory Encoding realization.

    The field is a complex 2D superposition. Each payload is converted to a
    normalized FFT outer-product pattern and written into a bounded spatial
    patch. The artifact ledger preserves payload/provenance for query-aware
    retrieval and QMesh lineage.
    """

    def __init__(
        self,
        memory_size: int = 64,
        encoding_resolution: int = 16,
        *,
        config: HMEConfig | None = None,
    ) -> None:
        self.config = config or HMEConfig(
            memory_size=memory_size,
            encoding_resolution=encoding_resolution,
        )
        self.field: ComplexArray = np.zeros(
            (self.config.memory_size, self.config.memory_size),
            dtype=np.complex128,
        )
        self.records: "OrderedDict[str, HMEArtifact]" = OrderedDict()
        self._payloads: "OrderedDict[str, ComplexArray]" = OrderedDict()
        self._patterns: "OrderedDict[str, ComplexArray]" = OrderedDict()
        self._counter = 0

    @property
    def memory_grid(self) -> ComplexArray:
        """Legacy-compatible alias for old HolographicMemory code."""
        return self.field

    @memory_grid.setter
    def memory_grid(self, value: ArrayLike) -> None:
        arr = np.asarray(value, dtype=np.complex128)
        if arr.shape != self.field.shape:
            arr = _resize_2d(arr, self.field.shape)
        self.field = arr.astype(np.complex128)

    @property
    def memory_size(self) -> int:
        return self.config.memory_size

    @property
    def encoding_resolution(self) -> int:
        return self.config.encoding_resolution

    def _generate_pattern(self, data: ArrayLike) -> tuple[ComplexArray, ComplexArray]:
        vector = _as_1d_complex(data, target_size=self.encoding_resolution)
        if self.config.use_hann_window:
            vector = vector * np.hanning(vector.size)
        vector = _normalize(vector).astype(np.complex128)

        spectrum = np.fft.fft(vector)
        spectral_outer = spectrum[:, None] * np.conjugate(spectrum[None, :])
        pattern = np.fft.ifft2(spectral_outer)
        if self.config.normalize_patterns:
            pattern = _normalize(pattern)
        return vector, pattern.astype(np.complex128)

    # Legacy helper names retained for old exploration scripts.
    def _generate_holographic_pattern(self, data: ArrayLike) -> ComplexArray:
        return self._generate_pattern(data)[1]

    def _fft(self, data: ArrayLike, n: int) -> ComplexArray:
        return np.fft.fft(_as_1d_complex(data, target_size=int(n)))

    def _ifft(self, data: ArrayLike) -> ComplexArray:
        return np.fft.ifft(np.asarray(data, dtype=np.complex128))

    def _ifft2d(self, data: ArrayLike) -> ComplexArray:
        arr = np.asarray(data, dtype=np.complex128)
        if arr.ndim != 2:
            raise ValueError("_ifft2d expects a 2D array")
        return np.fft.ifft2(arr)

    def _get_grid_slice(
        self, x: int, y: int, pattern_size: int
    ) -> tuple[range, range]:
        grid_slice, _ = self._patch_slices(
            (int(x), int(y)), (int(pattern_size), int(pattern_size))
        )
        return (
            range(grid_slice[0].start or 0, grid_slice[0].stop or 0),
            range(grid_slice[1].start or 0, grid_slice[1].stop or 0),
        )

    def _patch_slices(
        self, position: tuple[int, int], pattern_shape: tuple[int, int]
    ) -> tuple[tuple[slice, slice], tuple[slice, slice]]:
        x, y = map(int, position)
        height, width = pattern_shape
        half_h = height // 2
        half_w = width // 2

        raw_x0 = x - half_h
        raw_y0 = y - half_w
        raw_x1 = raw_x0 + height
        raw_y1 = raw_y0 + width

        grid_x0 = max(0, raw_x0)
        grid_y0 = max(0, raw_y0)
        grid_x1 = min(self.memory_size, raw_x1)
        grid_y1 = min(self.memory_size, raw_y1)

        pat_x0 = grid_x0 - raw_x0
        pat_y0 = grid_y0 - raw_y0
        pat_x1 = pat_x0 + (grid_x1 - grid_x0)
        pat_y1 = pat_y0 + (grid_y1 - grid_y0)

        return (
            (slice(grid_x0, grid_x1), slice(grid_y0, grid_y1)),
            (slice(pat_x0, pat_x1), slice(pat_y0, pat_y1)),
        )

    def _trim_records(self) -> None:
        while len(self.records) > self.config.max_records:
            artifact_id, _ = self.records.popitem(last=False)
            self._payloads.pop(artifact_id, None)
            self._patterns.pop(artifact_id, None)

    def encode(
        self,
        data: ArrayLike,
        position: tuple[int, int],
        recursive_factor: float = 0.1,
        *,
        tag: str | None = None,
        glyph: str = "Σ◯",
        observer_weight: float = 1.0,
        t: int = 0,
        metadata: Mapping[str, Any] | None = None,
    ) -> HMEArtifact:
        if not np.isfinite(recursive_factor):
            raise ValueError("recursive_factor must be finite")
        if not np.isfinite(observer_weight):
            raise ValueError("observer_weight must be finite")
        glyph = _validate_glyph(glyph)
        position = (int(position[0]), int(position[1]))
        if not (0 <= position[0] < self.memory_size and 0 <= position[1] < self.memory_size):
            raise ValueError(f"position {position} is outside the HME field")

        if self.config.field_decay > 0.0:
            self.field *= 1.0 - self.config.field_decay

        vector, pattern = self._generate_pattern(data)
        gain = float(recursive_factor) * float(observer_weight)
        grid_slice, pattern_slice = self._patch_slices(position, pattern.shape)
        self.field[grid_slice] += gain * pattern[pattern_slice]

        self._counter += 1
        tag_value = tag or f"hme:{self._counter:06d}"
        payload_hash = _sha256(vector)
        pattern_hash = _sha256(pattern)
        artifact_id = _sha256(
            {
                "counter": self._counter,
                "t": int(t),
                "tag": tag_value,
                "glyph": glyph,
                "position": position,
                "payload_hash": payload_hash,
                "pattern_hash": pattern_hash,
            }
        )[:20]

        artifact = HMEArtifact(
            artifact_id=artifact_id,
            t=int(t),
            tag=tag_value,
            glyph=glyph,
            position=position,
            gain=gain,
            observer_weight=float(observer_weight),
            payload_size=int(vector.size),
            payload_hash=payload_hash,
            pattern_hash=pattern_hash,
            metadata=dict(metadata or {}),
        )
        self.records[artifact_id] = artifact
        self._payloads[artifact_id] = vector
        self._patterns[artifact_id] = pattern
        self._trim_records()
        return artifact

    def encode_symbol(
        self,
        symbol: str,
        position: tuple[int, int],
        recursive_factor: float = 0.1,
        *,
        glyph: str = "Σ◯",
        observer_weight: float = 1.0,
        t: int = 0,
        metadata: Mapping[str, Any] | None = None,
    ) -> HMEArtifact:
        vector = deterministic_symbol_vector(symbol, self.encoding_resolution)
        merged_metadata = {"symbol": symbol, **dict(metadata or {})}
        return self.encode(
            vector,
            position,
            recursive_factor,
            tag=f"symbol:{symbol}",
            glyph=glyph,
            observer_weight=observer_weight,
            t=t,
            metadata=merged_metadata,
        )

    def _extract_window(
        self, position: tuple[int, int], radius: int
    ) -> tuple[ComplexArray, tuple[slice, slice]]:
        x, y = map(int, position)
        radius = max(1, int(radius))
        x0 = max(0, x - radius)
        x1 = min(self.memory_size, x + radius + 1)
        y0 = max(0, y - radius)
        y1 = min(self.memory_size, y + radius + 1)
        slices = (slice(x0, x1), slice(y0, y1))
        return self.field[slices].copy(), slices

    def retrieve(
        self,
        position: tuple[int, int],
        resolution_scale: int = 4,
        *,
        query: ArrayLike | str | None = None,
        top_k: int = 5,
        relevance_threshold: float | None = None,
        influence_retrieval: bool = False,
        retrieval_weight: float = 0.15,
        enable_inscription_rejection: bool = False,
        rejection_threshold: float | None = None,
    ) -> HMERetrieval:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        threshold = (
            self.config.relevance_threshold
            if relevance_threshold is None
            else float(relevance_threshold)
        )
        if not np.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
            raise ValueError("relevance_threshold must be finite and in [0, 1]")
        if not np.isfinite(retrieval_weight) or not 0.0 <= retrieval_weight <= 1.0:
            raise ValueError("retrieval_weight must be finite and in [0, 1]")
        if rejection_threshold is not None and not np.isfinite(rejection_threshold):
            raise ValueError("rejection_threshold must be finite or None")

        position = (int(position[0]), int(position[1]))
        window, _ = self._extract_window(position, resolution_scale)
        decoded_surface = np.fft.ifft2(window)

        query_vector: ComplexArray | None = None
        if isinstance(query, str):
            query_vector = deterministic_symbol_vector(
                query, self.encoding_resolution
            ).astype(np.complex128)
        elif query is not None:
            query_vector = _as_1d_complex(
                query, target_size=self.encoding_resolution
            )
            query_vector = _normalize(query_vector).astype(np.complex128)

        candidates: list[RetrievalHit] = []
        field_norm = float(np.linalg.norm(self.field))
        distance_sigma = max(
            self.memory_size * self.config.retrieval_distance_scale, 1.0
        )

        for artifact_id, artifact in self.records.items():
            dx = artifact.position[0] - position[0]
            dy = artifact.position[1] - position[1]
            distance = math.sqrt(dx * dx + dy * dy)
            distance_score = math.exp(-0.5 * (distance / distance_sigma) ** 2)

            payload = self._payloads[artifact_id]
            if query_vector is None:
                query_score = 1.0
            else:
                denom = float(np.linalg.norm(payload) * np.linalg.norm(query_vector))
                query_score = (
                    float(abs(np.vdot(payload, query_vector)) / denom)
                    if denom > _EPS
                    else 0.0
                )

            pattern = self._patterns[artifact_id]
            grid_slice, pattern_slice = self._patch_slices(
                artifact.position, pattern.shape
            )
            field_patch = self.field[grid_slice]
            pattern_patch = pattern[pattern_slice]
            denom = float(np.linalg.norm(field_patch) * np.linalg.norm(pattern_patch))
            pattern_score = (
                float(abs(np.vdot(field_patch, pattern_patch)) / denom)
                if denom > _EPS and field_norm > _EPS
                else 0.0
            )

            base_score = float(np.clip(
                0.38 * distance_score + 0.42 * query_score + 0.20 * pattern_score,
                0.0,
                1.0,
            ))
            if base_score < threshold:
                continue

            raw_c = artifact.metadata.get("c_psi")
            if raw_c is None:
                collapse_salience = 0.0
            else:
                try:
                    c_value = float(raw_c)
                except (TypeError, ValueError):
                    c_value = 0.0
                if not np.isfinite(c_value):
                    c_value = 0.0
                positive_c = max(c_value, 0.0)
                collapse_salience = positive_c / (1.0 + positive_c)

            final_score = base_score
            if influence_retrieval:
                final_score = base_score + (
                    retrieval_weight
                    * collapse_salience
                    * (1.0 - base_score)
                )
            final_score = float(np.clip(final_score, 0.0, 1.0))

            candidates.append(
                RetrievalHit(
                    artifact_id=artifact_id,
                    base_score=base_score,
                    collapse_salience=collapse_salience,
                    final_score=final_score,
                    distance_score=distance_score,
                    query_score=query_score,
                    pattern_score=pattern_score,
                )
            )

        candidates.sort(key=lambda hit: hit.final_score, reverse=True)
        hits = candidates[:top_k]

        if hits:
            weights = np.asarray([max(hit.final_score, _EPS) for hit in hits])
            payloads = np.stack([self._payloads[hit.artifact_id] for hit in hits])
            decoded_vector = np.average(payloads, axis=0, weights=weights)
            # Confidence remains semantic: C(psi) salience may rerank an
            # eligible hit but must not raise its semantic confidence.
            confidence = float(hits[0].base_score)
            outcome = "MATCH"
        else:
            decoded_vector = np.zeros(
                self.encoding_resolution, dtype=np.complex128
            )
            confidence = 0.0
            outcome = "NO_MATCH"

        rejected = False
        rejection_reason: str | None = None
        if (
            hits
            and enable_inscription_rejection
            and rejection_threshold is not None
        ):
            best_artifact = self.records[hits[0].artifact_id]
            raw_c = best_artifact.metadata.get("c_psi")
            try:
                origin_c = float(raw_c) if raw_c is not None else None
            except (TypeError, ValueError):
                origin_c = None
            if origin_c is not None and np.isfinite(origin_c) and origin_c < rejection_threshold:
                rejected = True
                outcome = "LOW_INSCRIPTION_SALIENCE"
                rejection_reason = (
                    f"originating c_psi {origin_c:.6g} below "
                    f"rejection_threshold {float(rejection_threshold):.6g}"
                )

        return HMERetrieval(
            position=position,
            radius=int(resolution_scale),
            window=window,
            decoded_surface=decoded_surface,
            decoded_vector=decoded_vector,
            confidence=confidence,
            hits=hits,
            outcome=outcome,
            rejected=rejected,
            rejection_reason=rejection_reason,
        )

    def merge(self, other: "HME | ArrayLike", *, weight: float = 1.0) -> None:
        if not np.isfinite(weight):
            raise ValueError("weight must be finite")
        if isinstance(other, HME):
            incoming = other.field
        else:
            incoming = np.asarray(other, dtype=np.complex128)
        if incoming.ndim != 2:
            raise ValueError("incoming HME field must be 2D")
        if incoming.shape != self.field.shape:
            incoming = _resize_2d(incoming, self.field.shape)
        self.field += float(weight) * incoming

        if isinstance(other, HME):
            for artifact_id, artifact in other.records.items():
                new_id = artifact_id
                if new_id in self.records and self.records[new_id] != artifact:
                    new_id = f"{artifact_id}-{_sha256(artifact.to_dict())[:8]}"
                    artifact = replace(artifact, artifact_id=new_id)
                self.records[new_id] = artifact
                self._payloads[new_id] = other._payloads[artifact_id].copy()
                self._patterns[new_id] = other._patterns[artifact_id].copy()
            self._trim_records()

    def decay(self, factor: float) -> None:
        if not 0.0 <= factor <= 1.0:
            raise ValueError("factor must be in [0, 1]")
        self.field *= 1.0 - factor

    def clear(self, *, keep_records: bool = False) -> None:
        self.field.fill(0.0)
        if not keep_records:
            self.records.clear()
            self._payloads.clear()
            self._patterns.clear()

    def snapshot(self) -> dict[str, Any]:
        return {
            "engine_id": ENGINE_ID,
            "config": _jsonable(asdict(self.config)),
            "field_hash": _field_hash(self.field),
            "records": [artifact.to_dict() for artifact in self.records.values()],
        }

    def save_npz(self, path: str | os.PathLike[str]) -> Path:
        out = Path(path)
        metadata = json.dumps(self.snapshot(), ensure_ascii=False)
        np.savez_compressed(out, field=self.field, metadata=np.asarray(metadata))
        return out

    def visualize_memory(self) -> None:
        """Legacy console visualization with magnitude values."""
        print("Holographic Memory Grid:")
        for row in np.abs(self.field):
            print(" ".join(f"{value:.2f}" for value in row))
        print()


HolographicMemory = HME


# ---------------------------------------------------------------------------
# QOSMOS HME / collapse overlay engine
# ---------------------------------------------------------------------------


class QOSMOSHMEEngine:
    """Single-file HME + QMesh + W(t) + collapse-layer runtime extension."""

    def __init__(
        self,
        memory_size: int = 64,
        encoding_resolution: int = 16,
        *,
        hme_config: HMEConfig | None = None,
        collapse_config: CollapseConfig | None = None,
        seed: int = 7,
        run_id: str | None = None,
    ) -> None:
        self.hme = HME(
            memory_size=memory_size,
            encoding_resolution=encoding_resolution,
            config=hme_config,
        )
        self.qmesh = QMesh()
        self.collapse_config = collapse_config or CollapseConfig()
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.run_id = run_id or f"qosmos-hme-{self.seed}-{_sha256(self.seed)[:8]}"

        self.psi_field: ComplexArray = np.zeros_like(self.hme.field)
        self._previous_psi_field: ComplexArray = self.psi_field.copy()
        self._previous_W: FloatArray | None = None
        self._previous_entropy = 0.0
        self._last_collapse_step = -10**9
        self._collapse_armed = True

        self.step_index = 0
        self.phase = 0
        self.telemetry: list[PsiMetaFrame] = []
        self.event_log: list[CollapseLayer] = []
        self.frame_history: list[FloatArray] = []
        self.frame_steps: list[int] = []
        self._attached_core: Any | None = None

    @property
    def memory_size(self) -> int:
        return self.hme.memory_size

    @property
    def HME(self) -> HME:
        """Uppercase compatibility alias used by some QOSMOS sketches."""
        return self.hme

    def set_psi_field(self, field_value: ArrayLike, *, blend: float = 1.0) -> None:
        if not 0.0 <= blend <= 1.0:
            raise ValueError("blend must be in [0, 1]")
        incoming = np.asarray(field_value, dtype=np.complex128)
        if incoming.ndim == 1:
            side = int(round(math.sqrt(incoming.size)))
            if side * side != incoming.size:
                raise ValueError("1D psi_field input must have a square number of elements")
            incoming = incoming.reshape(side, side)
        if incoming.ndim != 2:
            raise ValueError("psi_field must be a 2D array")
        if incoming.shape != self.psi_field.shape:
            incoming = _resize_2d(incoming, self.psi_field.shape)
        self._previous_psi_field = self.psi_field.copy()
        self.psi_field = (
            (1.0 - blend) * self.psi_field + blend * incoming
        ).astype(np.complex128)

    def inject_psi(self, delta: ArrayLike, *, gain: float = 1.0) -> None:
        incoming = np.asarray(delta, dtype=np.complex128)
        if incoming.ndim != 2:
            raise ValueError("delta must be a 2D array")
        if incoming.shape != self.psi_field.shape:
            incoming = _resize_2d(incoming, self.psi_field.shape)
        self._previous_psi_field = self.psi_field.copy()
        self.psi_field += float(gain) * incoming

    def _write_gain_multiplier(self, c_psi: Any) -> float:
        cfg = self.collapse_config
        if not cfg.influence_write_gain or c_psi is None:
            return 1.0
        try:
            value = float(c_psi)
        except (TypeError, ValueError):
            return 1.0
        if not np.isfinite(value):
            return 1.0
        raw = 1.0 + cfg.write_gain_scale * max(value, 0.0)
        return float(np.clip(raw, cfg.write_gain_floor, cfg.write_gain_ceiling))

    def encode_memory(
        self,
        data: ArrayLike | str,
        position: tuple[int, int],
        recursive_factor: float = 0.1,
        *,
        tag: str | None = None,
        glyph: str = "Σ◯",
        observer_weight: float = 1.0,
        metadata: Mapping[str, Any] | None = None,
        t: int | None = None,
    ) -> HMEArtifact:
        tick = self.step_index if t is None else int(t)
        durable_metadata = dict(metadata or {})
        effective_recursive_factor = float(recursive_factor) * self._write_gain_multiplier(
            durable_metadata.get("c_psi")
        )
        if isinstance(data, str):
            artifact = self.hme.encode_symbol(
                data,
                position,
                effective_recursive_factor,
                glyph=glyph,
                observer_weight=observer_weight,
                t=tick,
                metadata=durable_metadata,
            )
        else:
            artifact = self.hme.encode(
                data,
                position,
                effective_recursive_factor,
                tag=tag,
                glyph=glyph,
                observer_weight=observer_weight,
                t=tick,
                metadata=durable_metadata,
            )
        self.qmesh.add_memory_artifact(artifact)
        return artifact

    def retrieve_memory(
        self,
        position: tuple[int, int],
        resolution_scale: int = 4,
        *,
        query: ArrayLike | str | None = None,
        top_k: int = 5,
    ) -> HMERetrieval:
        return self.hme.retrieve(
            position,
            resolution_scale,
            query=query,
            top_k=top_k,
            relevance_threshold=self.hme.config.relevance_threshold,
            influence_retrieval=self.collapse_config.influence_retrieval,
            retrieval_weight=self.collapse_config.retrieval_weight,
            enable_inscription_rejection=self.collapse_config.enable_inscription_rejection,
            rejection_threshold=self.collapse_config.rejection_threshold,
        )

    def W(
        self,
        t: float | None = None,
        *,
        phase: float | None = None,
        normalize: bool = True,
        include_memory: bool = True,
    ) -> FloatArray:
        """
        W(t) projection used as an implementation/visualization coordinate.

        This is intentionally not presented as a canonical W-space definition.
        It phase-projects the current ψ field, optionally including HME residue,
        into a real diagnostic plane.
        """
        tick = float(self.step_index if t is None else t)
        angle = float(phase) if phase is not None else 2.0 * math.pi * (tick % 64.0) / 64.0
        combined = self.psi_field + (self.hme.field if include_memory else 0.0)

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

    project_W = W

    def _measure_meta(
        self,
        W_t: FloatArray,
        *,
        gamma_mag: float,
        notes: Sequence[str] = (),
    ) -> PsiMetaFrame:
        combined = self.psi_field + self.hme.field
        phi_energy = float(np.sqrt(np.mean(np.abs(combined) ** 2)))
        rho = _phase_coherence(combined)
        entropy = _normalized_entropy(np.abs(W_t))
        dS = float(entropy - self._previous_entropy)

        if self._previous_W is None:
            drift = 0.0
        else:
            denom = float(np.linalg.norm(self._previous_W)) + _EPS
            drift = float(np.linalg.norm(W_t - self._previous_W) / denom)

        reflex_conf = float(np.clip(1.0 - drift, 0.0, 1.0))
        c_psi = (
            phi_energy / max(rho, self.collapse_config.min_rho)
            - self.collapse_config.kappa_damp * dS
        )
        stable = bool(drift <= self.collapse_config.stable_drift_max)
        tags = ["tick", f"phase:{self.phase}", "Ψmeta:pre-collapse"]

        frame = PsiMetaFrame(
            run_id=self.run_id,
            step=self.step_index,
            phase=self.phase,
            rho=rho,
            phi_energy=phi_energy,
            gamma_mag=float(gamma_mag),
            reflex_conf=reflex_conf,
            entropy=entropy,
            dS=dS,
            drift=drift,
            stable=stable,
            collapse_triggered=False,
            tags=tags,
            c_psi=float(c_psi),
            notes=list(notes),
            scalars={
                "lambda_c": float(self.collapse_config.lambda_c),
                "kappa_damp": float(self.collapse_config.kappa_damp),
                "W_peak": float(np.max(np.abs(W_t))),
                "hme_norm": float(np.linalg.norm(self.hme.field)),
                "psi_norm": float(np.linalg.norm(self.psi_field)),
            },
        )
        return frame

    def _collapse_predicate(self, meta: PsiMetaFrame) -> bool:
        cfg = self.collapse_config
        if not cfg.enabled:
            return False
        if self.step_index - self._last_collapse_step < cfg.cooldown_steps:
            return False

        # Hysteresis prevents rapid arm/disarm chatter around lambda_c.
        if self._collapse_armed:
            fire = meta.c_psi > cfg.lambda_c
            if fire:
                self._collapse_armed = False
            return fire

        if meta.c_psi < cfg.lambda_c - cfg.hysteresis:
            self._collapse_armed = True
        return False

    def _collapse_center(self, W_t: FloatArray) -> tuple[int, int]:
        flat_index = int(np.argmax(np.abs(W_t)))
        return tuple(map(int, np.unravel_index(flat_index, W_t.shape)))

    def _apply_collapse_layer(
        self,
        meta: PsiMetaFrame,
        W_t: FloatArray,
        *,
        center: tuple[int, int] | None = None,
        reason: str = "C_psi exceeded implementation threshold",
    ) -> CollapseLayer:
        cfg = self.collapse_config
        center = center or self._collapse_center(W_t)
        radius = max(2, int(round(self.memory_size * cfg.radius_fraction)))
        pre_hash = _field_hash(self.psi_field)

        y, x = np.indices(self.psi_field.shape)
        distance_sq = (y - center[0]) ** 2 + (x - center[1]) ** 2
        sigma = max(radius / 2.0, 1.0)
        mask = np.exp(-distance_sq / (2.0 * sigma * sigma))

        local = self.psi_field * mask
        weights = np.abs(local)
        if float(weights.sum()) <= _EPS:
            target_phase = 0.0
        else:
            target_phase = float(
                np.angle(np.sum(weights * np.exp(1j * np.angle(local))))
            )

        magnitude = np.abs(self.psi_field)
        levels = cfg.quantization_levels
        max_mag = float(magnitude.max())
        if max_mag > _EPS:
            quantized_mag = np.round((magnitude / max_mag) * (levels - 1))
            quantized_mag = quantized_mag / (levels - 1) * max_mag
        else:
            quantized_mag = magnitude

        locked = quantized_mag * np.exp(1j * target_phase)
        strength = cfg.phase_lock_strength * mask
        self.psi_field = (
            (1.0 - strength) * self.psi_field + strength * locked
        ).astype(np.complex128)
        post_hash = _field_hash(self.psi_field)

        event_id = _sha256(
            {
                "run_id": self.run_id,
                "step": self.step_index,
                "center": center,
                "radius": radius,
                "score": meta.c_psi,
                "pre": pre_hash,
                "post": post_hash,
            }
        )[:20]
        event = CollapseLayer(
            event_id=event_id,
            step=self.step_index,
            center=center,
            radius=radius,
            score=meta.c_psi,
            threshold=cfg.lambda_c,
            mode="localized_phase_lock_quantize",
            glyph="Λψ",
            pre_hash=pre_hash,
            post_hash=post_hash,
            reason=reason,
            metadata={
                "rho": meta.rho,
                "phi_energy": meta.phi_energy,
                "dS": meta.dS,
                "phase_lock_strength": cfg.phase_lock_strength,
                "quantization_levels": cfg.quantization_levels,
                "threshold_scope": "implementation-specific",
            },
        )
        self.event_log.append(event)
        self.qmesh.add_collapse_layer(event)
        self._last_collapse_step = self.step_index
        return event

    def step(
        self,
        input_field: ArrayLike | None = None,
        *,
        input_blend: float = 1.0,
        memory_payload: ArrayLike | str | None = None,
        memory_position: tuple[int, int] | None = None,
        memory_gain: float = 0.1,
        memory_glyph: str = "Σ◯",
        observer_weight: float = 1.0,
        collapse_override: bool | None = None,
        collapse_center: tuple[int, int] | None = None,
        metadata: Mapping[str, Any] | None = None,
        record_frame: bool = True,
    ) -> EngineStepResult:
        """Advance one audited HME/collapse-overlay tick."""
        if input_field is not None:
            self.set_psi_field(input_field, blend=input_blend)

        gamma_mag = float(np.linalg.norm(self.psi_field - self._previous_psi_field))
        W_pre = self.W(self.step_index)

        # Load-bearing order: Ψmeta is computed before the collapse decision.
        meta_pre = self._measure_meta(W_pre, gamma_mag=gamma_mag)
        should_collapse = (
            self._collapse_predicate(meta_pre)
            if collapse_override is None
            else bool(collapse_override)
        )

        collapse_event: CollapseLayer | None = None
        if should_collapse:
            collapse_event = self._apply_collapse_layer(
                meta_pre,
                W_pre,
                center=collapse_center,
                reason=(
                    "manual collapse override"
                    if collapse_override is True
                    else "C_psi exceeded implementation threshold"
                ),
            )

        memory_artifact: HMEArtifact | None = None
        if memory_payload is not None:
            if memory_position is None:
                memory_position = collapse_center or (
                    collapse_event.center
                    if collapse_event is not None
                    else self._collapse_center(W_pre)
                )
            memory_artifact = self.encode_memory(
                memory_payload,
                memory_position,
                memory_gain,
                glyph=memory_glyph,
                observer_weight=observer_weight,
                metadata={
                    **dict(metadata or {}),
                    "committed_after_collapse": collapse_event is not None,
                    "c_psi": float(meta_pre.c_psi),
                },
                t=self.step_index,
            )
            if collapse_event is not None:
                self.qmesh.link_collapse_to_memory(collapse_event, memory_artifact)

        W_post = self.W(self.step_index)
        tags = list(meta_pre.tags)
        if collapse_event is not None:
            tags.append("collapse")
        if memory_artifact is not None:
            tags.append("memory_commit")
        meta = replace(
            meta_pre,
            collapse_triggered=collapse_event is not None,
            tags=tags,
        )
        self.telemetry.append(meta)

        if record_frame:
            self.frame_history.append(W_post.copy())
            self.frame_steps.append(self.step_index)

        self._previous_W = W_post.copy()
        self._previous_entropy = meta.entropy
        self._previous_psi_field = self.psi_field.copy()
        self.step_index += 1
        self.phase += 1

        return EngineStepResult(
            W_t=W_post,
            meta=meta,
            memory_artifact=memory_artifact,
            collapse_event=collapse_event,
        )

    def merge_hme(self, other: HME | ArrayLike, *, weight: float = 1.0) -> None:
        self.hme.merge(other, weight=weight)
        if isinstance(other, HME):
            for artifact in other.records.values():
                if f"memory:{artifact.artifact_id}" not in self.qmesh.nodes:
                    self.qmesh.add_memory_artifact(artifact)

    def attach_to_core(
        self,
        core: Any,
        *,
        merge_existing_hme: bool = False,
        merge_psi_field: bool = False,
        psi_blend: float = 0.5,
        attach_name: str = "hme_overlay",
    ) -> dict[str, Any]:
        """
        Duck-typed optional merge into qosmos_core_v2.X.

        Existing attributes are never overwritten silently. The overlay is
        attached under ``attach_name``. Compatible ``hme``, ``HME``, ``qmesh``,
        and ``psi_field`` values are merged only when explicitly requested.
        """
        if hasattr(core, attach_name):
            existing = getattr(core, attach_name)
            if existing is not self:
                raise AttributeError(
                    f"core already has a different {attach_name!r} attribute"
                )
        else:
            setattr(core, attach_name, self)

        report: dict[str, Any] = {
            "attached_as": attach_name,
            "hme_merged": False,
            "qmesh_merged": False,
            "psi_field_merged": False,
            "W_adapter": False,
            "notes": [],
        }

        if merge_existing_hme:
            existing_hme = getattr(core, "hme", getattr(core, "HME", None))
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

        existing_qmesh = getattr(core, "qmesh", getattr(core, "QMesh", None))
        if isinstance(existing_qmesh, QMesh):
            existing_qmesh.merge_from(self.qmesh, prefix="overlay:")
            report["qmesh_merged"] = True
        elif existing_qmesh is not None and hasattr(existing_qmesh, "add_node"):
            try:
                for node in self.qmesh.nodes.values():
                    node_attrs = node.to_dict()
                    node_attrs.pop("node_id", None)
                    existing_qmesh.add_node(node.node_id, **node_attrs)
                if hasattr(existing_qmesh, "add_edge"):
                    for edge in self.qmesh.edges:
                        edge_attrs = edge.to_dict()
                        edge_attrs.pop("source", None)
                        edge_attrs.pop("target", None)
                        existing_qmesh.add_edge(
                            edge.source,
                            edge.target,
                            **edge_attrs,
                        )
                report["qmesh_merged"] = True
            except TypeError:
                report["notes"].append(
                    "qmesh add_node/add_edge signature was not NetworkX-compatible"
                )

        if merge_psi_field and hasattr(core, "psi_field"):
            core_field = np.asarray(getattr(core, "psi_field"), dtype=np.complex128)
            self.set_psi_field(core_field, blend=psi_blend)
            report["psi_field_merged"] = True

        if not hasattr(core, "W_hme"):
            setattr(core, "W_hme", self.W)
            report["W_adapter"] = True
        else:
            report["notes"].append("core.W_hme already existed and was not overwritten")

        self._attached_core = core
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
            "psi_field_hash": _field_hash(self.psi_field),
            "hme_field_hash": _field_hash(self.hme.field),
            "memory_records": len(self.hme.records),
            "collapse_events": len(self.event_log),
            "qmesh_nodes": len(self.qmesh.nodes),
            "qmesh_edges": len(self.qmesh.edges),
            "collapse_threshold_scope": "implementation-specific",
            "W_scope": "extension diagnostic / visualization projection",
        }

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

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

    def _overlay_glyphs(
        self,
        ax: Any,
        *,
        upto_step: int | None = None,
        show_qmesh: bool = True,
        show_collapses: bool = True,
        show_labels: bool = True,
    ) -> None:
        _, _, Circle = self._require_matplotlib()
        max_step = self.step_index if upto_step is None else int(upto_step)

        visible_nodes = [
            node
            for node in self.qmesh.nodes.values()
            if node.position is not None and node.t <= max_step
        ]
        node_by_id = {node.node_id: node for node in visible_nodes}

        if show_qmesh:
            for edge in self.qmesh.edges:
                source = node_by_id.get(edge.source)
                target = node_by_id.get(edge.target)
                if source is None or target is None:
                    continue
                x0, y0 = source.position
                x1, y1 = target.position
                ax.plot([y0, y1], [x0, x1], linewidth=0.8, alpha=0.45)

        for node in visible_nodes:
            if node.glyph is None:
                continue
            x, y = node.position
            label = node.glyph
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

        if show_collapses:
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
                    "Λψ",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                )

    def render_overlay(
        self,
        *,
        field_mode: str = "W",
        t: int | None = None,
        save_path: str | os.PathLike[str] | None = None,
        title: str | None = None,
        show_qmesh: bool = True,
        show_collapses: bool = True,
        show_labels: bool = True,
        dpi: int = 160,
        close: bool = False,
    ) -> tuple[Any, Any]:
        plt, _, _ = self._require_matplotlib()
        mode = field_mode.lower()
        if mode == "w":
            image = self.W(self.step_index if t is None else t)
            default_title = "QOSMOS W(t) / HME symbolic overlay"
        elif mode in {"hme", "memory"}:
            image = np.abs(self.hme.field)
            default_title = "QOSMOS HME field / QMesh overlay"
        elif mode in {"psi", "psi_field"}:
            image = np.abs(self.psi_field)
            default_title = "QOSMOS ψ field / collapse overlay"
        else:
            raise ValueError("field_mode must be 'W', 'HME', or 'psi'")

        fig, ax = plt.subplots(figsize=(8, 7))
        shown = ax.imshow(image, origin="lower", interpolation="nearest")
        fig.colorbar(shown, ax=ax, label="field magnitude / projection")
        self._overlay_glyphs(
            ax,
            upto_step=self.step_index if t is None else t,
            show_qmesh=show_qmesh,
            show_collapses=show_collapses,
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
        title: str = "QOSMOS W(t) symbolic memory / collapse layers",
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
        fig.colorbar(shown, ax=ax, label="W(t) projection")
        ax.set_xlabel("field y")
        ax.set_ylabel("field x")

        def update(frame_index: int) -> list[Any]:
            ax.clear()
            shown_local = ax.imshow(
                source_frames[frame_index],
                origin="lower",
                interpolation="nearest",
            )
            self._overlay_glyphs(
                ax,
                upto_step=steps[frame_index],
                show_qmesh=True,
                show_collapses=True,
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


class QOSMOSCoreHME(QOSMOSHMEEngine):
    """
    Direct qosmos_core_v2.X integration.

    The standalone field engine remains available as QOSMOSHMEEngine. This
    subclass binds the actual current core conventions:

      ReflectiveStack → Ψmeta → C(ψ) / Λψ → Θλ HME commit → QMesh lineage

    C(ψ) uses the v2.1.4 local form when v27_constants is present:

      C(ψ) = Φ/ρ - κ_damp*dS
    """

    def __init__(
        self,
        memory_size: int = 64,
        encoding_resolution: int = 16,
        *,
        hme_config: HMEConfig | None = None,
        collapse_config: CollapseConfig | None = None,
        seed: int = 7,
        run_id: str | None = None,
        reflective_stack: Any | None = None,
        psi_meta_field: Any | None = None,
        rsbt_engine: Any | None = None,
        bias_calculator: Any | None = None,
        logger: Any | None = None,
    ) -> None:
        super().__init__(
            memory_size=memory_size,
            encoding_resolution=encoding_resolution,
            hme_config=hme_config,
            collapse_config=collapse_config or CollapseConfig(
                lambda_c=_CORE_LAMBDA_C,
                kappa_damp=_CORE_KAPPA_DAMP,
            ),
            seed=seed,
            run_id=run_id,
        )
        self.stack = reflective_stack or ReflectiveStack()
        self.psi_meta = psi_meta_field or PsiMetaField()
        self.rsbt = rsbt_engine or RSBT_CollapseEngine()
        if bias_calculator is not None:
            self.bias = bias_calculator
        elif PsiBiasCalculator is not None:
            glyph_masses = {
                glyph: float(meta.get("mass", 1.0))
                for glyph, meta in _CORE_GLYPH_METADATA.items()
            }
            self.bias = PsiBiasCalculator(
                emotion_weights={},
                glyph_masses=glyph_masses,
            )
        else:
            self.bias = None
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

    def _inject_symbol_into_psi(
        self,
        symbol: str,
        position: tuple[int, int],
        gain: float,
    ) -> None:
        vector = deterministic_symbol_vector(symbol, self.hme.encoding_resolution)
        _, pattern = self.hme._generate_pattern(vector)
        grid_slice, pattern_slice = self.hme._patch_slices(position, pattern.shape)
        self._previous_psi_field = self.psi_field.copy()
        self.psi_field[grid_slice] += float(gain) * pattern[pattern_slice]

    def bind_agent(
        self,
        agent: Any,
        *,
        use_agent_stack: bool = True,
        import_W_field: bool = True,
        attach_name: str = "hme_engine",
    ) -> dict[str, Any]:
        """Bind an existing Ξ agent without replacing its current methods."""
        report = {
            "attached_as": attach_name,
            "stack_bound": False,
            "W_field_imported": False,
            "notes": [],
        }
        existing = getattr(agent, attach_name, None)
        if existing is not None and existing is not self:
            raise AttributeError(f"agent already has a different {attach_name!r}")
        setattr(agent, attach_name, self)
        self.bound_agent = agent

        if use_agent_stack and hasattr(agent, "stack"):
            self.stack = agent.stack
            report["stack_bound"] = True
        if import_W_field and hasattr(agent, "W_field"):
            try:
                self.set_psi_field(np.asarray(agent.W_field), blend=1.0)
                report["W_field_imported"] = True
            except Exception as exc:
                report["notes"].append(f"W_field import skipped: {exc}")
        return report

    def sync_bound_agent(self, *, export_W_field: bool = False) -> dict[str, bool]:
        """Explicitly synchronize selected fields back to a bound agent."""
        report = {"W_field_exported": False, "hme_bundles_linked": False}
        agent = self.bound_agent
        if agent is None:
            return report
        if export_W_field and hasattr(agent, "W_field"):
            agent.W_field = self.W(normalize=False).copy()
            report["W_field_exported"] = True
        if hasattr(agent, "hme_bundles"):
            agent.hme_bundles = list(self.hme.records.values())
            report["hme_bundles_linked"] = True
        return report

    def step_core(
        self,
        glyph: str,
        *,
        phi: float | None = None,
        rho: float | None = None,
        dS: float | None = None,
        delta_psi: float = 0.0,
        observer_id: str = "ψᴽ-001",
        neighbor_deltas: Mapping[str, float] | None = None,
        neighbor_weights: Mapping[str, float] | None = None,
        input_field: ArrayLike | None = None,
        input_blend: float = 1.0,
        position: tuple[int, int] | None = None,
        payload: ArrayLike | str | None = None,
        memory_gain: float = 0.1,
        observer_weight: float = 1.0,
        collapse_override: bool | None = None,
        record_frame: bool = True,
        metadata: Mapping[str, Any] | None = None,
    ) -> EngineStepResult:
        """Advance one tick using the actual qosmos_core_v2.X state flow."""
        glyph = _validate_glyph(glyph, fallback="Ξ")
        if input_field is not None:
            self.set_psi_field(input_field, blend=input_blend)

        position = position or self._default_position(
            glyph, self.memory_size, self.step_index
        )
        self._inject_symbol_into_psi(
            glyph,
            position,
            gain=max(0.01, 0.08 * float(observer_weight)),
        )
        if hasattr(self.stack, "push"):
            self.stack.push(glyph)

        W_pre = self.W(self.step_index)
        entropy = _normalized_entropy(np.abs(W_pre))
        dS_value = (
            float(entropy - self._previous_entropy)
            if dS is None
            else float(dS)
        )
        combined = self.psi_field + self.hme.field
        phi_value = (
            float(np.sqrt(np.mean(np.abs(combined) ** 2)))
            if phi is None
            else float(phi)
        )
        rho_value = (
            max(_phase_coherence(combined), self.collapse_config.min_rho)
            if rho is None
            else max(float(rho), self.collapse_config.min_rho)
        )

        neighbor_deltas = dict(neighbor_deltas or {})
        neighbor_weights = dict(neighbor_weights or {})
        rsbt_map = self.rsbt.propagate_to_neighbors(
            observer_id,
            neighbor_deltas,
            neighbor_weights,
        ) if neighbor_deltas else {}
        w_drift_sum = float(sum(abs(value) for value in rsbt_map.values()))

        # Current core convention: Ψmeta is updated before Λψ is applied.
        psi_meta_value = float(
            self.psi_meta.update(abs(float(delta_psi)), w_drift_sum)
        )

        if self._previous_W is None:
            drift = 0.0
        else:
            drift = float(
                np.linalg.norm(W_pre - self._previous_W)
                / (float(np.linalg.norm(self._previous_W)) + _EPS)
            )
        gamma_mag = float(np.linalg.norm(self.psi_field - self._previous_psi_field))
        reflex_conf = float(np.clip(1.0 - drift, 0.0, 1.0))
        c_psi = (
            phi_value / rho_value
            - self.collapse_config.kappa_damp * dS_value
        )
        bias_score = 0.0
        if self.bias is not None and hasattr(self.bias, "score_with_psi_meta"):
            try:
                bias_score = float(
                    self.bias.score_with_psi_meta(glyph, psi_meta_value)
                )
            except Exception:
                bias_score = 0.0

        meta_pre = PsiMetaFrame(
            run_id=self.run_id,
            step=self.step_index,
            phase=self.phase,
            rho=rho_value,
            phi_energy=phi_value,
            gamma_mag=gamma_mag,
            reflex_conf=reflex_conf,
            entropy=entropy,
            dS=dS_value,
            drift=drift,
            stable=bool(drift <= self.collapse_config.stable_drift_max),
            collapse_triggered=False,
            tags=["tick", f"glyph:{glyph}", "Ψmeta:pre-collapse", "core:v2.X"],
            c_psi=float(c_psi),
            notes=[
                "Φ/ρ/dS use current-core inputs when supplied; otherwise field diagnostics"
            ],
            scalars={
                "psi_meta": psi_meta_value,
                "delta_psi": float(delta_psi),
                "w_drift_sum": w_drift_sum,
                "bias_score": bias_score,
                "lambda_c": float(self.collapse_config.lambda_c),
                "kappa_damp": float(self.collapse_config.kappa_damp),
                "CR_stack": self._stack_compression_ratio(),
            },
        )

        should_collapse = (
            self._collapse_predicate(meta_pre)
            if collapse_override is None
            else bool(collapse_override)
        )
        collapse_event = None
        if should_collapse:
            collapse_event = self._apply_collapse_layer(
                meta_pre,
                W_pre,
                center=position,
                reason=(
                    "manual collapse override"
                    if collapse_override is True
                    else "v2.1.4 local C(ψ) gate exceeded"
                ),
            )
            collapse_event.metadata.update({
                "observer_id": observer_id,
                "source_glyph": glyph,
                "psi_meta": psi_meta_value,
                "rsbt_map": rsbt_map,
            })

        memory_payload = glyph if payload is None else payload
        artifact = self.encode_memory(
            memory_payload,
            position,
            recursive_factor=memory_gain,
            glyph="Σ◯",
            observer_weight=observer_weight,
            metadata={
                "source_glyph": glyph,
                "observer_id": observer_id,
                "psi_meta": psi_meta_value,
                "c_psi": float(c_psi),
                "collapsed": collapse_event is not None,
                "rsbt_map": rsbt_map,
                **dict(metadata or {}),
            },
            t=self.step_index,
        )
        if collapse_event is not None:
            self.qmesh.link_collapse_to_memory(collapse_event, artifact)

        W_post = self.W(self.step_index)
        tags = list(meta_pre.tags) + ["memory_commit"]
        if collapse_event is not None:
            tags.append("collapse")
        meta = replace(
            meta_pre,
            collapse_triggered=collapse_event is not None,
            tags=tags,
        )
        self.telemetry.append(meta)

        if self.logger is not None and hasattr(self.logger, "log"):
            self.logger.log(
                "qosmos_hme_step",
                {
                    "glyph": glyph,
                    "phi": phi_value,
                    "rho": rho_value,
                    "dS": dS_value,
                    "C_psi": c_psi,
                    "collapsed": collapse_event is not None,
                    "psi_meta": psi_meta_value,
                    "artifact_id": artifact.artifact_id,
                },
                agent=observer_id,
            )

        if record_frame:
            self.frame_history.append(W_post.copy())
            self.frame_steps.append(self.step_index)
        self._previous_W = W_post.copy()
        self._previous_entropy = entropy
        self._previous_psi_field = self.psi_field.copy()
        self.step_index += 1
        self.phase += 1

        return EngineStepResult(
            W_t=W_post,
            meta=meta,
            memory_artifact=artifact,
            collapse_event=collapse_event,
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

    def merge_qmesh_snapshot(
        self,
        source: Mapping[str, Any] | str | os.PathLike[str],
        *,
        include_active: bool = True,
        gain: float = 0.08,
    ) -> dict[str, Any]:
        """Ingest the legacy Observer_MemoryMesh.qmesh.json schema."""
        if isinstance(source, Mapping):
            data = dict(source)
        else:
            data = json.loads(Path(source).read_text(encoding="utf-8"))

        active = list(data.get("active_glyphs", [])) if include_active else []
        collapsed_entries = list(data.get("collapsed_glyphs", []))
        symbols: list[tuple[str, str, Mapping[str, Any]]] = []
        symbols.extend((str(g), "active", {}) for g in active)
        for entry in collapsed_entries:
            if isinstance(entry, Mapping):
                symbols.append((str(entry.get("glyph", "Θλ")), "collapsed", entry))
            else:
                symbols.append((str(entry), "collapsed", {}))

        artifacts: list[str] = []
        for index, (symbol, state, entry) in enumerate(symbols):
            glyph = symbol if symbol in CANONICAL_GLYPHS else "Θλ"
            position = self._default_position(symbol, self.memory_size, index)
            artifact = self.encode_memory(
                symbol,
                position,
                recursive_factor=gain * (1.5 if state == "collapsed" else 1.0),
                glyph=glyph,
                metadata={
                    "legacy_qmesh": True,
                    "legacy_state": state,
                    "qmesh_name": data.get("qmesh_name", "Unnamed"),
                    "observer_id": data.get("observer_id", "ψᴽ-unknown"),
                    "recursion_depth": data.get("recursion_depth", 1),
                    "legacy_entry": dict(entry),
                },
                t=self.step_index,
            )
            artifacts.append(artifact.artifact_id)

        return {
            "qmesh_name": data.get("qmesh_name", "Unnamed"),
            "artifacts_added": artifacts,
            "semantic_links_seen": len(data.get("semantic_links", [])),
            "source_hash": _sha256(data),
        }

    def merge_legacy_hme(
        self,
        source: Mapping[str, Any] | str | os.PathLike[str],
        *,
        gain_scale: float = 0.1,
    ) -> dict[str, Any]:
        """Ingest Xi_HMEConverter / xibuild_engine HME JSON structures."""
        if isinstance(source, Mapping):
            data = dict(source)
        else:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
        layers = list(data.get("memory_layers", []))
        artifacts: list[str] = []
        for index, layer in enumerate(layers):
            layer = dict(layer)
            symbol = str(layer.get("source_glyph", layer.get("label", "Θλ")))
            position = self._default_position(symbol, self.memory_size, index)
            artifact = self.encode_memory(
                symbol,
                position,
                recursive_factor=gain_scale * float(layer.get("weight", 1.0)),
                glyph=symbol if symbol in CANONICAL_GLYPHS else "Θλ",
                metadata={
                    "legacy_hme": True,
                    "hme_name": data.get("hme_name", "Unnamed.hme"),
                    "legacy_layer": layer,
                },
                t=self.step_index,
            )
            artifacts.append(artifact.artifact_id)
        return {
            "hme_name": data.get("hme_name", "Unnamed.hme"),
            "layers_seen": len(layers),
            "artifacts_added": artifacts,
            "source_hash": _sha256(data),
        }


# Public current-core class. Keep QOSMOSHMEEngine for standalone compatibility.


def merge_hme_overlay(
    core: Any,
    overlay: QOSMOSHMEEngine,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience wrapper for optional qosmos_core_v2.X attachment."""
    return overlay.attach_to_core(core, **kwargs)


# ---------------------------------------------------------------------------
# Demonstration / smoke test
# ---------------------------------------------------------------------------


def _traveling_field(size: int, t: int, *, seed_phase: float = 0.0) -> ComplexArray:
    y, x = np.indices((size, size))
    center_x = size * (0.25 + 0.5 * ((math.sin(t * 0.17) + 1.0) / 2.0))
    center_y = size * (0.25 + 0.5 * ((math.cos(t * 0.13) + 1.0) / 2.0))
    sigma = max(size * 0.11, 1.0)
    envelope = np.exp(
        -((x - center_x) ** 2 + (y - center_y) ** 2) / (2.0 * sigma * sigma)
    )
    wave = np.exp(1j * (0.22 * x + 0.17 * y + t * 0.31 + seed_phase))
    return (envelope * wave).astype(np.complex128)


def run_demo(
    output_dir: str | os.PathLike[str] = ".",
    *,
    memory_size: int = 64,
    steps: int = 28,
    seed: int = 7,
    make_animation: bool = True,
) -> dict[str, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Demo threshold is intentionally local to the visualization so at least
    # one collapse layer is normally visible. It does not alter the class
    # default or claim a universal threshold.
    collapse = CollapseConfig(lambda_c=0.84, kappa_damp=0.15, cooldown_steps=5)
    engine = QOSMOSCoreHME(
        memory_size=memory_size,
        encoding_resolution=min(16, memory_size // 2),
        collapse_config=collapse,
        seed=seed,
    )

    positions = [
        (memory_size // 3, memory_size // 3),
        (memory_size // 3, 2 * memory_size // 3),
        (2 * memory_size // 3, memory_size // 2),
        (memory_size // 2, memory_size // 4),
    ]
    symbols = ["recursive_self", "memory_residue", "collapse_commit", "field_return"]
    glyphs = ["Πᴽ", "Θλ", "Λψ", "Π↺"]
    for index, (symbol, position, glyph) in enumerate(zip(symbols, positions, glyphs)):
        engine.encode_memory(
            symbol,
            position,
            recursive_factor=0.22 + 0.03 * index,
            glyph=glyph,
            observer_weight=1.0 + index * 0.08,
            metadata={"demo_seed": True, "index": index},
            t=0,
        )

    for t in range(steps):
        field_value = _traveling_field(memory_size, t, seed_phase=seed * 0.01)
        payload: str | None = None
        position: tuple[int, int] | None = None
        glyph = "Θλ"
        if t in {6, 13, 20}:
            payload = f"recursive_frame_{t}"
            position = positions[(t // 6) % len(positions)]
            glyph = DEFAULT_GLYPH_CYCLE[(t // 6) % len(DEFAULT_GLYPH_CYCLE)]
        engine.step(
            field_value,
            input_blend=0.38,
            memory_payload=payload,
            memory_position=position,
            memory_gain=0.18,
            memory_glyph=glyph,
            observer_weight=1.0,
            metadata={"demo_step": t},
        )

    png_path = out_dir / "qosmos_hme_symbolic_overlay.png"
    gif_path = out_dir / "qosmos_hme_symbolic_overlay.gif"
    telemetry_path = out_dir / "qosmos_hme_demo_telemetry.jsonl"
    events_path = out_dir / "qosmos_hme_demo_events.jsonl"
    state_path = out_dir / "qosmos_hme_demo_state.json"

    engine.render_overlay(
        field_mode="W",
        save_path=png_path,
        title="QOSMOS HME / QMesh / Λψ symbolic overlay",
        show_labels=False,
        close=True,
    )
    engine.export_telemetry_jsonl(telemetry_path)
    engine.export_events_jsonl(events_path)
    state_path.write_text(
        json.dumps(engine.state_summary(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    outputs = {
        "png": png_path,
        "telemetry": telemetry_path,
        "events": events_path,
        "state": state_path,
    }
    if make_animation:
        engine.animate(gif_path, fps=8)
        outputs["gif"] = gif_path
    return outputs


def _self_test() -> dict[str, Any]:
    cfg = CollapseConfig(enabled=True, lambda_c=0.1, cooldown_steps=0)
    engine_a = QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        collapse_config=cfg,
        seed=42,
    )
    engine_b = QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        collapse_config=cfg,
        seed=42,
    )

    payload = [0.1, 0.3, 0.9, 0.2]
    artifact_a = engine_a.encode_memory(payload, (12, 12), 0.4, glyph="Σ◯")
    artifact_b = engine_b.encode_memory(payload, (12, 12), 0.4, glyph="Σ◯")
    assert artifact_a.payload_hash == artifact_b.payload_hash
    assert np.allclose(engine_a.hme.field, engine_b.hme.field)

    test_field = _traveling_field(24, 3)
    result = engine_a.step(
        test_field,
        input_blend=1.0,
        memory_payload="self_test",
        memory_position=(10, 10),
        collapse_override=True,
    )
    assert result.meta.collapse_triggered
    assert len(engine_a.telemetry) == 1
    assert len(engine_a.event_log) == 1
    assert result.collapse_event is not None
    assert result.memory_artifact is not None
    assert result.collapse_event.pre_hash != result.collapse_event.post_hash
    assert np.all(np.isfinite(result.W_t))

    retrieval = engine_a.retrieve_memory((12, 12), query=payload)
    assert retrieval.hits
    assert retrieval.confidence > 0.0

    return {
        "status": "PASS",
        "artifact_hash_deterministic": True,
        "field_deterministic": True,
        "telemetry_count": len(engine_a.telemetry),
        "event_count": len(engine_a.event_log),
        "qmesh_nodes": len(engine_a.qmesh.nodes),
        "qmesh_edges": len(engine_a.qmesh.edges),
        "retrieval_confidence": retrieval.confidence,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="QOSMOS HME / QMesh / collapse-layer single-file overlay"
    )
    parser.add_argument("--demo", action="store_true", help="render PNG/GIF demo")
    parser.add_argument("--self-test", action="store_true", help="run deterministic smoke tests")
    parser.add_argument("--output-dir", default=".", help="demo output directory")
    parser.add_argument("--memory-size", type=int, default=64)
    parser.add_argument("--steps", type=int, default=28)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--no-animation", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    ran = False
    if args.self_test:
        ran = True
        print(json.dumps(_self_test(), indent=2, ensure_ascii=False))
    if args.demo:
        ran = True
        outputs = run_demo(
            args.output_dir,
            memory_size=args.memory_size,
            steps=args.steps,
            seed=args.seed,
            make_animation=not args.no_animation,
        )
        print(json.dumps({k: str(v) for k, v in outputs.items()}, indent=2))
    if not ran:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
