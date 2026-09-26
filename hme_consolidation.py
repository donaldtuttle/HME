"""Opt-in, DEVELOP consolidation around the unchanged v3.1 FFT encoder.

A single aligned site supports weighted moments, not individual-item recovery.
After consolidate(), retained instance state is one owned active patch and one fixed-width
control array. There is no retained engine, codec, payload cache, or lineage.
This module does not change hme_engine.py or enable consolidation by default.
"""
from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hme_engine import HME, HMEConfig, HMEEngine

_MAGIC = b"HMEFC002"
_LEGACY_MAGIC = b"HMEFC001"
_VERSION = 2
_CONTROL = np.dtype([
    ("version", "<u4"), ("memory_size", "<u4"), ("dimension", "<u4"),
    ("hann", "u1"), ("reserved", "u1", (3,)), ("decay", "<f8"),
    ("mass", "<f8"), ("squared_mass", "<f8"), ("writes", "<u8"),
])
_MAX_WRITES = np.iinfo(np.uint64).max
_DIGEST_BYTES = 32


class _PatternEncoder:
    """Reuse the pinned encoder without allocating a grid or retaining records."""
    __slots__ = ("config",)
    _generate_pattern = HME._generate_pattern

    def __init__(self, config: HMEConfig) -> None:
        self.config = config

    @property
    def encoding_resolution(self) -> int:
        return self.config.encoding_resolution


