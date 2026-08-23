#!/usr/bin/env python3
"""
symbolic_field_dynamics.py
================================
Stable refactor of the July 3, 2025 QOSMOS SymbolicGlyphEngine.

Status
------
Typed Realization / DEVELOP. This module does not amend QOFT/QOSMOS canon.
It preserves the historical computational idea:

    glyph raster
        -> 1D symbolic waveform
        -> recursive Ψ field evolution
        -> observer/W modulation
        -> diffusion-like coupling
        -> FFT/HME spectral diagnostic

The refactor adds deterministic replay, bounded integration, typed telemetry,
ablation controls, fixed-length glyph signatures, and an optional bridge into
the current qosmos_hme_engine. The generated Φ/ρ/dS and C(ψ) values are
explicitly realization-specific diagnostics; they are not asserted to be the
canonical physical quantities.

Historical behavior retained
----------------------------
- ``SymbolicGlyphEngine`` remains available as a compatibility wrapper.
- ``evolve_waveform()``, ``extract_glyph_image()``, and
  ``compute_HME_spectrum()`` retain the old call shapes.
- ``integration_mode='legacy'`` reproduces the old additive update closely,
  including wide clipping. The default ``stable`` mode is recommended.

Current behavior added
----------------------
- Seeded NumPy RNG for exact replay.
- Stable explicit integration:

      Ψ[n+1] = Ψ[n] + dt * (drive + D*laplacian - damping*Ψ[n])

- Field-pressure, coherence, entropy, drift, spectral, and saturation metrics.
- Diagnostic collapse proxy using the current local form:

      C_psi_proxy = Φ_proxy / ρ_proxy - κ_damp * dS_proxy

- Fixed-length field signatures suitable for HME payloads.
- Paired ablation runner using identical seeds.
- Separate diagnostic image exporters.
- Built-in deterministic self-test and command-line demo.

Required dependencies
---------------------
- numpy
- Pillow

Optional dependency
-------------------
- matplotlib, only for PNG diagnostic exports

Drop-in location
----------------
Place this file in the existing ``core/`` directory:

    qosmos_core/core/symbolic_field_dynamics.py

Quick use
---------
    from core.symbolic_field_dynamics import SymbolicFieldDynamicsEngine

    engine = SymbolicFieldDynamicsEngine()
    result = engine.run(glyph="Ξ")
    print(result.summary())

HME bridge
----------
    from core.qosmos_hme_engine import QOSMOSCoreHME
    from core.symbolic_field_dynamics import SymbolicFieldDynamicsEngine

    field_engine = SymbolicFieldDynamicsEngine()
    result = field_engine.run(glyph="Ξ")

    hme = QOSMOSCoreHME(memory_size=64, encoding_resolution=16, seed=7)
    receipt = field_engine.commit_to_hme(
        hme,
        result,
        position=(32, 32),
        recursive_factor=0.15,
    )

The bridge defaults to glyph ``Σ◯`` because it is a consolidation/write step.
It does not redefine ``Θλ`` as a write operator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Optional current-core constants
# ---------------------------------------------------------------------------

try:
    from .v27_constants import CONST as _CORE_CONST
except Exception:
    try:
        from core.v27_constants import CONST as _CORE_CONST
    except Exception:
        _CORE_CONST = None

_CORE_ENGINE = getattr(_CORE_CONST, "engine", "qosmos_core_v2.X")
_CORE_SCHEMA = getattr(_CORE_CONST, "schema", "v2X")
_CORE_LAMBDA_C = float(getattr(_CORE_CONST, "lambda_c", 1.67))
_CORE_KAPPA_DAMP = float(getattr(_CORE_CONST, "kappa_damp_default", 0.15))

ENGINE_ID = f"{_CORE_ENGINE}+symbolic-field-dynamics-v1.0.0"
SCHEMA_ID = f"{_CORE_SCHEMA}:symbolic-field-dynamics-v1"
REALIZATION_STATUS = "Typed Realization / DEVELOP"
_EPS = 1.0e-12

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


# ---------------------------------------------------------------------------
# Stable helpers
# ---------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, np.ndarray):
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
        payload = json.dumps(
            _jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_l2(values: ArrayLike) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    norm = float(np.linalg.norm(arr))
    if norm <= _EPS:
        return np.zeros_like(arr)
    return arr / norm


def _normalize_minmax(values: ArrayLike) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    span = hi - lo
    if span <= _EPS:
        return np.zeros_like(arr)
    return (arr - lo) / span


def _resample_1d(values: ArrayLike, size: int) -> FloatArray:
    if size < 1:
        raise ValueError("size must be positive")
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        raise ValueError("cannot resample an empty array")
    if arr.size == size:
        return arr.copy()
    src = np.linspace(0.0, 1.0, arr.size)
    dst = np.linspace(0.0, 1.0, size)
    return np.interp(dst, src, arr).astype(np.float64)


def _cosine_similarity(a: ArrayLike, b: ArrayLike) -> float:
    av = np.asarray(a, dtype=np.float64).reshape(-1)
    bv = np.asarray(b, dtype=np.float64).reshape(-1)
    if av.size != bv.size:
        bv = _resample_1d(bv, av.size)
    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    if denom <= _EPS:
        return 0.0
    return float(np.clip(np.dot(av, bv) / denom, -1.0, 1.0))


def _normalized_entropy(values: ArrayLike) -> float:
    weights = np.abs(np.asarray(values, dtype=np.float64)).reshape(-1)
    total = float(np.sum(weights))
    if total <= _EPS or weights.size <= 1:
        return 0.0
    p = weights / total
    p = p[p > _EPS]
    entropy = -float(np.sum(p * np.log(p)))
    return float(np.clip(entropy / math.log(weights.size), 0.0, 1.0))


def _field_hash(values: ArrayLike) -> str:
    arr = np.round(np.asarray(values, dtype=np.float64), 12)
    return _sha256(arr)


def _validate_finite(name: str, values: ArrayLike) -> None:
    if not np.all(np.isfinite(np.asarray(values))):
        raise FloatingPointError(f"{name} contains NaN or infinite values")


def _default_font_candidates(font_path: str | None) -> list[str]:
    candidates: list[str] = []
    if font_path:
        candidates.append(font_path)
    candidates.extend(
        [
            "DejaVuSans-Bold.ttf",
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    return list(dict.fromkeys(candidates))


# ---------------------------------------------------------------------------
# Typed configuration and results
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SymbolicFieldConfig:
    """Configuration for the stable symbolic-field realization."""

    grid_size: int = 200
    img_size: int = 128
    font_size: int = 100
    font_path: str | None = None
    num_steps: int = 400
    lattice_size: int = 8
    seed: int = 7

    # Historical seed/evolution controls.
    initial_noise_std: float = 0.05
    phase0: float = math.pi / 4.0
    phase_drift_per_step: float = 0.02
    phase_wobble: float = 0.10
    phase_wobble_rate: float = 0.01
    amplitude: float = 0.50
    amplitude_modulation: float = 0.30
    amplitude_rate: float = 0.02
    drive_cycles: float = 1.50
    observer_gain: float = 1.00
    w_min: float = 0.01
    w_max: float = 1.00

    # Stable integration controls.
    integration_mode: str = "stable"  # stable | legacy
    dt: float = 0.04
    diffusion: float = 0.05
    damping: float = 0.12
    clip_limit: float = 12.0
    legacy_clip_limit: float = 1000.0

    # Diagnostic signature and collapse-proxy controls.
    signature_size: int = 32
    lambda_c: float = _CORE_LAMBDA_C
    kappa_damp: float = _CORE_KAPPA_DAMP
    min_rho_proxy: float = 0.50

    def __post_init__(self) -> None:
        if self.grid_size < 16:
            raise ValueError("grid_size must be at least 16")
        if self.img_size < 16:
            raise ValueError("img_size must be at least 16")
        if self.font_size < 4:
            raise ValueError("font_size must be at least 4")
        if self.num_steps < 2:
            raise ValueError("num_steps must be at least 2")
        if self.lattice_size < 1:
            raise ValueError("lattice_size must be positive")
        if self.initial_noise_std < 0.0:
            raise ValueError("initial_noise_std cannot be negative")
        if self.integration_mode not in {"stable", "legacy"}:
            raise ValueError("integration_mode must be 'stable' or 'legacy'")
        if self.dt <= 0.0:
            raise ValueError("dt must be positive")
        if self.diffusion < 0.0:
            raise ValueError("diffusion cannot be negative")
        if self.damping < 0.0:
            raise ValueError("damping cannot be negative")
        if self.clip_limit <= 0.0 or self.legacy_clip_limit <= 0.0:
            raise ValueError("clip limits must be positive")
        if self.signature_size < 4:
            raise ValueError("signature_size must be at least 4")
        if self.min_rho_proxy <= 0.0:
            raise ValueError("min_rho_proxy must be positive")
        for name in (
            "phase0",
            "phase_drift_per_step",
            "phase_wobble",
            "phase_wobble_rate",
            "amplitude",
            "amplitude_modulation",
            "amplitude_rate",
            "drive_cycles",
            "observer_gain",
            "w_min",
            "w_max",
            "lambda_c",
            "kappa_damp",
        ):
            if not np.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        if self.w_max <= self.w_min:
            raise ValueError("w_max must be greater than w_min")


@dataclass(slots=True)
class AblationConfig:
    """Feature switches for paired ON/OFF tests."""

    glyph_seed: bool = True
    initial_noise: bool = True
    observer_modulation: bool = True
    recursive_drive: bool = True
    diffusion: bool = True
    damping: bool = True

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(slots=True)
class FieldFrameMetrics:
    step: int
    rms: float
    energy: float
    max_abs: float
    drift: float
    seed_coherence: float
    spectral_entropy: float
    spectral_centroid: float
    spectral_spread: float
    saturation_fraction: float
    phi_proxy: float
    rho_proxy: float
    dS_proxy: float
    c_psi_proxy: float
    collapse_proxy_triggered: bool

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(slots=True)
class SymbolicFieldResult:
    glyph: str
    x: FloatArray
    glyph_waveform: FloatArray
    psi: FloatArray
    hme_spectrum: FloatArray
    signature: FloatArray
    metrics: list[FieldFrameMetrics]
    collapse_steps: list[int]
    config: SymbolicFieldConfig
    ablation: AblationConfig
    engine_id: str = ENGINE_ID
    schema_id: str = SCHEMA_ID
    realization_status: str = REALIZATION_STATUS
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def final_field(self) -> FloatArray:
        return self.psi[-1].copy()

    @property
    def final_metrics(self) -> FieldFrameMetrics:
        return self.metrics[-1]

    @property
    def signature_hash(self) -> str:
        return _field_hash(self.signature)

    @property
    def trajectory_hash(self) -> str:
        return _field_hash(self.psi)

    def summary(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "schema_id": self.schema_id,
            "realization_status": self.realization_status,
            "glyph": self.glyph,
            "steps": int(self.psi.shape[0]),
            "grid_size": int(self.psi.shape[1]),
            "integration_mode": self.config.integration_mode,
            "seed": self.config.seed,
            "signature_size": int(self.signature.size),
            "signature_hash": self.signature_hash,
            "trajectory_hash": self.trajectory_hash,
            "collapse_steps": list(self.collapse_steps),
            "final_metrics": self.final_metrics.to_dict(),
            "ablation": self.ablation.to_dict(),
            "metadata": _jsonable(self.metadata),
        }

    def save_npz(self, path: str | os.PathLike[str]) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            out,
            glyph=np.asarray(self.glyph),
            x=self.x,
            glyph_waveform=self.glyph_waveform,
            psi=self.psi,
            hme_spectrum=self.hme_spectrum,
            signature=self.signature,
            collapse_steps=np.asarray(self.collapse_steps, dtype=np.int64),
            summary_json=np.asarray(
                json.dumps(self.summary(), ensure_ascii=False, sort_keys=True)
            ),
        )
        return out

    def save_summary(self, path: str | os.PathLike[str]) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(self.summary(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return out


@dataclass(slots=True)
class AblationComparison:
    feature: str
    baseline_signature_hash: str
    ablated_signature_hash: str
    signature_cosine: float
    final_field_rmse: float
    collapse_step_delta: int
    metric_delta: dict[str, float]
    effect_detected: bool

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SymbolicFieldDynamicsEngine:
    """
    Deterministic glyph-to-field encoder and dynamics probe.

    The engine is deliberately narrow. It does not claim that glyphs are
    physical fields, that the FFT is an optical hologram, or that the proxy
    collapse score is a universal law. It provides a stable realization that
    can be measured, ablated, stored in HME, and compared against baselines.
    """

    def __init__(
        self,
        config: SymbolicFieldConfig | None = None,
        *,
        ablation: AblationConfig | None = None,
    ) -> None:
        self.config = config or SymbolicFieldConfig()
        self.ablation = ablation or AblationConfig()

    # ------------------------------------------------------------------
    # Glyph raster -> waveform
    # ------------------------------------------------------------------

    def _load_font(self) -> tuple[ImageFont.ImageFont, str]:
        for candidate in _default_font_candidates(self.config.font_path):
            try:
                return ImageFont.truetype(candidate, self.config.font_size), candidate
            except Exception:
                continue
        return ImageFont.load_default(), "Pillow-default"

    @staticmethod
    def _fallback_symbol_waveform(glyph: str, size: int) -> FloatArray:
        """Deterministic fallback if the selected font cannot render a glyph."""
        seed = int.from_bytes(
            hashlib.sha256(glyph.encode("utf-8")).digest()[:8],
            byteorder="big",
            signed=False,
        )
        rng = np.random.default_rng(seed)
        raw = rng.standard_normal(max(8, size // 4))
        smooth = np.convolve(raw, np.ones(5) / 5.0, mode="same")
        return _normalize_minmax(_resample_1d(smooth, size))

    def render_glyph_waveform(self, glyph: str) -> tuple[FloatArray, dict[str, Any]]:
        if not glyph:
            raise ValueError("glyph cannot be empty")

        image = Image.new("L", (self.config.img_size, self.config.img_size), color=0)
        draw = ImageDraw.Draw(image)
        font, font_source = self._load_font()
        bbox = draw.textbbox((0, 0), glyph, font=font)
        width = max(1, bbox[2] - bbox[0])
        height = max(1, bbox[3] - bbox[1])
        x = (self.config.img_size - width) / 2.0 - bbox[0]
        y = (self.config.img_size - height) / 2.0 - bbox[1]
        draw.text((x, y), glyph, fill=255, font=font)

        # Historical code resized the raster directly to one row. That is
        # effectively a vertical projection. We keep the behavior explicitly.
        projected = image.resize(
            (self.config.grid_size, 1),
            resample=Image.Resampling.BILINEAR,
        )
        waveform = np.asarray(projected, dtype=np.float64).reshape(-1) / 255.0
        used_fallback = False
        if float(np.max(waveform)) <= _EPS:
            waveform = self._fallback_symbol_waveform(glyph, self.config.grid_size)
            used_fallback = True

        return waveform.astype(np.float64), {
            "font_source": font_source,
            "font_fallback_waveform": used_fallback,
            "glyph_bbox": [int(v) for v in bbox],
            "raster_size": [self.config.img_size, self.config.img_size],
        }

    # ------------------------------------------------------------------
    # Dynamics
    # ------------------------------------------------------------------

    @staticmethod
    def _observer_weights(num_agents: int, steps: int) -> FloatArray:
        t = np.linspace(0.0, 2.0 * math.pi, steps, endpoint=False)
        phases = np.arange(num_agents, dtype=np.float64)[:, None]
        phases *= 2.0 * math.pi / num_agents
        return np.sin(t[None, :] + phases)

    def _measure_frame(
        self,
        step: int,
        current: FloatArray,
        previous: FloatArray,
        seed_waveform: FloatArray,
        previous_entropy: float,
    ) -> FieldFrameMetrics:
        energy = float(np.mean(current * current))
        rms = math.sqrt(max(energy, 0.0))
        max_abs = float(np.max(np.abs(current)))
        drift = float(
            np.linalg.norm(current - previous)
            / (float(np.linalg.norm(previous)) + _EPS)
        )
        seed_coherence = abs(_cosine_similarity(current, seed_waveform))

        spectrum = np.abs(np.fft.rfft(current))
        spectral_entropy = _normalized_entropy(spectrum)
        if float(np.sum(spectrum)) <= _EPS:
            centroid = 0.0
            spread = 0.0
        else:
            frequencies = np.linspace(0.0, 1.0, spectrum.size)
            weights = spectrum / float(np.sum(spectrum))
            centroid = float(np.sum(frequencies * weights))
            spread = float(
                math.sqrt(max(np.sum(((frequencies - centroid) ** 2) * weights), 0.0))
            )

        active_clip = (
            self.config.legacy_clip_limit
            if self.config.integration_mode == "legacy"
            else self.config.clip_limit
        )
        saturation = float(np.mean(np.abs(current) >= 0.98 * active_clip))

        # Realization-specific diagnostic mapping. These values are intentionally
        # named proxies and are not a silent redefinition of canonical Φ/ρ/dS.
        phi_proxy = float(np.clip(rms + drift + spectral_entropy, 0.0, 3.0))
        rho_proxy = float(
            np.clip(
                self.config.min_rho_proxy + 2.5 * seed_coherence,
                self.config.min_rho_proxy,
                3.0,
            )
        )
        dS_proxy = float(np.clip(spectral_entropy - previous_entropy, -3.0, 3.0))
        c_psi_proxy = float(
            phi_proxy / max(rho_proxy, self.config.min_rho_proxy)
            - self.config.kappa_damp * dS_proxy
        )

        return FieldFrameMetrics(
            step=int(step),
            rms=rms,
            energy=energy,
            max_abs=max_abs,
            drift=drift,
            seed_coherence=seed_coherence,
            spectral_entropy=spectral_entropy,
            spectral_centroid=centroid,
            spectral_spread=spread,
            saturation_fraction=saturation,
            phi_proxy=phi_proxy,
            rho_proxy=rho_proxy,
            dS_proxy=dS_proxy,
            c_psi_proxy=c_psi_proxy,
            collapse_proxy_triggered=bool(c_psi_proxy > self.config.lambda_c),
        )

    def evolve(
        self,
        glyph_waveform: ArrayLike,
        *,
        num_steps: int | None = None,
        lattice_size: int | None = None,
        seed: int | None = None,
    ) -> tuple[FloatArray, FloatArray, list[FieldFrameMetrics]]:
        cfg = self.config
        steps = cfg.num_steps if num_steps is None else int(num_steps)
        agents = cfg.lattice_size if lattice_size is None else int(lattice_size)
        if steps < 2:
            raise ValueError("num_steps must be at least 2")
        if agents < 1:
            raise ValueError("lattice_size must be positive")

        rng = np.random.default_rng(cfg.seed if seed is None else int(seed))
        x = np.linspace(0.0, 2.0 * math.pi, cfg.grid_size, endpoint=True)
        seed_waveform = _resample_1d(glyph_waveform, cfg.grid_size)

        psi = np.zeros((steps, cfg.grid_size), dtype=np.float64)
        if self.ablation.glyph_seed:
            psi[0] = seed_waveform
        if self.ablation.initial_noise and cfg.initial_noise_std > 0.0:
            psi[0] += cfg.initial_noise_std * rng.standard_normal(cfg.grid_size)

        observer_weights = self._observer_weights(agents, steps)
        w_coordinates = np.linspace(cfg.w_min, cfg.w_max, agents)
        metrics: list[FieldFrameMetrics] = []
        initial_metrics = self._measure_frame(
            0,
            psi[0],
            np.zeros_like(psi[0]),
            seed_waveform,
            0.0,
        )
        metrics.append(initial_metrics)
        previous_entropy = initial_metrics.spectral_entropy

        for n in range(1, steps):
            previous = psi[n - 1]
            laplacian = np.gradient(np.gradient(previous, x), x)

            observer_mod = np.zeros_like(previous)
            if self.ablation.observer_modulation:
                for i in range(agents):
                    phase_i = (
                        cfg.phase0
                        + cfg.phase_drift_per_step * n
                        + cfg.phase_wobble * math.sin(cfg.phase_wobble_rate * n + i)
                    )
                    observer_mod += (
                        observer_weights[i, n]
                        * np.sin(w_coordinates[i] * x + phase_i)
                    )
                observer_mod *= cfg.observer_gain / max(agents, 1)

            amplitude_n = cfg.amplitude * (
                1.0 + cfg.amplitude_modulation * math.cos(cfg.amplitude_rate * n)
            )
            if self.ablation.recursive_drive:
                if cfg.integration_mode == "legacy":
                    drive_phase = 2.0 * math.pi * cfg.drive_cycles * n
                else:
                    drive_phase = (
                        2.0
                        * math.pi
                        * cfg.drive_cycles
                        * n
                        / max(steps - 1, 1)
                    )
                drive = amplitude_n * np.sin(drive_phase + observer_mod)
            else:
                drive = np.zeros_like(previous)

            diffusion_term = (
                cfg.diffusion * laplacian
                if self.ablation.diffusion
                else np.zeros_like(previous)
            )
            damping_term = (
                -cfg.damping * previous
                if self.ablation.damping
                else np.zeros_like(previous)
            )

            if cfg.integration_mode == "legacy":
                next_field = previous + drive + diffusion_term
                clip_limit = cfg.legacy_clip_limit
            else:
                next_field = previous + cfg.dt * (
                    drive + diffusion_term + damping_term
                )
                clip_limit = cfg.clip_limit

            psi[n] = np.clip(next_field, -clip_limit, clip_limit)
            _validate_finite(f"psi[{n}]", psi[n])

            frame_metrics = self._measure_frame(
                n,
                psi[n],
                previous,
                seed_waveform,
                previous_entropy,
            )
            metrics.append(frame_metrics)
            previous_entropy = frame_metrics.spectral_entropy

        return x, psi, metrics

    # ------------------------------------------------------------------
    # HME diagnostic and signature
    # ------------------------------------------------------------------

    @staticmethod
    def compute_hme_spectrum(
        psi: ArrayLike,
        *,
        log_scale: bool = True,
    ) -> FloatArray:
        field = np.asarray(psi, dtype=np.float64)
        if field.ndim != 2:
            raise ValueError("psi must be a 2D [time, field] array")
        magnitude = np.fft.fftshift(np.abs(np.fft.fft2(field)))
        if log_scale:
            magnitude = np.log1p(magnitude)
        return _normalize_minmax(magnitude).astype(np.float64)

    def build_signature(
        self,
        glyph_waveform: ArrayLike,
        psi: ArrayLike,
        hme_spectrum: ArrayLike,
        metrics: Sequence[FieldFrameMetrics],
        *,
        size: int | None = None,
    ) -> FloatArray:
        target = self.config.signature_size if size is None else int(size)
        if target < 4:
            raise ValueError("signature size must be at least 4")

        glyph_seed = np.asarray(glyph_waveform, dtype=np.float64).reshape(-1)
        field = np.asarray(psi, dtype=np.float64)
        hme = np.asarray(hme_spectrum, dtype=np.float64)
        final_fft = np.fft.rfft(field[-1])
        temporal_fft = np.fft.rfft(np.mean(field, axis=1))
        metric_tail = np.asarray(
            [
                metrics[-1].rms,
                metrics[-1].drift,
                metrics[-1].seed_coherence,
                metrics[-1].spectral_entropy,
                metrics[-1].spectral_centroid,
                metrics[-1].spectral_spread,
                metrics[-1].c_psi_proxy,
                float(len([m for m in metrics if m.collapse_proxy_triggered]))
                / len(metrics),
            ],
            dtype=np.float64,
        )

        # Keep three explicitly allocated bands so glyph identity is not washed
        # out by the much larger trajectory/spectrum arrays. Each band is
        # standardized separately, then the full signature is L2-normalized.
        seed_size = max(4, target // 3)
        final_size = max(4, target // 3)
        dynamic_size = target - seed_size - final_size
        if dynamic_size < 1:
            dynamic_size = 1
            final_size = max(1, target - seed_size - dynamic_size)

        seed_source = np.concatenate([glyph_seed, np.gradient(glyph_seed)])
        final_source = np.concatenate(
            [field[-1], np.abs(final_fft), np.angle(final_fft)]
        )
        dynamic_source = np.concatenate(
            [
                _resample_1d(hme.reshape(-1), max(16, target)),
                np.abs(temporal_fft),
                metric_tail,
            ]
        )

        def standardized_segment(source: FloatArray, segment_size: int) -> FloatArray:
            segment = _resample_1d(source, segment_size)
            segment = segment - float(np.mean(segment))
            scale = float(np.std(segment))
            if scale > _EPS:
                segment = segment / scale
            return segment

        signature = np.concatenate(
            [
                standardized_segment(seed_source, seed_size),
                standardized_segment(final_source, final_size),
                standardized_segment(dynamic_source, dynamic_size),
            ]
        )[:target]
        signature = _normalize_l2(signature)
        _validate_finite("signature", signature)
        return signature

    # ------------------------------------------------------------------
    # Public run / compatibility API
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        glyph: str = "Ξ",
        num_steps: int | None = None,
        lattice_size: int | None = None,
        seed: int | None = None,
        hme_log_scale: bool = True,
    ) -> SymbolicFieldResult:
        waveform, glyph_metadata = self.render_glyph_waveform(glyph)
        x, psi, metrics = self.evolve(
            waveform,
            num_steps=num_steps,
            lattice_size=lattice_size,
            seed=seed,
        )
        hme_spectrum = self.compute_hme_spectrum(psi, log_scale=hme_log_scale)
        signature = self.build_signature(waveform, psi, hme_spectrum, metrics)
        collapse_steps = [
            frame.step for frame in metrics if frame.collapse_proxy_triggered
        ]

        run_seed = self.config.seed if seed is None else int(seed)
        metadata = {
            **glyph_metadata,
            "historical_source": "2025-07-03 engine_symbolic_feedback.py",
            "canonical_scope": "none; implementation realization only",
            "phi_rho_dS_scope": "realization-specific diagnostic proxies",
            "hme_scope": "FFT-derived field diagnostic and payload feature source",
            "run_seed": run_seed,
        }
        return SymbolicFieldResult(
            glyph=glyph,
            x=x,
            glyph_waveform=waveform,
            psi=psi,
            hme_spectrum=hme_spectrum,
            signature=signature,
            metrics=metrics,
            collapse_steps=collapse_steps,
            config=replace(
                self.config,
                num_steps=psi.shape[0],
                lattice_size=(
                    self.config.lattice_size
                    if lattice_size is None
                    else int(lattice_size)
                ),
                seed=run_seed,
            ),
            ablation=replace(self.ablation),
            metadata=metadata,
        )

    @staticmethod
    def extract_glyph_image(
        psi_final: ArrayLike,
        *,
        output_size: int = 256,
    ) -> Image.Image:
        final = np.asarray(psi_final, dtype=np.float64).reshape(-1)
        normalized = _normalize_minmax(final)
        image = Image.fromarray((normalized * 255.0).astype(np.uint8)[None, :])
        return image.resize(
            (output_size, output_size),
            resample=Image.Resampling.NEAREST,
        )

    # ------------------------------------------------------------------
    # HME integration
    # ------------------------------------------------------------------

    def to_hme_payload(
        self,
        result: SymbolicFieldResult,
        *,
        dimensions: int | None = None,
    ) -> FloatArray:
        target = (
            result.signature.size if dimensions is None else int(dimensions)
        )
        if target < 2:
            raise ValueError("dimensions must be at least 2")
        payload = _resample_1d(result.signature, target)
        return _normalize_l2(payload)

    def commit_to_hme(
        self,
        hme_engine: Any,
        result: SymbolicFieldResult,
        *,
        position: tuple[int, int],
        recursive_factor: float = 0.10,
        observer_weight: float = 1.0,
        commit_glyph: str = "Σ◯",
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        """
        Commit the field signature into a compatible current HME engine.

        Expected target API:

            encode_memory(data, position, recursive_factor,
                          glyph=..., observer_weight=..., metadata=...)

        The adapter is intentionally duck-typed so it works with
        QOSMOSCoreHME/QOSMOSHMEEngine without importing them here.
        """
        if not hasattr(hme_engine, "encode_memory"):
            raise TypeError("hme_engine must provide encode_memory(...)")

        encoding_resolution = getattr(
            getattr(hme_engine, "hme", None),
            "encoding_resolution",
            result.signature.size,
        )
        payload = self.to_hme_payload(
            result,
            dimensions=int(encoding_resolution),
        )
        merged_metadata = {
            "typed_bridge": "SymbolicFieldResult -> HME payload",
            "source_engine": result.engine_id,
            "source_glyph": result.glyph,
            "source_signature_hash": result.signature_hash,
            "source_trajectory_hash": result.trajectory_hash,
            "source_integration_mode": result.config.integration_mode,
            "source_ablation": result.ablation.to_dict(),
            "source_collapse_proxy_steps": result.collapse_steps,
            "claim_scope": "tested realization only",
            **dict(metadata or {}),
        }
        return hme_engine.encode_memory(
            payload,
            tuple(map(int, position)),
            recursive_factor=float(recursive_factor),
            glyph=commit_glyph,
            observer_weight=float(observer_weight),
            metadata=merged_metadata,
        )

    # ------------------------------------------------------------------
    # Ablation and comparison
    # ------------------------------------------------------------------

    def run_ablation_pair(
        self,
        feature: str,
        *,
        glyph: str = "Ξ",
    ) -> tuple[SymbolicFieldResult, SymbolicFieldResult, AblationComparison]:
        if feature not in AblationConfig.__dataclass_fields__:
            allowed = ", ".join(AblationConfig.__dataclass_fields__)
            raise ValueError(f"unknown ablation {feature!r}; choose from {allowed}")

        baseline_ablation = replace(self.ablation)
        baseline_ablation = replace(baseline_ablation, **{feature: True})
        ablated_ablation = replace(baseline_ablation, **{feature: False})

        baseline = SymbolicFieldDynamicsEngine(
            replace(self.config),
            ablation=baseline_ablation,
        ).run(glyph=glyph)
        ablated = SymbolicFieldDynamicsEngine(
            replace(self.config),
            ablation=ablated_ablation,
        ).run(glyph=glyph)

        signature_cosine = _cosine_similarity(
            baseline.signature,
            ablated.signature,
        )
        rmse = float(
            np.sqrt(np.mean((baseline.final_field - ablated.final_field) ** 2))
        )
        baseline_metrics = baseline.final_metrics
        ablated_metrics = ablated.final_metrics
        metric_delta = {
            name: float(getattr(baseline_metrics, name) - getattr(ablated_metrics, name))
            for name in (
                "rms",
                "drift",
                "seed_coherence",
                "spectral_entropy",
                "spectral_centroid",
                "spectral_spread",
                "c_psi_proxy",
            )
        }
        effect_detected = bool(
            rmse > 1.0e-8
            or signature_cosine < 0.999999
            or baseline.collapse_steps != ablated.collapse_steps
        )
        comparison = AblationComparison(
            feature=feature,
            baseline_signature_hash=baseline.signature_hash,
            ablated_signature_hash=ablated.signature_hash,
            signature_cosine=signature_cosine,
            final_field_rmse=rmse,
            collapse_step_delta=len(baseline.collapse_steps)
            - len(ablated.collapse_steps),
            metric_delta=metric_delta,
            effect_detected=effect_detected,
        )
        return baseline, ablated, comparison

    # ------------------------------------------------------------------
    # Diagnostics and exports
    # ------------------------------------------------------------------

    @staticmethod
    def _require_matplotlib() -> Any:
        try:
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise RuntimeError("PNG diagnostics require matplotlib") from exc
        return plt

    def save_diagnostics(
        self,
        result: SymbolicFieldResult,
        output_dir: str | os.PathLike[str],
        *,
        dpi: int = 160,
    ) -> dict[str, Path]:
        """Save separate diagnostic plots. No combined subplot dashboard."""
        plt = self._require_matplotlib()
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"symbolic_field_{result.glyph}_{result.config.seed}"

        outputs: dict[str, Path] = {}

        waveform_path = out_dir / f"{stem}_glyph_waveform.png"
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(result.x, result.glyph_waveform)
        ax.set_title(f"{result.glyph} glyph seed waveform")
        ax.set_xlabel("field coordinate x")
        ax.set_ylabel("seed amplitude")
        fig.tight_layout()
        fig.savefig(waveform_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        outputs["glyph_waveform"] = waveform_path

        final_path = out_dir / f"{stem}_final_field.png"
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(result.x, result.final_field)
        ax.set_title(f"{result.glyph} final symbolic field")
        ax.set_xlabel("field coordinate x")
        ax.set_ylabel("Ψ amplitude")
        fig.tight_layout()
        fig.savefig(final_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        outputs["final_field"] = final_path

        spectrum_path = out_dir / f"{stem}_hme_spectrum.png"
        fig, ax = plt.subplots(figsize=(10, 6))
        shown = ax.imshow(
            result.hme_spectrum,
            origin="lower",
            aspect="auto",
            interpolation="nearest",
        )
        fig.colorbar(shown, ax=ax, label="normalized FFT magnitude")
        ax.set_title(f"{result.glyph} HME spectral diagnostic")
        ax.set_xlabel("spatial frequency")
        ax.set_ylabel("temporal frequency")
        fig.tight_layout()
        fig.savefig(spectrum_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        outputs["hme_spectrum"] = spectrum_path

        metrics_path = out_dir / f"{stem}_metrics.png"
        steps = [frame.step for frame in result.metrics]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(steps, [frame.rms for frame in result.metrics], label="RMS")
        ax.plot(
            steps,
            [frame.seed_coherence for frame in result.metrics],
            label="seed coherence",
        )
        ax.plot(
            steps,
            [frame.c_psi_proxy for frame in result.metrics],
            label="C_psi proxy",
        )
        ax.axhline(result.config.lambda_c, linestyle="--", label="lambda_c")
        ax.set_title(f"{result.glyph} symbolic-field telemetry")
        ax.set_xlabel("step")
        ax.set_ylabel("diagnostic value")
        ax.legend()
        fig.tight_layout()
        fig.savefig(metrics_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        outputs["metrics"] = metrics_path

        return outputs


# ---------------------------------------------------------------------------
# Backwards-compatible wrapper
# ---------------------------------------------------------------------------


class SymbolicGlyphEngine:
    """
    Compatibility wrapper for old ``engine_symbolic_feedback.py`` imports.

    Existing calls continue to work while receiving deterministic, stable
    defaults. Pass ``integration_mode='legacy'`` to reproduce the historical
    additive update more closely.
    """

    def __init__(
        self,
        glyph: str = "Ξ",
        grid_size: int = 200,
        font_path: str = "DejaVuSans-Bold.ttf",
        img_size: int = 128,
        font_size: int = 100,
        *,
        seed: int = 7,
        integration_mode: str = "stable",
    ) -> None:
        self.glyph = glyph
        self.config = SymbolicFieldConfig(
            grid_size=grid_size,
            font_path=font_path,
            img_size=img_size,
            font_size=font_size,
            seed=seed,
            integration_mode=integration_mode,
        )
        self._engine = SymbolicFieldDynamicsEngine(self.config)
        self.waveform, self.glyph_metadata = self._engine.render_glyph_waveform(
            glyph
        )
        self.last_result: SymbolicFieldResult | None = None

    def _render_glyph_waveform(self) -> FloatArray:
        return self.waveform.copy()

    def evolve_waveform(
        self,
        num_steps: int = 400,
        lattice_size: int = 8,
    ) -> tuple[FloatArray, FloatArray]:
        self.last_result = self._engine.run(
            glyph=self.glyph,
            num_steps=num_steps,
            lattice_size=lattice_size,
        )
        return self.last_result.x.copy(), self.last_result.psi.copy()

    def extract_glyph_image(self, psi_final: ArrayLike) -> Image.Image:
        return self._engine.extract_glyph_image(psi_final)

    def compute_HME_spectrum(self, Psi: ArrayLike) -> FloatArray:
        # Legacy method keeps the original linear-magnitude normalization.
        return self._engine.compute_hme_spectrum(Psi, log_scale=False)


# ---------------------------------------------------------------------------
# Self-test and CLI
# ---------------------------------------------------------------------------


def _self_test() -> dict[str, Any]:
    config = SymbolicFieldConfig(
        grid_size=96,
        num_steps=120,
        lattice_size=6,
        seed=7312026,
        signature_size=24,
    )
    engine_a = SymbolicFieldDynamicsEngine(config)
    engine_b = SymbolicFieldDynamicsEngine(replace(config))

    result_a = engine_a.run(glyph="Ξ")
    result_b = engine_b.run(glyph="Ξ")
    assert np.array_equal(result_a.psi, result_b.psi)
    assert np.array_equal(result_a.signature, result_b.signature)
    assert result_a.signature_hash == result_b.signature_hash
    assert np.all(np.isfinite(result_a.psi))
    assert result_a.final_metrics.saturation_fraction < 0.01

    result_omega = engine_a.run(glyph="Ω")
    glyph_similarity = _cosine_similarity(
        result_a.signature,
        result_omega.signature,
    )
    assert result_a.signature_hash != result_omega.signature_hash
    assert glyph_similarity < 0.99

    _, _, observer_ablation = engine_a.run_ablation_pair(
        "observer_modulation",
        glyph="Ξ",
    )
    assert observer_ablation.effect_detected

    payload = engine_a.to_hme_payload(result_a, dimensions=16)
    assert payload.shape == (16,)
    assert np.all(np.isfinite(payload))
    assert math.isclose(float(np.linalg.norm(payload)), 1.0, rel_tol=1e-10)

    legacy = SymbolicGlyphEngine(
        glyph="Ξ",
        grid_size=64,
        seed=19,
        integration_mode="stable",
    )
    x, psi = legacy.evolve_waveform(num_steps=32, lattice_size=4)
    assert x.shape == (64,)
    assert psi.shape == (32, 64)
    assert legacy.compute_HME_spectrum(psi).shape == (32, 64)

    return {
        "status": "PASS",
        "deterministic_trajectory": True,
        "deterministic_signature": True,
        "finite_and_unsaturated": True,
        "distinct_glyph_hashes": True,
        "xi_omega_signature_cosine": glyph_similarity,
        "observer_ablation_effect_detected": observer_ablation.effect_detected,
        "observer_ablation_signature_cosine": observer_ablation.signature_cosine,
        "observer_ablation_final_rmse": observer_ablation.final_field_rmse,
        "hme_payload_norm": float(np.linalg.norm(payload)),
        "legacy_api_compatible": True,
        "signature_hash": result_a.signature_hash,
        "trajectory_hash": result_a.trajectory_hash,
    }


def run_demo(
    output_dir: str | os.PathLike[str],
    *,
    glyph: str = "Ξ",
    grid_size: int = 200,
    steps: int = 400,
    lattice_size: int = 8,
    seed: int = 7,
    integration_mode: str = "stable",
    make_plots: bool = True,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = SymbolicFieldConfig(
        grid_size=grid_size,
        num_steps=steps,
        lattice_size=lattice_size,
        seed=seed,
        integration_mode=integration_mode,
    )
    engine = SymbolicFieldDynamicsEngine(config)
    result = engine.run(glyph=glyph)

    safe_glyph = hashlib.sha256(glyph.encode("utf-8")).hexdigest()[:8]
    npz_path = output / f"symbolic_field_{safe_glyph}_{seed}.npz"
    json_path = output / f"symbolic_field_{safe_glyph}_{seed}.json"
    result.save_npz(npz_path)
    result.save_summary(json_path)
    paths: dict[str, Path] = {"npz": npz_path, "summary": json_path}
    if make_plots:
        paths.update(engine.save_diagnostics(result, output))
    return paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stable QOSMOS symbolic-field dynamics and HME feature encoder"
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--glyph", default="Ξ")
    parser.add_argument("--grid-size", type=int, default=200)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--lattice-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--integration-mode", choices=("stable", "legacy"), default="stable")
    parser.add_argument("--output-dir", default="./symbolic_field_output")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument(
        "--ablate",
        choices=tuple(AblationConfig.__dataclass_fields__),
        help="run a paired feature ON/OFF comparison",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    ran = False

    if args.self_test:
        ran = True
        print(json.dumps(_self_test(), indent=2, ensure_ascii=False))

    config = SymbolicFieldConfig(
        grid_size=args.grid_size,
        num_steps=args.steps,
        lattice_size=args.lattice_size,
        seed=args.seed,
        integration_mode=args.integration_mode,
    )
    engine = SymbolicFieldDynamicsEngine(config)

    if args.ablate:
        ran = True
        _, _, comparison = engine.run_ablation_pair(args.ablate, glyph=args.glyph)
        print(json.dumps(comparison.to_dict(), indent=2, ensure_ascii=False))

    if args.demo:
        ran = True
        outputs = run_demo(
            args.output_dir,
            glyph=args.glyph,
            grid_size=args.grid_size,
            steps=args.steps,
            lattice_size=args.lattice_size,
            seed=args.seed,
            integration_mode=args.integration_mode,
            make_plots=not args.no_plots,
        )
        print(
            json.dumps(
                {name: str(path) for name, path in outputs.items()},
                indent=2,
                ensure_ascii=False,
            )
        )

    if not ran:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
