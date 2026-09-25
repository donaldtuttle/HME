#!/usr/bin/env python3
"""Holographic Memory Engine: standalone FFT-pattern storage and ranked retrieval.

Numerical storage and ranking are extracted from the preserved v2.2 engine.
Schema v3 uses plain operation names and explicitly uncalibrated relevance scores.
Only NumPy is required. See docs/ARCHITECTURE.md for the exact mechanism.
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
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

ENGINE_ID = "hme-3.0.0"
SCHEMA_ID = "hme-v3"
_EPS = 1.0e-12
ComplexArray = NDArray[np.complex128]
FloatArray = NDArray[np.float64]


def _validate_operation(operation: str | None, *, fallback: str = "write") -> str:
    if operation is None:
        return fallback
    if not isinstance(operation, str) or not operation.strip():
        raise ValueError("operation must be a non-empty string")
    return operation


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
class HMEArtifact:
    artifact_id: str
    t: int
    tag: str
    operation: str
    position: tuple[int, int]
    gain: float
    write_weight: float
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
    salience: float
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
    relevance_score: float
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
            "schema_id": SCHEMA_ID,
            "position": self.position,
            "radius": self.radius,
            "relevance_score": self.relevance_score,
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
class LineageNode:
    node_id: str
    kind: str
    t: int
    position: tuple[int, int] | None
    operation: str | None
    payload_hash: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(slots=True)
class LineageEdge:
    source: str
    target: str
    relation: str
    weight: float = 1.0
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


class HME:
    """
    FFT-pattern associative memory with a retained artifact ledger.

    The field is a complex 2D superposition. Each payload is converted to a
    normalized FFT outer-product pattern and written into a bounded spatial
    patch. The artifact ledger preserves payload/provenance for query-aware
    retrieval and LineageGraph lineage.
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
        strength: float = 0.1,
        *,
        tag: str | None = None,
        operation: str = "write",
        write_weight: float = 1.0,
        t: int = 0,
        metadata: Mapping[str, Any] | None = None,
    ) -> HMEArtifact:
        if not np.isfinite(strength):
            raise ValueError("strength must be finite")
        if not np.isfinite(write_weight):
            raise ValueError("write_weight must be finite")
        operation = _validate_operation(operation)
        position = (int(position[0]), int(position[1]))
        if not (0 <= position[0] < self.memory_size and 0 <= position[1] < self.memory_size):
            raise ValueError(f"position {position} is outside the HME field")

        if self.config.field_decay > 0.0:
            self.field *= 1.0 - self.config.field_decay

        vector, pattern = self._generate_pattern(data)
        gain = float(strength) * float(write_weight)
        grid_slice, pattern_slice = self._patch_slices(position, pattern.shape)
        self.field[grid_slice] += gain * pattern[pattern_slice]

        self._counter += 1
        tag_value = tag or f"hme:{self._counter:06d}"
        payload_hash = _sha256(vector)
        pattern_hash = _sha256(pattern)
        artifact_id = _sha256(
            {
                "schema": SCHEMA_ID,
                "counter": self._counter,
                "t": int(t),
                "tag": tag_value,
                "operation": operation,
                "position": position,
                "payload_hash": payload_hash,
                "pattern_hash": pattern_hash,
            }
        )[:20]

        artifact = HMEArtifact(
            artifact_id=artifact_id,
            t=int(t),
            tag=tag_value,
            operation=operation,
            position=position,
            gain=gain,
            write_weight=float(write_weight),
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
        strength: float = 0.1,
        *,
        operation: str = "write",
        write_weight: float = 1.0,
        t: int = 0,
        metadata: Mapping[str, Any] | None = None,
    ) -> HMEArtifact:
        vector = deterministic_symbol_vector(symbol, self.encoding_resolution)
        merged_metadata = {"symbol": symbol, **dict(metadata or {})}
        return self.encode(
            vector,
            position,
            strength,
            tag=f"symbol:{symbol}",
            operation=operation,
            write_weight=write_weight,
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
        enable_salience_rejection: bool = False,
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

            raw_c = artifact.metadata.get("write_salience")
            if raw_c is None:
                salience = 0.0
            else:
                try:
                    c_value = float(raw_c)
                except (TypeError, ValueError):
                    c_value = 0.0
                if not np.isfinite(c_value):
                    c_value = 0.0
                positive_c = max(c_value, 0.0)
                salience = positive_c / (1.0 + positive_c)

            final_score = base_score
            if influence_retrieval:
                final_score = base_score + (
                    retrieval_weight
                    * salience
                    * (1.0 - base_score)
                )
            final_score = float(np.clip(final_score, 0.0, 1.0))

            candidates.append(
                RetrievalHit(
                    artifact_id=artifact_id,
                    base_score=base_score,
                    salience=salience,
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
            # The base relevance score is uncalibrated. Salience may rerank an
            # eligible hit without changing that base score.
            relevance_score = float(hits[0].base_score)
            outcome = "MATCH"
        else:
            decoded_vector = np.zeros(
                self.encoding_resolution, dtype=np.complex128
            )
            relevance_score = 0.0
            outcome = "NO_MATCH"

        rejected = False
        rejection_reason: str | None = None
        if (
            hits
            and enable_salience_rejection
            and rejection_threshold is not None
        ):
            best_artifact = self.records[hits[0].artifact_id]
            raw_c = best_artifact.metadata.get("write_salience")
            try:
                origin_c = float(raw_c) if raw_c is not None else None
            except (TypeError, ValueError):
                origin_c = None
            if origin_c is not None and np.isfinite(origin_c) and origin_c < rejection_threshold:
                rejected = True
                outcome = "LOW_WRITE_SALIENCE"
                rejection_reason = (
                    f"originating write_salience {origin_c:.6g} below "
                    f"rejection_threshold {float(rejection_threshold):.6g}"
                )

        return HMERetrieval(
            position=position,
            radius=int(resolution_scale),
            window=window,
            decoded_surface=decoded_surface,
            decoded_vector=decoded_vector,
            relevance_score=relevance_score,
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
            "schema_id": SCHEMA_ID,
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


class LineageGraph:
    """In-memory graph recording insertion order and artifact metadata."""

    def __init__(self) -> None:
        self.nodes: OrderedDict[str, LineageNode] = OrderedDict()
        self.edges: list[LineageEdge] = []
        self._last_memory_node: str | None = None

    def add_node(self, node: LineageNode) -> LineageNode:
        existing = self.nodes.get(node.node_id)
        if existing is not None and existing != node:
            raise ValueError(f"LineageGraph node id collision: {node.node_id}")
        self.nodes[node.node_id] = node
        return node


    def add_edge(self, edge: LineageEdge) -> LineageEdge:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise KeyError("LineageGraph edge endpoints must exist before adding an edge")
        self.edges.append(edge)
        return edge


    def add_memory_artifact(self, artifact: HMEArtifact) -> LineageNode:
        node_id = f"memory:{artifact.artifact_id}"
        node = self.add_node(
            LineageNode(
                node_id=node_id,
                kind="HMEArtifact",
                t=artifact.t,
                position=artifact.position,
                operation=artifact.operation,
                payload_hash=artifact.payload_hash,
                attrs={
                    "tag": artifact.tag,
                    "gain": artifact.gain,
                    "write_weight": artifact.write_weight,
                    "pattern_hash": artifact.pattern_hash,
                    **artifact.metadata,
                },
            )
        )
        if self._last_memory_node is not None:
            self.add_edge(
                LineageEdge(
                    source=self._last_memory_node,
                    target=node_id,
                    relation="next_memory",
                )
            )
        self._last_memory_node = node_id
        return node


    def merge_from(self, other: "LineageGraph", *, prefix: str = "") -> dict[str, int]:
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


@dataclass(slots=True)
class SalienceConfig:
    """Experimental write weighting and reranking; all switches default off."""

    influence_write_gain: bool = False
    influence_retrieval: bool = False
    enable_salience_rejection: bool = False
    write_gain_scale: float = 0.25
    write_gain_floor: float = 0.05
    write_gain_ceiling: float = 1.5
    retrieval_weight: float = 0.15
    rejection_threshold: float | None = None

    def __post_init__(self) -> None:
        for name in ("write_gain_scale", "write_gain_floor", "write_gain_ceiling"):
            value = getattr(self, name)
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.write_gain_ceiling < self.write_gain_floor:
            raise ValueError("write_gain_ceiling must be >= write_gain_floor")
        if not np.isfinite(self.retrieval_weight) or not 0.0 <= self.retrieval_weight <= 1.0:
            raise ValueError("retrieval_weight must be finite and in [0, 1]")
        if self.rejection_threshold is not None and not np.isfinite(self.rejection_threshold):
            raise ValueError("rejection_threshold must be finite or None")


class HMEEngine:
    """Standalone memory store, retrieval policy, and insertion lineage."""

    def __init__(
        self,
        memory_size: int = 64,
        encoding_resolution: int = 16,
        *,
        hme_config: HMEConfig | None = None,
        salience_config: SalienceConfig | None = None,
        seed: int = 7,
        run_id: str | None = None,
    ) -> None:
        self.hme = HME(memory_size, encoding_resolution, config=hme_config)
        self.lineage = LineageGraph()
        self.salience_config = salience_config or SalienceConfig()
        # Run provenance only; symbol encodings derive their own seed from SHA-256.
        self.seed = int(seed)
        self.run_id = run_id or f"hme-{self.seed}-{_sha256(self.seed)[:8]}"
        self.step_index = 0

    @property
    def memory_size(self) -> int:
        return self.hme.memory_size

    def _write_gain_multiplier(self, write_salience: Any) -> float:
        cfg = self.salience_config
        if not cfg.influence_write_gain or write_salience is None:
            return 1.0
        try:
            value = float(write_salience)
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
        strength: float = 0.1,
        *,
        tag: str | None = None,
        operation: str = "write",
        write_weight: float = 1.0,
        metadata: Mapping[str, Any] | None = None,
        t: int | None = None,
    ) -> HMEArtifact:
        tick = self.step_index if t is None else int(t)
        durable_metadata = dict(metadata or {})
        effective_strength = float(strength) * self._write_gain_multiplier(
            durable_metadata.get("write_salience")
        )
        if isinstance(data, str):
            artifact = self.hme.encode_symbol(
                data,
                position,
                effective_strength,
                operation=operation,
                write_weight=write_weight,
                t=tick,
                metadata=durable_metadata,
            )
        else:
            artifact = self.hme.encode(
                data,
                position,
                effective_strength,
                tag=tag,
                operation=operation,
                write_weight=write_weight,
                t=tick,
                metadata=durable_metadata,
            )
        self.lineage.add_memory_artifact(artifact)
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
            influence_retrieval=self.salience_config.influence_retrieval,
            retrieval_weight=self.salience_config.retrieval_weight,
            enable_salience_rejection=self.salience_config.enable_salience_rejection,
            rejection_threshold=self.salience_config.rejection_threshold,
        )



def _self_test() -> dict[str, Any]:
    a = HMEEngine(memory_size=24, encoding_resolution=8)
    b = HMEEngine(memory_size=24, encoding_resolution=8)
    payload = np.linspace(-1.0, 1.0, 8)
    first = a.encode_memory(payload, (12, 12))
    second = b.encode_memory(payload, (12, 12))
    result = a.retrieve_memory((12, 12), query=payload, top_k=1)
    checks = {
        "artifact_hash_deterministic": first.artifact_id == second.artifact_id,
        "field_deterministic": bool(np.array_equal(a.hme.field, b.hme.field)),
        "top_hit_correct": bool(result.hits and result.hits[0].artifact_id == first.artifact_id),
        "plain_operation": first.operation == "write",
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "schema_id": SCHEMA_ID, **checks}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Run the deterministic smoke check")
    args = parser.parse_args(argv)
    if args.self_test:
        report = _self_test()
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "PASS" else 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