def _owned_bytes(value: Any, seen: set[int] | None = None) -> int:
    """Unique instance-reachable Python storage, excluding classes/modules/code.

    Arrays owned by these instances are counted once by sys.getsizeof (which
    includes the data buffer for owning ndarrays). This is not process RSS.
    """
    if seen is None:
        seen = set()
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, np.ndarray):
        return size + (_owned_bytes(value.base, seen) if value.base is not None else 0)
    if isinstance(value, dict):
        return size + sum(_owned_bytes(k, seen) + _owned_bytes(v, seen)
                          for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return size + sum(_owned_bytes(v, seen) for v in value)
    if hasattr(value, "__dict__"):
        size += _owned_bytes(vars(value), seen)
    for cls in type(value).__mro__:
        slots = cls.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots:
            if name not in ("__dict__", "__weakref__") and hasattr(value, name):
                size += _owned_bytes(getattr(value, name), seen)
    return size


class ConsolidatingMemory:
    """Own a record store, then irreversibly retain only its aligned field.

    Numeric inputs use the pinned HME preprocessing and FFT pattern. Gain is an
    explicit nonnegative multiplier, not an inferred importance score. Decay is
    applied once per accepted write, including a zero-gain write. No wall-clock
    forgetting is implied. All writes use the central, unclipped site.

    consolidate() discards this instance's record/lineage references; it does
    not securely erase RAM or delete caller-owned vectors, results, or files.
    The class is single-threaded. Direct mutation of private state is unsupported.
    """
    __slots__ = ("_engine", "_field", "_control")

    def __init__(self, *, memory_size: int = 64, dimension: int = 16,
                 use_hann_window: bool = False, decay: float = 0.0) -> None:
        for name, value in (("memory_size", memory_size), ("dimension", dimension)):
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
                raise TypeError(f"{name} must be an integer")
            if not 0 <= int(value) <= np.iinfo(np.uint32).max:
                raise ValueError(f"{name} exceeds fixed-width schema")
        if not isinstance(use_hann_window, (bool, np.bool_)):
            raise TypeError("use_hann_window must be boolean")
        cfg = HMEConfig(memory_size=int(memory_size), encoding_resolution=int(dimension),
                        use_hann_window=bool(use_hann_window), field_decay=float(decay))
        self._control = np.zeros(1, dtype=_CONTROL)
        self._control[0] = (_VERSION, cfg.memory_size, cfg.encoding_resolution,
                            int(cfg.use_hann_window), (0, 0, 0), cfg.field_decay,
                            0.0, 0.0, 0)
        self._engine: HMEEngine | None = HMEEngine(hme_config=cfg)
        self._field = self._engine.hme.field

    @property
    def consolidated(self) -> bool:
        return self._engine is None

    @property
    def dimension(self) -> int:
        return int(self._control["dimension"][0])

    @property
    def write_count(self) -> int:
        return int(self._control["writes"][0])

    @property
    def weight_mass(self) -> float:
        return float(self._control["mass"][0])

    @property
    def effective_sample_size(self) -> float:
        squared = float(self._control["squared_mass"][0])
        # This is a weight concentration statistic, not independent evidence.
        return (self.weight_mass / math.sqrt(squared)) ** 2 if squared > 0 else 0.0

    def _config(self) -> HMEConfig:
        c = self._control[0]
        return HMEConfig(memory_size=int(c["memory_size"]),
                         encoding_resolution=int(c["dimension"]),
                         use_hann_window=bool(c["hann"]), field_decay=float(c["decay"]))

    def _slices(self) -> tuple[slice, slice]:
        start = self._field.shape[0] // 2 - self.dimension // 2
        return slice(start, start + self.dimension), slice(start, start + self.dimension)

    def write(self, data: ArrayLike, *, gain: float = 1.0) -> None:
        """Accept a numeric observation, with all validation before mutation.

        The normalized processed vector must be nonzero and finite. Unit-norm
        payloads are required so that tracked mass normalizes the field moment.
        Overflow is rejected, not silently wrapped or promoted to larger state.
        """
        if isinstance(data, str):
            raise TypeError("numeric observations required; semantic text encoding is external")
        gain = float(gain)
        if not math.isfinite(gain) or gain < 0:
            raise ValueError("gain must be finite and nonnegative")
        if self.write_count == _MAX_WRITES:
            raise OverflowError("fixed-width write counter exhausted")
        cfg = self._config()
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            vector, pattern = _PatternEncoder(cfg)._generate_pattern(data)
        if (not np.all(np.isfinite(pattern)) or
                not np.isclose(np.linalg.norm(vector), 1.0, rtol=1e-12, atol=1e-12)):
            raise ValueError("processed payload must have a finite, nonzero unit norm")
        keep = 1.0 - cfg.field_decay
        mass = keep * self.weight_mass + gain
        squared = keep * keep * float(self._control["squared_mass"][0]) + gain * gain
        if not math.isfinite(mass) or not math.isfinite(squared):
            raise OverflowError("fixed-width weight accumulator overflow")
        # Conservative bound prevents the mutating pinned encoder from overflow.
        bound = keep * float(np.max(np.abs(self._field))) + gain * float(np.max(np.abs(pattern)))
        if not math.isfinite(bound):
            raise OverflowError("field update would overflow")
        if self._engine is not None:
            self._engine.encode_memory(data, (cfg.memory_size // 2, cfg.memory_size // 2),
                                       strength=gain, t=self.write_count)
        else:
            self._field *= keep
            self._field[self._slices()] += gain * pattern
        self._control["mass"][0] = mass
        self._control["squared_mass"][0] = squared
        self._control["writes"][0] = self.write_count + 1

    def consolidate(self) -> dict[str, int | bool]:
        """Retain only an owning copy of the active patch; release the full grid.

        Idempotent and irreversible. Active complex pattern bytes are preserved,
        including floating-point residues. New writes remain patch-only. No view
        or hidden snapshot may keep the old grid allocation alive.
        """
        if self._engine is not None:
            patch = self._field[self._slices()].copy(order="C")
            engine = self._engine
            for name in ("records", "_payloads", "_patterns"):
                getattr(engine.hme, name).clear()
            engine.lineage.nodes.clear()
            engine.lineage.edges.clear()
            engine.lineage._last_memory_node = None
            self._field = patch
            self._engine = None
        return self.storage_report()

    def patch_copy(self) -> NDArray[np.complex128]:
        """Return an independent copy of the active FFT-layout patch."""
        return self._field[self._slices()].copy()

    def field_copy(self) -> NDArray[np.complex128]:
        """Materialize a caller-owned full-grid inspection copy.

        In consolidated mode the zero exterior is rebuilt only for this result.
        This potentially large temporary/caller allocation is not retained state.
        Use patch_copy() for inspection without allocating the old grid shape.
        """
        if not self.consolidated:
            return self._field.copy()
        side = int(self._control["memory_size"][0])
        start = side // 2 - self.dimension // 2
        out = np.zeros((side, side), dtype=np.complex128)
        out[start:start+self.dimension, start:start+self.dimension] = self._field
        return out

    def moment(self) -> NDArray[np.complex128]:
        """Read the gain/decay-normalized uncentered second moment.

        This is valid because this adapter permits only one aligned site and
        nonnegative gains. It is not a general decoder for overlapping sites.
        """
        if self.weight_mass <= 0:
            raise ValueError("no positive retained write weight")
        j = (-np.arange(self.dimension)) % self.dimension
        c = self._field[self._slices()][:, j] / self.weight_mass
        return (c + c.conj().T) / 2.0  # Remove roundoff anti-Hermitian residue.

    def reconstruct(self, observed: ArrayLike, mask: ArrayLike, *,
                    ridge: float = 0.01) -> NDArray[np.complex128]:
        """Experimental ridge completion; caller must state observed coordinates.

        Hidden entries are ignored, visible values are copied unchanged. This
        is moment-based numerical completion, not record or text recovery.
        Hann-windowed storage is refused: endpoint information was discarded and
        visible values are not in the tapered, renormalized training coordinates.
        """
        if bool(self._control["hann"][0]):
            raise ValueError("reconstruction requires use_hann_window=False; "
                             "Hann-tapered endpoints cannot be recovered")
        y = np.asarray(observed, dtype=np.complex128)
        m = np.asarray(mask)
        if y.shape != (self.dimension,) or m.shape != y.shape or m.dtype != np.bool_:
            raise ValueError("observed and boolean mask must be dimension-length vectors")
        if not m.any() or m.all():
            raise ValueError("mask must contain observed and hidden coordinates")
        if not np.all(np.isfinite(y[m])):
            raise ValueError("visible observations must be finite")
        ridge = float(ridge)
        if not math.isfinite(ridge) or ridge <= 0:
            raise ValueError("ridge must be finite and positive")
        c = self.moment()
        reg = ridge * float(np.trace(c).real) / self.dimension
        out = np.zeros(self.dimension, dtype=np.complex128)
        out[m] = y[m]
        out[~m] = c[np.ix_(~m, m)] @ np.linalg.solve(
            c[np.ix_(m, m)] + reg * np.eye(int(m.sum())), y[m])
        if not np.all(np.isfinite(out)):
            raise FloatingPointError("nonfinite reconstruction")
        return out

    def retrieve(self, query: ArrayLike, *, top_k: int = 1):
        """Legacy identity lookup is deliberately unavailable after consolidation."""
        if self._engine is None:
            raise RuntimeError("identity lookup unavailable: records were consolidated")
        side = self._field.shape[0]
        return self._engine.retrieve_memory((side // 2, side // 2), query=query, top_k=top_k)

    def storage_report(self) -> dict[str, int | bool]:
        """Count retained arrays and unique instance-owned Python objects.

        Excludes code/module globals, interpreter, transient workspaces, caller
        copies, and allocator slack. Report is computed, never retained.
        Serialized bytes are an uncompressed complete consolidated checkpoint.
        """
        arrays = self._field.nbytes + self._control.nbytes
        records = payloads = patterns = nodes = edges = 0
        if self._engine is not None:
            h = self._engine.hme
            records, payloads, patterns = len(h.records), len(h._payloads), len(h._patterns)
            nodes, edges = len(self._engine.lineage.nodes), len(self._engine.lineage.edges)
            arrays += sum(a.nbytes for a in h._payloads.values())
            arrays += sum(a.nbytes for a in h._patterns.values())
        return {
            "consolidated": self.consolidated, "field_bytes": self._field.nbytes,
            "control_bytes": self._control.nbytes, "retained_array_bytes": arrays,
            "instance_owned_bytes": _owned_bytes(self), "records": records,
            "payloads": payloads, "patterns": patterns, "lineage_nodes": nodes,
            "lineage_edges": edges,
            "active_patch_bytes": self.dimension * self.dimension * 16,
            "packed_real_symmetric_reference_bytes": self.dimension * (self.dimension + 1) // 2 * 8,
            "dense_real_moment_reference_bytes": self.dimension * self.dimension * 8,
            "legacy_grid_data_bytes": int(self._control["memory_size"][0]) ** 2 * 16,
            "consolidated_checkpoint_bytes": len(_MAGIC) + self._control.nbytes
                                             + self.dimension ** 2 * 16 + _DIGEST_BYTES,
        }

    def save(self, path: str | Path) -> Path:
        """Save a complete fixed-layout field-only checkpoint, without pickle.

        No overwrite by default. Hash detects damage; it does not repair it.
        Files/copies outside the instance are not erased by consolidate().
        """
        if not self.consolidated:
            raise RuntimeError("call consolidate() explicitly before saving field-only state")
        out = Path(path)
        payload = _MAGIC + self._control.tobytes() + self._field.astype("<c16", copy=False).tobytes()
        with out.open("xb") as f:
            f.write(payload)
            f.write(hashlib.sha256(payload).digest())
        return out

    @classmethod
    def load(cls, path: str | Path) -> "ConsolidatingMemory":
        """Load compact v2, or validate and losslessly crop a legacy v1 grid.

        Configuration bounds are checked before reading or reshaping the body.
        Legacy files must have a zero exterior; hidden nonzero cells are rejected,
        never silently discarded. Every successful load owns a d-by-d patch.
        """
        path = Path(path)
        with path.open("rb") as f:
            header = f.read(len(_MAGIC) + _CONTROL.itemsize)
            if len(header) != len(_MAGIC) + _CONTROL.itemsize:
                raise ValueError("invalid consolidation checkpoint header")
            magic = header[:len(_MAGIC)]
            if magic not in (_MAGIC, _LEGACY_MAGIC):
                raise ValueError("invalid consolidation checkpoint header")
            control = np.frombuffer(header[len(_MAGIC):], dtype=_CONTROL).copy()
            c = control[0]
            version = 1 if magic == _LEGACY_MAGIC else _VERSION
            if int(c["version"]) != version or int(c["hann"]) not in (0, 1) or np.any(c["reserved"]):
                raise ValueError("unsupported control schema")
            side, dimension = int(c["memory_size"]), int(c["dimension"])
            if dimension > side:
                raise ValueError("checkpoint dimension cannot exceed memory_size")
            HMEConfig(memory_size=side, encoding_resolution=dimension,
                      field_decay=float(c["decay"]))
            if (not np.isfinite(c["mass"]) or c["mass"] < 0 or
                    not np.isfinite(c["squared_mass"]) or c["squared_mass"] < 0):
                raise ValueError("invalid checkpoint weight state")
            stored_side = side if version == 1 else dimension
            body_size = stored_side * stored_side * 16
            f.seek(0, 2)
            if f.tell() != len(header) + body_size + _DIGEST_BYTES:
                raise ValueError("checkpoint length does not match schema")
            f.seek(len(header))
            rest = f.read(body_size + _DIGEST_BYTES)
        if len(rest) != body_size + _DIGEST_BYTES:
            raise ValueError("checkpoint truncated during read")
        payload, digest = header + rest[:-_DIGEST_BYTES], rest[-_DIGEST_BYTES:]
        if hashlib.sha256(payload).digest() != digest:
            raise ValueError("checkpoint integrity failure")
        field = np.frombuffer(rest[:-_DIGEST_BYTES], dtype="<c16").reshape(stored_side, stored_side)
        if not np.all(np.isfinite(field)):
            raise ValueError("nonfinite checkpoint field")
        if version == 1:
            start = side // 2 - dimension // 2
            end = start + dimension
            if (np.any(field[:start, :]) or np.any(field[end:, :]) or
                    np.any(field[start:end, :start]) or np.any(field[start:end, end:])):
                raise ValueError("legacy checkpoint has nonzero cells outside the active patch")
            field = field[start:end, start:end]
        patch = field.copy(order="C")
        control["version"][0] = _VERSION
        result = cls.__new__(cls)
        result._engine, result._field, result._control = None, patch, control
        return result
